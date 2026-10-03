import json
import re
import unicodedata
from pathlib import Path

from .errors import NERPipelineError
from .paths import RULES_PATH
from .schema import ENTITY_TYPES


_TOKEN = re.compile(r"[^\W_]+|[^\w\s]", flags=re.UNICODE)
_CAPITALIZED = re.compile(r"^[A-ZÀ-ỸĐ][\wÀ-ỹĐđ.-]*$", flags=re.UNICODE)
_LOCATION_PREPOSITIONS = {"ở", "tại", "thuộc", "đến", "từ"}
_LOCATION_DESIGNATORS = {
    "tỉnh",
    "quận",
    "huyện",
    "phường",
    "xã",
    "thị xã",
    "thị trấn",
    "thành phố",
}
_ORGANIZATION_CUES = {
    "công an",
    "ủy ban",
    "tòa án",
    "viện kiểm sát",
    "công ty",
    "ngân hàng",
    "chi nhánh",
    "bộ",
    "sở",
    "cục",
    "phòng",
    "trường",
    "đội",
}
_PERSON_TITLES = {"ông", "bà", "anh", "chị", "bị", "nghi phạm"}


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("_", " ")).casefold()


def _tokens(value: str) -> list[tuple[str, int, int]]:
    return [(match.group(), match.start(), match.end()) for match in _TOKEN.finditer(value)]


def _phrase_matches(
    normalized_sentence: list[str], phrase: str
) -> list[tuple[int, int]]:
    phrase_tokens = [_normalize(token) for token, _, _ in _tokens(phrase)]
    return [
        (index, index + len(phrase_tokens))
        for index in range(len(normalized_sentence) - len(phrase_tokens) + 1)
        if phrase_tokens
        and normalized_sentence[index : index + len(phrase_tokens)] == phrase_tokens
    ]


def _consume_name(tokens: list[tuple[str, int, int]], index: int) -> int:
    stop = index
    while stop < len(tokens):
        value = tokens[stop][0]
        if _CAPITALIZED.match(value) or value.isdigit():
            stop += 1
            continue
        if (
            value == "."
            and stop + 1 < len(tokens)
            and _CAPITALIZED.match(tokens[stop + 1][0])
        ):
            stop += 1
            continue
        break
    return stop


class RuleBasedNER:
    """A transparent cue/keyword baseline; rules are not trained from test data."""

    def __init__(self, rules_path: Path = RULES_PATH):
        self.keywords: dict[str, list[str]] = {entity: [] for entity in ENTITY_TYPES}
        if rules_path.is_file():
            try:
                payload = json.loads(rules_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise NERPipelineError(
                    f"Không đọc được file rule {rules_path}: {exc}"
                ) from exc
            if not isinstance(payload, dict):
                raise NERPipelineError("ner_rules.json phải là JSON object.")
            for entity, values in payload.items():
                if entity not in ENTITY_TYPES or not isinstance(values, list) or any(
                    not isinstance(value, str) or not value.strip() for value in values
                ):
                    raise NERPipelineError(
                        "ner_rules.json chỉ nhận PERSON, ORGANIZATION, LOCATION "
                        "với danh sách keyword dạng chuỗi."
                    )
                self.keywords[entity] = values

    def predict(self, sentence: str) -> list[dict[str, str | int]]:
        matches: dict[tuple[int, int], str] = {}
        sentence_tokens = _tokens(sentence)
        normalized_sentence = [_normalize(token) for token, _, _ in sentence_tokens]

        for entity_type, phrases in self.keywords.items():
            for phrase in phrases:
                for index, stop in _phrase_matches(normalized_sentence, phrase):
                    matches[
                        (sentence_tokens[index][1], sentence_tokens[stop - 1][2])
                    ] = entity_type

        for index, (token, start, end) in enumerate(sentence_tokens):
            previous = normalized_sentence[index - 1] if index else ""
            for cue in _LOCATION_PREPOSITIONS:
                for cue_start, cue_end in _phrase_matches(normalized_sentence, cue):
                    if cue_start != index:
                        continue
                    name_start = cue_end
                    name_end = _consume_name(sentence_tokens, name_start)
                    for designator in _LOCATION_DESIGNATORS:
                        if (name_start, name_start + len(_tokens(designator))) in (
                            _phrase_matches(normalized_sentence, designator)
                        ):
                            name_end = _consume_name(
                                sentence_tokens,
                                name_start + len(_tokens(designator)),
                            )
                            break
                    if name_end > name_start:
                        matches.setdefault(
                            (
                                sentence_tokens[name_start][1],
                                sentence_tokens[name_end - 1][2],
                            ),
                            "LOCATION",
                        )
            for designator in _LOCATION_DESIGNATORS:
                for cue_start, cue_end in _phrase_matches(
                    normalized_sentence, designator
                ):
                    if cue_start != index:
                        continue
                    name_end = _consume_name(sentence_tokens, cue_end)
                    if name_end > cue_start:
                        matches.setdefault(
                            (start, sentence_tokens[name_end - 1][2]), "LOCATION"
                        )
            for cue in _ORGANIZATION_CUES:
                for cue_start, cue_end in _phrase_matches(normalized_sentence, cue):
                    if cue_start != index:
                        continue
                    begin = index
                    while begin > 0 and _CAPITALIZED.match(
                        sentence_tokens[begin - 1][0]
                    ):
                        begin -= 1
                    stop = _consume_name(sentence_tokens, cue_end)
                    matches.setdefault(
                        (sentence_tokens[begin][1], sentence_tokens[stop - 1][2]),
                        "ORGANIZATION",
                    )
            if (
                previous in _PERSON_TITLES
                and _CAPITALIZED.match(token)
                and index + 1 < len(sentence_tokens)
                and _CAPITALIZED.match(sentence_tokens[index + 1][0])
            ):
                stop = _consume_name(sentence_tokens, index)
                matches.setdefault(
                    (start, sentence_tokens[stop - 1][2]), "PERSON"
                )

        for index, _ in enumerate(sentence_tokens):
            if not _CAPITALIZED.match(sentence_tokens[index][0]):
                continue
            stop = _consume_name(sentence_tokens, index)
            capitalized_words = sum(
                1
                for token, _, _ in sentence_tokens[index:stop]
                if _CAPITALIZED.match(token)
            )
            if capitalized_words < 2:
                continue
            start, end = sentence_tokens[index][1], sentence_tokens[stop - 1][2]
            if any(
                start < match_end
                and end > match_start
                and label in {"ORGANIZATION", "LOCATION"}
                for (match_start, match_end), label in matches.items()
            ):
                continue
            matches.setdefault((start, end), "PERSON")

        ordered = sorted(
            ((start, end, label) for (start, end), label in matches.items()),
            key=lambda item: (item[0], -(item[1] - item[0])),
        )
        selected: list[tuple[int, int, str]] = []
        for candidate in ordered:
            start, end, _ = candidate
            if any(start < prior_end and end > prior_start for prior_start, prior_end, _ in selected):
                continue
            selected.append(candidate)
        return [
            {
                "text": sentence[start:end],
                "label": label,
                "start": start,
                "end": end,
            }
            for start, end, label in sorted(selected)
        ]
