
import json
import re
import unicodedata
from pathlib import Path

from .errors import NERPipelineError
from .paths import RULES_PATH
from .schema import ENTITY_TYPES


_TOKEN = re.compile(r"[^\W_]+|[^\w\s]", flags=re.UNICODE)

_LABEL_ALIASES = {
    "PERSON": "PERSON",
    "ORG": "ORG",
    "ORGANIZATION": "ORG",
    "LOC": "LOC",
    "LOCATION": "LOC",
    "DATE/TIME": "DATE/TIME",
    "MONEY": "MONEY",
    "PRODUCT": "PRODUCT",
    "DRUG": "DRUG",
    "LAW": "LAW",
}

_CAPITALIZED = re.compile(
    r"^[A-ZÀ-ỸĐ][\wÀ-ỹĐđ.-]*$",
    flags=re.UNICODE,
)

_DATE_TIME = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|\d{1,2}\s+tháng\s+\d{1,2}(?:\s+năm\s+\d{4})?"
    r"|\d{1,2}\s+giờ(?:\s+\d{1,2}\s+phút)?"
    r"|\d{1,2}\s+giờ"
    r"|\d{4})\b",
    flags=re.IGNORECASE,
)

_MONEY = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*"
    r"(?:triệu|tỷ|nghìn|ngàn)?\s*"
    r"(?:đồng|VNĐ|VND|USD|đô la)\b",
    flags=re.IGNORECASE,
)

_DRUG_TERMS = (
    "ma túy", "heroin", "cocaine", "methamphetamine",
    "meth", "ketamine", "cần sa", "thuốc lắc",
)

_WEAPON_TERMS = (
    "dao", "súng", "súng ngắn", "súng trường",
    "kiếm", "gậy", "vũ khí",
)

_PRODUCT_TERMS = (
    "điện thoại", "xe máy", "ô tô", "xe hơi",
    "laptop", "máy tính", "iPhone", "xe đạp",
)

_LAW_TERMS = (
    "trộm cắp tài sản", "cướp tài sản", "lừa đảo chiếm đoạt tài sản",
    "giết người", "đánh bạc", "cố ý gây thương tích",
    "tàng trữ trái phép chất ma túy",
)

_ORGANIZATION_CUES = (
    "công an", "ủy ban", "ubnd", "tòa án",
    "viện kiểm sát", "công ty", "ngân hàng",
    "chi nhánh", "bộ", "sở", "cục",
    "trường", "đội", "tổng cục", "bệnh viện",
)

_LOCATION_DESIGNATORS = (
    ("thành", "phố"),
    ("thị", "xã"),
    ("thị", "trấn"),
    ("tỉnh",),
    ("quận",),
    ("huyện",),
    ("phường",),
    ("xã",),
)

_LOCATION_PREPOSITIONS = ("ở", "tại", "thuộc")

_PERSON_TITLES = (
    "ông", "bà", "anh", "chị", "cô", "chú",
    "bác", "em", "nghi phạm", "bị can", "nạn nhân",
)

_STOP_WORDS = {
    "đang", "đã", "sẽ", "và", "nhưng", "thì", "là",
    "có", "được", "trong", "khi", "cho", "theo",
    "đến", "để", "về", "nên", "vẫn", "còn", "bị",
    "từ", "với", "làm", "nói", "gặp", "ban hành",
    "vì", "sau", "trước", "khoảng", "trong đó",
}


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _tokens(value: str) -> list[tuple[str, int, int]]:
    return [
        (match.group(), match.start(), match.end())
        for match in _TOKEN.finditer(value)
    ]


def _phrase_matches(
    normalized_sentence: list[str],
    phrase: str,
) -> list[tuple[int, int]]:
    phrase_tokens = [
        _normalize(token)
        for token, _, _ in _tokens(phrase)
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
    tokens: list[tuple[str, int, int]],
    index: int,
) -> int:
    stop = index

    while stop < len(tokens):
        value = tokens[stop][0]
        normalized = _normalize(value)

        if normalized in _STOP_WORDS:
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


class RuleBasedNER:
    """Rule-based baseline with the team's canonical NER labels."""

    def __init__(self, rules_path: Path = RULES_PATH):
        self.keywords: dict[str, list[str]] = {
            entity: [] for entity in ENTITY_TYPES
        }

        if not rules_path.is_file():
            return

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
            label = _LABEL_ALIASES.get(entity, entity)

            if (
                label not in ENTITY_TYPES
                or not isinstance(values, list)
                or any(
                    not isinstance(value, str) or not value.strip()
                    for value in values
                )
            ):
                raise NERPipelineError(
                    "Nhãn trong ner_rules.json không hợp lệ "
                    "hoặc danh sách keyword không đúng định dạng."
                )

            self.keywords[label].extend(values)

    def predict(self, sentence: str) -> list[dict[str, str | int]]:
        tokens = _tokens(sentence)

        if not tokens:
            return []

        normalized = [
            _normalize(token)
            for token, _, _ in tokens
        ]

        candidates: dict[
            tuple[int, int], tuple[str, int]
        ] = {}

        def add(
            start_i: int,
            end_i: int,
            label: str,
            priority: int,
        ) -> None:
            if (
                start_i < 0
                or start_i >= end_i
                or end_i > len(tokens)
            ):
                return

            if label not in ENTITY_TYPES:
                return

            start = tokens[start_i][1]
            end = tokens[end_i - 1][2]
            key = (start, end)
            old = candidates.get(key)

            if old is None or priority > old[1]:
                candidates[key] = (label, priority)

        # 1. Exact dictionary matches.
        for label, phrases in self.keywords.items():
            for phrase in phrases:
                for start_i, end_i in _phrase_matches(
                    normalized, phrase
                ):
                    add(start_i, end_i, label, 120)

        # 2. Organization cues and following names.
        for cue in _ORGANIZATION_CUES:
            for start_i, end_i in _phrase_matches(
                normalized, cue
            ):
                stop = end_i

                if (
                    stop < len(tokens)
                    and normalized[stop] in {
                        "tỉnh", "quận", "huyện",
                    }
                ):
                    stop = _consume_name(tokens, stop + 1)

                elif (
                    stop + 1 < len(tokens)
                    and normalized[stop:stop + 2]
                    == ["thành", "phố"]
                ):
                    stop = _consume_name(tokens, stop + 2)

                else:
                    stop = _consume_name(tokens, end_i)

                add(start_i, max(end_i, stop), "ORG", 110)

        # 3. Locations after prepositions and designators.
        for cue in _LOCATION_PREPOSITIONS:
            for cue_start, cue_end in _phrase_matches(
                normalized, cue
            ):
                if cue_end >= len(tokens):
                    continue

                name_start = cue_end
                name_end = _consume_name(tokens, name_start)

                if name_end > name_start:
                    add(name_start, name_end, "LOC", 65)

        for designator in _LOCATION_DESIGNATORS:
            size = len(designator)

            for start_i in range(len(tokens) - size + 1):
                if tuple(
                    normalized[start_i:start_i + size]
                ) != designator:
                    continue

                name_start = start_i + size
                name_end = _consume_name(tokens, name_start)

                if name_end > name_start:
                    add(start_i, name_end, "LOC", 70)

        # 4. Person names after titles.
        for index, word in enumerate(normalized):
            if word not in _PERSON_TITLES:
                continue

            name_start = index + 1

            if name_start >= len(tokens):
                continue

            if not _is_capitalized(tokens[name_start][0]):
                continue

            name_end = _consume_name(tokens, name_start)

            if name_end > name_start:
                add(name_start, name_end, "PERSON", 85)

        # 5. Generic multi-token person names.
        for index, token in enumerate(tokens):
            if not _is_capitalized(token[0]):
                continue

            if index > 0 and normalized[index - 1] in {
                "đường", "phố", "hồ", "sông", "núi",
                "tỉnh", "quận", "huyện", "phường", "xã",
                "bệnh", "viện", "công", "an",
            }:
                continue

            stop = _consume_name(tokens, index)

            capitalized_count = sum(
                1
                for item, _, _ in tokens[index:stop]
                if _is_capitalized(item)
            )

            if capitalized_count >= 2:
                add(index, stop, "PERSON", 35)

        # 6. DATE/TIME.
        for match in _DATE_TIME.finditer(sentence):
            start_i = next(
                (
                    i for i, item in enumerate(tokens)
                    if item[1] == match.start()
                ),
                None,
            )
            end_i = next(
                (
                    i + 1 for i, item in enumerate(tokens)
                    if item[2] == match.end()
                ),
                None,
            )

            if start_i is not None and end_i is not None:
                add(start_i, end_i, "DATE/TIME", 100)

        # 7. MONEY.
        for match in _MONEY.finditer(sentence):
            start_i = next(
                (
                    i for i, item in enumerate(tokens)
                    if item[1] == match.start()
                ),
                None,
            )
            end_i = next(
                (
                    i + 1 for i, item in enumerate(tokens)
                    if item[2] == match.end()
                ),
                None,
            )

            if start_i is not None and end_i is not None:
                add(start_i, end_i, "MONEY", 105)

        # 8. DRUG, PRODUCT and LAW keyword phrases.
        for label, phrases in (
            ("DRUG", _DRUG_TERMS),
            ("PRODUCT", _PRODUCT_TERMS),
            ("LAW", _LAW_TERMS),
        ):
            for phrase in phrases:
                for start_i, end_i in _phrase_matches(
                    normalized, phrase
                ):
                    add(start_i, end_i, label, 90)

        # 9. Resolve overlaps: priority first, then longer span.
        ordered = sorted(
            (
                (start, end, label, priority)
                for (start, end), (label, priority)
                in candidates.items()
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
