import json
import re
import unicodedata
from pathlib import Path

from .errors import NERPipelineError
from .paths import RULES_PATH
from .schema import ENTITY_TYPES


_TOKEN = re.compile(r"[^\W_]+|[^\w\s]", flags=re.UNICODE)
_CAPITALIZED = re.compile(r"^[A-ZÀ-ỸĐ][\wÀ-ỹĐđ.-]*$", flags=re.UNICODE)

_LOCATION_PREPOSITIONS = {"ở", "tại", "thuộc"}
_LOCATION_DESIGNATORS = {
    ("tỉnh",),
    ("quận",),
    ("huyện",),
    ("phường",),
    ("xã",),
    ("thị", "xã"),
    ("thị", "trấn"),
    ("thành", "phố"),
}
_LOCATION_CONTEXT = {
    "đường", "phố", "hồ", "sông", "núi",
    "tỉnh", "quận", "huyện", "phường", "xã",
    "thị", "thành phố",
}
_ORGANIZATION_CUES = {
    "công an", "ủy ban", "tòa án", "viện kiểm sát",
    "công ty", "ngân hàng", "chi nhánh", "bộ", "sở",
    "cục", "trường", "đội", "tổng cục",
}
_PERSON_TITLES = {
    "ông", "bà", "anh", "chị", "cô", "chú", "bác",
    "em", "nghi phạm", "bị can", "nạn nhân",
}
_STOP_WORDS = {
    "đang", "đã", "sẽ", "và", "nhưng", "thì", "là",
    "có", "được", "trong", "khi", "cho", "theo",
    "đến", "để", "về", "nên", "vẫn", "còn", "bị",
    "từ", "với", "làm", "nói", "gặp", "ban hành",
}


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("_", " ")).casefold()


def _tokens(value: str) -> list[tuple[str, int, int]]:
    return [
        (match.group(), match.start(), match.end())
        for match in _TOKEN.finditer(value)
    ]


def _phrase_matches(
    normalized_sentence: list[str], phrase: str
) -> list[tuple[int, int]]:
    phrase_tokens = [
        _normalize(token) for token, _, _ in _tokens(phrase)
    ]
    if not phrase_tokens:
        return []

    size = len(phrase_tokens)
    return [
        (index, index + size)
        for index in range(len(normalized_sentence) - size + 1)
        if normalized_sentence[index:index + size] == phrase_tokens
    ]


def _is_capitalized(token: str) -> bool:
    return bool(_CAPITALIZED.match(token))


def _consume_name(
    tokens: list[tuple[str, int, int]], index: int
) -> int:
    """Consume a proper-name sequence, including abbreviations such as TP.HCM."""
    stop = index

    stop_words = {
        "đang", "đã", "sẽ", "vừa", "được", "bị",
        "là", "cho", "theo", "sau", "khi", "và",
        "nhưng", "để", "từ", "với"
    }

    while stop < len(tokens):
        value = tokens[stop][0]

        if value.casefold() in stop_words:
            break

        if _is_capitalized(value):
            stop += 1
            continue

        if (
            value == "."
            and stop + 1 < len(tokens)
            and _is_capitalized(tokens[stop + 1][0])
        ):
            stop += 1
            continue

        break

    return stop


def _consume_contextual_location(
    tokens: list[tuple[str, int, int]],
    normalized: list[str],
    index: int,
) -> int:
    """
    Consume locations after a location designator.
    Also supports synthetic examples such as 'Quận mô phỏng 001'.
    """
    if index >= len(tokens):
        return index

    first = normalized[index]

    if first == "mô" and index + 1 < len(tokens):
        if normalized[index + 1] == "phỏng":
            stop = index + 2
            if stop < len(tokens) and tokens[stop][0].isdigit():
                return stop + 1
            return stop

    stop = _consume_name(tokens, index)

    # Keep the designator alone only if no name follows.
    if stop == index:
        return index

    return stop


class RuleBasedNER:
    """Transparent keyword/cue baseline; rules do not learn from test data."""

    def __init__(self, rules_path: Path = RULES_PATH):
        self.keywords: dict[str, list[str]] = {
            entity: [] for entity in ENTITY_TYPES
        }

        if rules_path.is_file():
            try:
                payload = json.loads(
                    rules_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError) as exc:
                raise NERPipelineError(
                    f"Không đọc được file rule {rules_path}: {exc}"
                ) from exc

            if not isinstance(payload, dict):
                raise NERPipelineError(
                    "ner_rules.json phải là JSON object."
                )

            for entity, values in payload.items():
                if (
                    entity not in ENTITY_TYPES
                    or not isinstance(values, list)
                    or any(
                        not isinstance(value, str) or not value.strip()
                        for value in values
                    )
                ):
                    raise NERPipelineError(
                        "ner_rules.json chỉ nhận PERSON, ORGANIZATION, "
                        "LOCATION với danh sách keyword dạng chuỗi."
                    )

                self.keywords[entity] = values

    def predict(self, sentence: str) -> list[dict[str, str | int]]:
        tokens = _tokens(sentence)
        if not tokens:
            return []

        normalized = [_normalize(token) for token, _, _ in tokens]
        # Candidate key: (start, end); value: (label, priority).
        # Longer exact dictionary matches have the highest priority.
        candidates: dict[
            tuple[int, int], tuple[str, int]
        ] = {}

        def add(start_i: int, end_i: int, label: str, priority: int) -> None:
            if start_i >= end_i or start_i < 0 or end_i > len(tokens):
                return

            start = tokens[start_i][1]
            end = tokens[end_i - 1][2]
            key = (start, end)
            old = candidates.get(key)

            if old is None or priority > old[1]:
                candidates[key] = (label, priority)

        # 1. Exact dictionary matches.
        for entity_type, phrases in self.keywords.items():
            for phrase in phrases:
                for start_i, end_i in _phrase_matches(normalized, phrase):
                    add(start_i, end_i, entity_type, 100)

    
        # 1b. Hospital names are organizations.
        for cue in ("b?nh vi?n",):
            for start_i, end_i in _phrase_matches(normalized, cue):
                stop = _consume_name(tokens, end_i)
                add(start_i, max(end_i, stop), "ORGANIZATION", 115)

        # 2. Explicit organization cue phrases and their following names.
        for cue in _ORGANIZATION_CUES:
            for start_i, end_i in _phrase_matches(normalized, cue):
                stop = end_i

                # Expand: "Công an tỉnh Thanh Hóa", "UBND tỉnh Bắc Ninh".
                if stop < len(tokens) and normalized[stop] in {
                    "tỉnh", "quận", "huyện"
                }:
                    stop += 1
                    stop = _consume_name(tokens, stop)

                # Expand: "Công an thành phố Hồ Chí Minh".
                elif (
                    stop + 1 < len(tokens)
                    and normalized[stop] == "thành"
                    and normalized[stop + 1] == "phố"
                ):
                    stop += 2
                    stop = _consume_name(tokens, stop)

                else:
                    stop = _consume_name(tokens, end_i)

                add(start_i, max(end_i, stop), "ORGANIZATION", 110)


        # 3. Expand organization candidates through location designators.
        # Example: UBND tỉnh Bắc Ninh.
        for (start, end), (label, priority) in list(candidates.items()):
            if label != "ORGANIZATION":
                continue

            start_i = next(
                (i for i, item in enumerate(tokens) if item[1] == start),
                None,
            )
            end_i = next(
                (i + 1 for i, item in enumerate(tokens) if item[2] == end),
                None,
            )
            if start_i is None or end_i is None:
                continue

            if end_i < len(tokens) and normalized[end_i] in {
                "tỉnh", "quận", "huyện"
            }:
                stop = _consume_name(tokens, end_i + 1)
                if stop > end_i + 1:
                    add(start_i, stop, "ORGANIZATION", 90)

        # 4. Locations following an explicit location preposition.
        for cue in _LOCATION_PREPOSITIONS:
            for cue_start, cue_end in _phrase_matches(normalized, cue):
                if cue_end >= len(tokens):
                    continue

                name_start = cue_end
                name_end = _consume_name(tokens, name_start)

                if name_end > name_start:
                    add(name_start, name_end, "LOCATION", 50)

                # Also allow lower-case synthetic place names after a
                # location designator, e.g. "ở Quận mô phỏng 001".
                for designator in _LOCATION_DESIGNATORS:
                    size = len(designator)
                    if tuple(normalized[name_start:name_start + size]) == designator:
                        stop = _consume_contextual_location(
                            tokens, normalized, name_start + size
                        )
                        if stop > name_start:
                            add(name_start, stop, "LOCATION", 65)
                        break

        # 5. Locations introduced by a designator.
        for designator in _LOCATION_DESIGNATORS:
            size = len(designator)

            for start_i in range(len(tokens) - size + 1):
                if tuple(normalized[start_i:start_i + size]) != designator:
                    continue

                name_start = start_i + size
                name_end = _consume_contextual_location(
                    tokens, normalized, name_start
                )
                if name_end > start_i:
                    add(start_i, name_end, "LOCATION", 60)

        # 6. Street, lake, river and similar location contexts.
        for index, word in enumerate(normalized):
            if word not in {"đường", "phố", "hồ", "sông", "núi"}:
                continue

            stop = _consume_name(tokens, index + 1)
            if stop > index + 1:
                add(index, stop, "LOCATION", 75)

        # 7. Person names following titles, including initials like "ông B."
        for index, word in enumerate(normalized):
            if word not in _PERSON_TITLES:
                continue

            name_start = index + 1
            if name_start >= len(tokens):
                continue

            token = tokens[name_start][0]

            if not _is_capitalized(token):
                continue

            name_end = _consume_name(tokens, name_start)

            # Include initials with trailing period in the returned span
            # only when the annotation itself includes that period.
            if (
                name_end + 1 < len(tokens)
                and tokens[name_end][0] == "."
            ):
                name_end += 1

            add(name_start, name_end, "PERSON", 80)

        # 8. Generic multi-token person candidates.
        for index, token in enumerate(tokens):
            if not _is_capitalized(token[0]):
                continue

            # Avoid interpreting a title or location designator as a person.
            if index > 0 and normalized[index - 1] in {
                "đường", "phố", "hồ", "sông", "núi",
                "tỉnh", "quận", "huyện", "phường", "xã",
            }:
                continue

            if normalized[index] in {
                "b?nh", "vi?n", "t?a", "?n", "c?ng", "an",
                "c?", "quan", "l?c", "l??ng", "nh?n", "d?n",
            }:
                continue

            stop = _consume_name(tokens, index)
            capitalized_count = sum(
                1 for item, _, _ in tokens[index:stop]
                if _is_capitalized(item)
            )

            if capitalized_count < 2:
                continue

            add(index, stop, "PERSON", 30)

        # 9. Prefer higher-priority candidates and longer spans.
        ordered = sorted(
            (
                (start, end, label, priority)
                for (start, end), (label, priority) in candidates.items()
            ),
            key=lambda item: (
                -item[3],
                -(item[1] - item[0]),
                item[0],
            ),
        )

        selected: list[tuple[int, int, str]] = []
        for start, end, label, _priority in ordered:
            if any(
                start < prior_end and end > prior_start
                for prior_start, prior_end, _ in selected
            ):
                continue
            selected.append((start, end, label))

        return [
            {
                "text": sentence[start:end],
                "label": label,
                "start": start,
                "end": end,
            }
            for start, end, label in sorted(selected)
        ]