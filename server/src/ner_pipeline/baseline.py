import json
import re
import unicodedata
from pathlib import Path

from .errors import NERPipelineError
from .paths import RULES_PATH
from .schema import ENTITY_TYPES
from .schema import LABEL_ALIASES


_TOKEN = re.compile(r"(?:[^\W_]|[\u0300-\u036f])+|[^\w\s]", flags=re.UNICODE)

# Normalize spelling variants during matching while preserving offsets in the source sentence.
_SPELLING_VARIANTS = {
    "tuý": "túy",
    "uỷ": "ủy",
}

_CAPITALIZED_REST = re.compile(r"^[\w.-]*$", flags=re.UNICODE)

_DAY_PART = r"(?:sáng|trưa|chiều|tối|đêm|khuya|sớm|rạng\s+sáng)"
_WEEKDAY = r"(?:thứ\s+(?:hai|ba|tư|năm|sáu|bảy)|chủ\s+nhật)"

# Simple time patterns (priority 100).
_DATE_TIME = re.compile(
    r"\b(?:"
    rf"(?:{_DAY_PART}\s+(?:ngày\s+)?)?\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}"
    rf"|(?:{_DAY_PART}\s+(?:ngày\s+)?|ngày\s+)\d{{1,2}}[/-]\d{{1,2}}(?![\d/])"
    r"|\d{1,2}\s+tháng\s+\d{1,2}(?:\s+năm\s+\d{4})?"
    r"|\d{1,2}\s+giờ(?:\s+\d{1,2}\s+phút)?"
    rf"|(?:(?:khoảng|hơn|gần|lúc|đến)\s+)?\d{{1,2}}h(?:\d{{2}})?(?:\s+{_WEEKDAY})?"
    rf"|{_WEEKDAY}"
    r"|(?:19|20)\d{2})\b",
    flags=re.IGNORECASE,
)

# Composite patterns have higher priority so they are not split into isolated years.
_TIME_COMPOSITE = (
    (re.compile(r"\b(?:đầu|giữa|cuối)\s+năm\s+(?:19|20)\d{2}\b", re.IGNORECASE), 115),
    (re.compile(r"\b(?:đầu|giữa|cuối)\s+tháng\s+\d{1,2}[/-]\d{4}\b", re.IGNORECASE), 115),
    (re.compile(r"\b\d{1,2}h(?:\d{2})?\s+ngày\s+\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b", re.IGNORECASE), 115),
    (re.compile(r"\b(?:mùng|mồng)\s+\d{1,2}\s+tết\b", re.IGNORECASE), 110),
    (re.compile(r"\btháng\s+\d{1,2}[/-]\d{4}\b", re.IGNORECASE), 105),
    (re.compile(r"\btháng\s+\d{1,2}\s+năm\s+\d{4}\b", re.IGNORECASE), 105),
)

_MONEY = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*"
    r"(?:triệu|tỷ|nghìn|ngàn)?\s*"
    r"(?:đồng|VNĐ|VND|USD|đô la)\b",
    flags=re.IGNORECASE,
)

_DRUG_TERMS = (
    "ma túy", "ma tuý", "ma túy đá", "ma tuý đá", "hồng phiến",
    "heroin", "cocaine", "methamphetamine",
    "meth", "ketamine", "cần sa", "thuốc lắc",
)

# PRODUCT: concrete objects in crime contexts (gold labels include guns, knives, bullets, etc.).
# Generic terms such as motorcycle, car, and phone are excluded because gold annotations
# did not label them in reviewed sentences; recognize them only with a brand or proper name.
_PRODUCT_TERMS = (
    "iPhone", "điện thoại iPhone",
    "súng", "súng ngắn", "súng trường", "súng hơi", "khẩu súng",
    "dao", "kiếm", "gậy", "mã tấu",
    "lựu đạn", "hung khí",
)

# Words before product nouns that are not part of the product name (numbers and classifiers).
_PRODUCT_LEADING_NOISE = {
    "một", "các", "những", "hai", "ba", "bốn", "năm", "sáu", "bảy",
    "tám", "chín", "mười", "chiếc", "cái", "con", "khẩu", "quả", "cây",
}

# Words that overlap with weapon keywords but are usually not entities (e.g. "fluctuate").
_PRODUCT_NEGATIVE_NEXT = {
    "dao": {"động"},
}

# Head terms for products named by brand, e.g. "scooter, Ari Blade brand".
_PRODUCT_BRAND_HEADS = ("tay ga", "xe ga", "xe số", "xe tay ga", "điện thoại")

_CRIME_TERMS = (
    "trộm cắp tài sản", "cướp tài sản", "lừa đảo chiếm đoạt tài sản",
    "giết người", "đánh bạc", "cố ý gây thương tích",
    "tàng trữ trái phép chất ma túy",
)

# Agency or organization phrases that can stand alone (must still be capitalized initially).
_ORG_STANDALONE = (
    "quốc hội", "chính phủ", "đảng",
)

# Agency or organization phrases: create an entity only when followed by a proper name.
_ORG_CUES = (
    "ủy ban", "uỷ ban", "tòa án", "viện kiểm sát", "công ty", "ngân hàng",
    "chi nhánh", "bộ", "sở", "cục", "đội", "tổng cục", "bệnh viện", "công an",
    "thanh tra", "hội đồng nhân dân", "phòng", "hội",
    "trung tâm", "tập đoàn", "tổng công ty", "hợp tác xã",
    "trường đại học", "đại học", "viện",
    "tand", "vksnd", "cand", "ubnd", "ca", "cơ quan csđt",
)

# Lowercase phrases that occur within organization names; recognize them as a unit.
_ORG_UNITS = (
    ("sử", "dụng", "công", "nghệ", "cao"),
    ("thông", "vận", "tải"),
    ("nhân", "dân"),
    ("kiểm", "sát"),
    ("đa", "khoa"),
    ("nội", "bộ"),
    ("tối", "cao"),
    ("thương", "mại", "và", "dịch", "vụ"),
    ("dịch", "vụ"),
    ("nông", "nghiệp"),
    ("tài", "nguyên", "và", "môi", "trường"),
    ("kinh", "tế"),
    ("nhà", "báo"),
    ("chính", "trị"),
)

# Numeric prefixes: following numbers belong to the name ("District 10", "D.2", "No. 1").
_ORG_NUMBER_PREFIX = {"quận", "phường", "huyện", "xã", "thị", "tỉnh", "số", "khu", "thôn", "ấp"}

# Words that are never part of an organization name (grammatical words, verbs, prepositions).
_ORG_BLOCK = {
    "của", "về", "tại", "ở", "do", "bị", "cho", "đã", "đang", "sẽ",
    "được", "với", "theo", "trong", "là", "có", "từ", "đến", "để",
    "khi", "nên", "vì", "sau", "trước", "khoảng", "hoặc",
}

# Words commonly found in organization names; accept only after a capitalized or name word.
_ORG_NAME_WORDS = {
    "thông", "vận", "tải", "nông", "nghiệp", "kinh", "tế", "trị", "nội", "nhân", "dân",
    "tối", "cao", "đa", "khoa", "nhà", "nước", "văn", "hóa", "thể", "thao", "du", "lịch",
    "giao", "xây", "dựng", "kiểm", "sát", "ninh", "truyền", "hình", "sự", "nguyên",
    "môi", "trường", "và", "ốc", "thương", "mại", "dịch", "vụ", "tài", "lao", "động", "binh",
    "xã", "hội", "tư", "pháp", "chính", "phủ", "điện", "lực", "cổ", "phần", "trách",
    "nhiệm", "hữu", "hạn", "khẩu", "nhập", "sản", "xuất", "kỹ", "thuật", "công", "ty",
    "mạng", "phòng", "chống", "tội", "phạm", "nghệ", "bộ", "thành", "phố", "tỉnh", "số",
    "quận", "huyện", "phường", "thị", "trấn", "y", "tế", "giáo", "dục", "đào", "tạo",
    "đầu", "tư", "hạt", "kiểm", "lâm",
}

# Words allowed after a comma in a name (e.g. "department of, crime prevention").
_ORG_COMMA_WORDS = {"phòng", "chống", "tội", "phạm", "công", "nghệ", "cao"}

# Words allowed immediately after an agency phrase (e.g. mixed-case official names).
_ORG_NAME_AFTER_CUE = {
    "nhân", "dân", "tối", "cao", "đa", "khoa", "kiểm", "sát", "nội", "bộ", "tư", "pháp",
    "tỉnh", "huyện", "quận", "thành", "phố", "thị", "xã", "phường", "trấn", "nghiệp",
    "dịch", "vụ", "kỹ", "thuật", "nông", "y", "tế", "khu",
}

_LOC_DESIGNATORS = (
    ("thành", "phố"),
    ("thị", "xã"),
    ("thị", "trấn"),
    ("tỉnh",),
    ("quận",),
    ("huyện",),
    ("phường",),
    ("xã",),
    ("tp",),
    ("đường",),
    ("thôn",),
    ("ấp",),
)

_LOC_DESIGNATOR_WORDS = {"tp", "tỉnh", "thành", "thị", "quận", "huyện", "phường", "xã", "đường", "thôn", "ấp"}

_LOC_PREPOSITIONS = ("ở", "tại", "thuộc")

# Common province, city, and country names from general geographic knowledge, not test data.
_LOC_GAZETTEER = (
    "Việt Nam", "Trung Quốc", "Campuchia", "Lào", "Thái Lan", "Hàn Quốc",
    "Nhật Bản", "Hoa Kỳ", "Đài Loan",
    "Hà Nội", "Hải Phòng", "Đà Nẵng", "Cần Thơ", "Sài Gòn", "Hồ Chí Minh",
    "An Giang", "Bắc Giang", "Bắc Kạn", "Bạc Liêu", "Bắc Ninh", "Bến Tre",
    "Bình Định", "Bình Dương", "Bình Phước", "Bình Thuận", "Cà Mau", "Cao Bằng",
    "Đắk Lắk", "Đắk Nông", "Điện Biên", "Đồng Nai", "Đồng Tháp", "Gia Lai",
    "Hà Giang", "Hà Nam", "Hà Tĩnh", "Hải Dương", "Hậu Giang", "Hòa Bình",
    "Hưng Yên", "Khánh Hòa", "Kiên Giang", "Kon Tum", "Lai Châu", "Lâm Đồng",
    "Lạng Sơn", "Lào Cai", "Long An", "Nam Định", "Nghệ An", "Ninh Bình",
    "Ninh Thuận", "Phú Thọ", "Phú Yên", "Quảng Bình", "Quảng Nam", "Quảng Ngãi",
    "Quảng Ninh", "Quảng Trị", "Sóc Trăng", "Sơn La", "Tây Ninh", "Thái Bình",
    "Thái Nguyên", "Thanh Hóa", "Thừa Thiên Huế", "Tiền Giang", "Trà Vinh",
    "Tuyên Quang", "Vĩnh Long", "Vĩnh Phúc", "Yên Bái",
)

_PERSON_TITLES = (
    "ông", "bà", "anh", "chị", "cô", "chú",
    "bác", "em", "nghi phạm", "bị can", "nạn nhân",
)

# Role phrases before a person's name are outside the span (e.g. "suspect Hung", "victim Lan").
_PERSON_ROLE_PHRASES = (
    "đối tượng", "bị can", "bị hại", "nghi phạm", "nạn nhân", "tên", "hung thủ",
    "chồng", "vợ", "cháu", "cha", "mẹ",
)

# Titles or roles before an agency or person's name are outside the span.
_ROLE_WORDS = {"chánh", "phó", "trưởng", "giám", "đốc", "cấp"}

_STOP_WORDS = {
    "tại", "ngày", "tối", "sáng", "chiều", "hiện", "nếu", "vào", "theo",
    "đang", "đã", "sẽ", "và", "nhưng", "thì", "là",
    "có", "được", "trong", "khi", "cho", "theo",
    "đến", "để", "về", "nên", "vẫn", "còn", "bị",
    "từ", "với", "làm", "nói", "gặp", "ban hành",
    "vì", "sau", "trước", "khoảng", "trong đó",
}

# Common Vietnamese surnames, used to reduce false positives for names without titles.
_VI_SURNAMES = {
    "nguyễn", "trần", "lê", "phạm", "hoàng", "huỳnh", "phan", "vũ", "võ",
    "đặng", "bùi", "đỗ", "hồ", "ngô", "dương", "lý", "đinh", "đào", "đoàn",
    "mai", "tạ", "trịnh", "cao", "châu", "lâm", "lương", "tô", "thái",
    "đàm", "tăng", "vương", "đường", "quách", "kiều", "mạc",
    "đồng", "lường", "trương", "phùng", "triệu", "lục", "vi", "sầm",
    "chu", "âu", "thạch", "lưu", "bế", "hứa", "diệp", "giang",
}

_NAME_BLOCKLIST = {
    "vụ", "án", "giai", "đoạn", "thời", "kỳ",
    "chánh", "phó", "trưởng", "giám", "đốc",
}

_SN_PREFIX = re.compile(r"(?:sinh|SN)\s*$", flags=re.IGNORECASE)

YEAR_RANGE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:(?:năm)\s+)?"
    r"(?:19\d{2}|20\d{2})"
    r"\s*(?:-|–|—|đến|tới)\s*"
    r"(?:19\d{2}|20\d{2})"
    r"(?!\d)",
    re.IGNORECASE
)


def find_year_ranges(text):
    return [
        {
            "text": match.group(0),
            "start": match.start(),
            "end": match.end(),
            "label": "TIME",
        }
        for match in YEAR_RANGE_PATTERN.finditer(text)
    ]


def _normalize(value: str) -> str:
    value = value.replace("Ð", "Đ").replace("ð", "đ")
    value = unicodedata.normalize("NFC", value).casefold()
    return _SPELLING_VARIANTS.get(value, value)


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
    # Unicode range À-Ỹ includes lowercase accented letters too, so use isupper() to test case.
    value = unicodedata.normalize("NFC", token)
    return bool(value) and value[0].isupper() and bool(_CAPITALIZED_REST.match(value))


def _is_digit(token: str) -> bool:
    return token.isdigit()


def _is_name_token(token: str) -> bool:
    return _is_capitalized(token) or _is_digit(token)


def _cue_token_lists() -> list[list[str]]:
    # "CA" (abbreviation for police) is a cue only when capitalized; do not block names like "Mr. Ca".
    phrases = [c for c in _ORG_CUES if c != "ca"] + list(_ORG_STANDALONE) + [" ".join(d) for d in _LOC_DESIGNATORS]
    return [[_normalize(t) for t, _, _ in _tokens(p)] for p in phrases]


def _span_has_cue(normalized, start, end, cue_lists) -> bool:
    """Return whether an agency/administrative cue overlaps the [start, end) span."""
    for cue in cue_lists:
        size = len(cue)
        for i in range(max(0, start - size + 1), min(end, len(normalized) - size + 1)):
            if normalized[i:i + size] == cue:
                return True
    return False


def _consume_capitalized(
    tokens: list[tuple[str, int, int]],
    normalized: list[str],
    index: int,
    max_tokens: int,
) -> int:
    """Consume a capitalized sequence (person or place name). Include periods only when a name follows."""
    stop = index
    while stop < len(tokens) and stop - index < max_tokens:
        value = tokens[stop][0]
        if normalized[stop] in _STOP_WORDS:
            break
        if _is_capitalized(value):
            stop += 1
            continue
        if (
            value == "."
            and stop + 1 < len(tokens)
            and _is_capitalized(tokens[stop + 1][0])
            and normalized[stop + 1] not in _STOP_WORDS
        ):
            stop += 1
            continue
        break
    return stop


def _consume_place(
    tokens: list[tuple[str, int, int]],
    normalized: list[str],
    index: int,
    max_tokens: int = 6,
) -> int:
    """Consume a place name: capitalized words, numbers, and hyphens within the name."""
    stop = index
    while stop < len(tokens) and stop - index < max_tokens:
        value = tokens[stop][0]
        if normalized[stop] in _STOP_WORDS:
            break
        if _is_name_token(value):
            stop += 1
            continue
        if (
            value in {".", "-"}
            and stop + 1 < len(tokens)
            and _is_name_token(tokens[stop + 1][0])
            and normalized[stop + 1] not in _STOP_WORDS
        ):
            stop += 1
            continue
        break
    return stop


# Lowercase words that commonly end organization names ("Supreme", "crime", "internal").
_ORG_NAME_FINAL = {
    "cao", "bộ", "khoa", "dựng", "tế", "thuật", "pháp", "mại", "vụ", "trị",
    "nội", "hạn", "phần", "nghiệp", "mạng", "phạm",
}


def _org_cue_heads() -> set:
    return {
        _normalize(_tokens(cue)[0][0])
        for cue in (*_ORG_CUES, *_ORG_STANDALONE)
        if _tokens(cue)
    }


_ORG_CUE_HEADS = None


def _lowercase_continues_name(tokens, normalized, index) -> bool:
    """Accept a lowercase name token only when the next token continues the name or ends the phrase.

    Avoid consuming reporting terms such as "thông báo", "công bố", or "thông tin".
    """
    if normalized[index] in _ORG_NAME_FINAL:
        return True
    if index + 1 >= len(tokens):
        return True
    nxt, nxt_norm = tokens[index + 1][0], normalized[index + 1]
    if not any(ch.isalnum() for ch in nxt):
        return True
    return _is_name_token(nxt) or nxt_norm in _ORG_NAME_WORDS


def _consume_org(
    tokens: list[tuple[str, int, int]],
    normalized: list[str],
    index: int,
    max_tokens: int = 14,
) -> int:
    """Consume the organization name following an organization cue.

    - Capitalized words, numbers, ampersands, and abbreviations are part of the name.
    - Accept lowercase words only in known phrases (_ORG_UNITS), or when the word is part
      of the name and the next token continues it (see _lowercase_continues_name).
    - After "Công an", continue only with a proper name or a word in _ORG_NAME_AFTER_CUE.
    - Continue across "và" only when it does not begin a new agency name.
    """
    global _ORG_CUE_HEADS
    if _ORG_CUE_HEADS is None:
        _ORG_CUE_HEADS = _org_cue_heads()

    stop = index
    prev_name = False
    after_cong_an = False
    while stop < len(tokens) and stop - index < max_tokens:
        value = tokens[stop][0]
        norm = normalized[stop]

        # Fixed lowercase phrases (e.g. "general hospital", "internal").
        if prev_name and not after_cong_an:
            unit = next(
                (u for u in _ORG_UNITS if tuple(normalized[stop:stop + len(u)]) == u),
                None,
            )
            if unit is not None:
                stop += len(unit)
                prev_name = True
                continue

        if norm in _ORG_BLOCK:
            break
        if _is_name_token(value) or value == "&":
            stop += 1
            prev_name = True
            continue
        if (
            value in {".", "-"}
            and stop + 1 < len(tokens)
            and _is_name_token(tokens[stop + 1][0])
            and normalized[stop + 1] not in _ORG_BLOCK
            and normalized[stop + 1] not in _STOP_WORDS
        ):
            stop += 1
            continue
        if value == "," and prev_name and stop + 1 < len(tokens) and normalized[stop + 1] in _ORG_COMMA_WORDS:
            stop += 1
            continue
        if norm == "và":
            # "and" joins parts of a name but does not join a separate agency.
            starts_new_org = (
                stop + 1 < len(tokens)
                and normalized[stop + 1] in _ORG_CUE_HEADS
                and _is_capitalized(tokens[stop + 1][0])
            )
            if prev_name and stop + 1 < len(tokens) and not starts_new_org:
                stop += 1
                continue
            break
        if norm == "an" and stop > index and normalized[stop - 1] == "công" and not after_cong_an:
            stop += 1
            prev_name = True
            after_cong_an = True
            continue
        if after_cong_an:
            if norm in _ORG_NAME_AFTER_CUE:
                stop += 1
                prev_name = True
                continue
            break
        if stop == index and norm in _ORG_NAME_AFTER_CUE:
            stop += 1
            prev_name = True
            continue
        if norm == "báo" and stop > index and normalized[stop - 1] == "nhà":
            stop += 1
            prev_name = True
            continue
        if prev_name and norm in _ORG_NAME_WORDS and _lowercase_continues_name(tokens, normalized, stop):
            stop += 1
            continue
        break

    # Trim trailing words that cannot end a name, hyphens, and numbers not part of the name.
    while stop > index:
        last = tokens[stop - 1][0]
        if _is_digit(last):
            if stop - 2 >= index and (
                normalized[stop - 2] in _ORG_NUMBER_PREFIX or tokens[stop - 2][0] == "."
            ):
                break
            stop -= 1
            continue
        if last in {".", "-"}:
            stop -= 1
            continue
        if normalized[stop - 1] in _ORG_DANGLING and not _is_capitalized(last):
            stop -= 1
            continue
        break
    return stop


# Words that cannot end an organization name; trim them when they appear at the end.
_ORG_DANGLING = {
    "tỉnh", "quận", "huyện", "phường", "xã", "thành", "phố", "thị",
    "đa", "khoa", "nhập", "khẩu", "cổ", "phần", "trách", "nhiệm",
    "hữu", "hạn", "thương", "mại", "kỹ", "thuật",
    "tư", "pháp", "lao", "động", "tài", "chính", "kế", "hoạch",
    "đầu", "giáo", "dục", "đào", "tạo", "y", "tế", "hội",
}


class RuleBasedNER:
    """Rule-based baseline with the team's canonical NER labels."""

    def __init__(self, rules_path: Path = RULES_PATH):
        self.keywords: dict[str, list[str]] = {
            entity: [] for entity in ENTITY_TYPES
        }
        self.last_candidates: list[dict] = []

        if not rules_path.is_file():
            return

        try:
            payload = json.loads(
                rules_path.read_text(encoding="utf-8-sig")
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
            key = entity.strip().upper()
            label = LABEL_ALIASES.get(key, key)

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
        # Normalize to NFC as in phobert.predict_sentence; offsets refer to the NFC string.
        sentence = unicodedata.normalize("NFC", sentence)
        tokens = _tokens(sentence)

        if not tokens:
            self.last_candidates = []
            return []

        normalized = [_normalize(token) for token, _, _ in tokens]
        cue_lists = _cue_token_lists()
        start_to_token = {start: i for i, (_, start, _) in enumerate(tokens)}
        end_to_token = {end: i + 1 for i, (_, _, end) in enumerate(tokens)}

        candidates: dict[tuple[int, int], tuple[str, int, str]] = {}

        def add(start_i, end_i, label, priority, rule):
            if start_i is None or end_i is None:
                return
            if start_i < 0 or start_i >= end_i or end_i > len(tokens):
                return
            if label not in ENTITY_TYPES:
                return
            key = (tokens[start_i][1], tokens[end_i - 1][2])
            old = candidates.get(key)
            if old is None or priority > old[1]:
                candidates[key] = (label, priority, rule)

        def phrase_priority(base, start_i, end_i):
            # Prefer longer phrases within the same group.
            return base + (end_i - start_i)

        # 1. Dictionary (from the rules file and built-in defaults).
        for label, phrases in self.keywords.items():
            for phrase in phrases:
                for start_i, end_i in _phrase_matches(normalized, phrase):
                    add(start_i, end_i, label,
                        phrase_priority(120, start_i, end_i), "dict")

        # 2. Organizations: agency phrase plus the following name.
        # Lowercase phrases (such as "police" in ordinary text) apply only when followed by a capitalized name.
        def cue_is_valid(start_i, end_i):
            first_cap = _is_capitalized(tokens[start_i][0])
            next_ok = end_i < len(tokens) and (
                _is_name_token(tokens[end_i][0]) or normalized[end_i] in _ORG_NAME_AFTER_CUE
            )
            return first_cap or next_ok

        for cue in _ORG_STANDALONE:
            for start_i, end_i in _phrase_matches(normalized, cue):
                if not cue_is_valid(start_i, end_i):
                    continue
                stop = _consume_org(tokens, normalized, end_i)
                add(start_i, max(end_i, stop), "ORGANIZATION", 110, "org_standalone")

        for cue in _ORG_CUES:
            for start_i, end_i in _phrase_matches(normalized, cue):
                if start_i > 0 and normalized[start_i - 1] in _ROLE_WORDS:
                    continue
                if cue == "ca" and not tokens[start_i][0].isupper():
                    continue
                if not cue_is_valid(start_i, end_i):
                    continue
                stop = _consume_org(tokens, normalized, end_i)
                if stop > end_i:
                    add(start_i, stop, "ORGANIZATION", 110, "org_cue")

        # 3. Locations after prepositions; exclude phrases beginning with agencies, titles, or unit nouns.
        for cue in _LOC_PREPOSITIONS:
            for _, cue_end in _phrase_matches(normalized, cue):
                if cue_end >= len(tokens):
                    continue
                if not _is_capitalized(tokens[cue_end][0]):
                    continue
                if normalized[cue_end] in _LOC_DESIGNATOR_WORDS or normalized[cue_end] in _ROLE_WORDS:
                    continue
                name_end = _consume_place(tokens, normalized, cue_end, max_tokens=6)
                if name_end > cue_end and not _span_has_cue(normalized, cue_end, name_end, cue_lists):
                    add(cue_end, name_end, "LOCATION", 65, "loc_prep")

        # 3b. Locations after administrative prefixes (province, district, city, street, etc.).
        for designator in _LOC_DESIGNATORS:
            size = len(designator)
            for start_i in range(len(tokens) - size + 1):
                if tuple(normalized[start_i:start_i + size]) != designator:
                    continue
                name_start = start_i + size
                # Remove the period from "TP." before capturing the name.
                if name_start < len(tokens) and tokens[name_start][0] == ".":
                    name_start += 1
                name_end = _consume_place(tokens, normalized, name_start, max_tokens=6)
                if name_end > name_start:
                    add(start_i, name_end, "LOCATION", 80, "loc_designator")

        # 3c. Gazetteer locations; exclude those after "person/people", which indicate nationality.
        for name in _LOC_GAZETTEER:
            for start_i, end_i in _phrase_matches(normalized, name):
                if start_i > 0 and (
                    normalized[start_i - 1] == "người"
                    or normalized[start_i - 1] in _LOC_DESIGNATOR_WORDS
                ):
                    continue
                add(start_i, end_i, "LOCATION", phrase_priority(72, start_i, end_i), "loc_gazetteer")

        # 4. Person names after titles; exclude the title from the span.
        for index, word in enumerate(normalized):
            if word not in _PERSON_TITLES:
                continue
            name_start = index + 1
            if name_start >= len(tokens):
                continue
            if not _is_capitalized(tokens[name_start][0]):
                continue
            name_end = _consume_capitalized(tokens, normalized, name_start, max_tokens=4)
            if name_end > name_start and not _span_has_cue(normalized, name_start, name_end, cue_lists):
                add(name_start, name_end, "PERSON", 85, "person_title")

        # 4b. Person names after role phrases (suspect, victim, named, etc.).
        for role in _PERSON_ROLE_PHRASES:
            for _, role_end in _phrase_matches(normalized, role):
                if role_end >= len(tokens) or not _is_capitalized(tokens[role_end][0]):
                    continue
                name_end = _consume_capitalized(tokens, normalized, role_end, max_tokens=4)
                if name_end > role_end and not _span_has_cue(normalized, role_end, name_end, cue_lists):
                    add(role_end, name_end, "PERSON", 60, "person_role")

        # 5. Untitled person names: 2–4 consecutive capitalized words beginning with a common surname.
        index = 0
        while index < len(tokens):
            if not _is_capitalized(tokens[index][0]) or normalized[index] in _NAME_BLOCKLIST:
                index += 1
                continue
            if index > 0 and normalized[index - 1] in {
                "đường", "phố", "hồ", "sông", "núi",
                "tỉnh", "quận", "huyện", "phường", "xã",
                "bệnh", "viện", "công", "an", "tp",
            }:
                index += 1
                continue
            stop = _consume_capitalized(tokens, normalized, index, max_tokens=4)
            count = stop - index
            if (
                2 <= count <= 4
                and normalized[index] in _VI_SURNAMES
                and not _span_has_cue(normalized, index, stop, cue_lists)
            ):
                add(index, stop, "PERSON", 35, "person_generic")
            index = max(stop, index + 1)

        # 5b. Locations recognized from prefixes above; reserve space for later groups.

        # 6. TIME: composite patterns before simple patterns.
        for pattern, priority in _TIME_COMPOSITE:
            for match in pattern.finditer(sentence):
                add(start_to_token.get(match.start()),
                    end_to_token.get(match.end()),
                    "TIME", priority, "time_composite")

        for match in YEAR_RANGE_PATTERN.finditer(sentence):
            add(start_to_token.get(match.start()),
                end_to_token.get(match.end()),
                "TIME", 110, "year_range")

        for match in _DATE_TIME.finditer(sentence):
            text = match.group(0)
            # Birth years ("born 1999", "year of birth 1999") are not event times.
            if re.fullmatch(r"(?:19|20)\d{2}", text) and _SN_PREFIX.search(sentence[:match.start()]):
                continue
            add(start_to_token.get(match.start()),
                end_to_token.get(match.end()),
                "TIME", 100, "time_basic")

        # 7. MONEY.
        for match in _MONEY.finditer(sentence):
            add(start_to_token.get(match.start()),
                end_to_token.get(match.end()),
                "MONEY", 105, "money")

        # 8. DRUG, PRODUCT, and CRIME from fixed phrases.
        for label, phrases in (
            ("DRUG", _DRUG_TERMS),
            ("PRODUCT", _PRODUCT_TERMS),
            ("CRIME", _CRIME_TERMS),
        ):
            for phrase in phrases:
                for start_i, end_i in _phrase_matches(normalized, phrase):
                    if label == "PRODUCT":
                        if end_i < len(tokens) and normalized[end_i] in _PRODUCT_NEGATIVE_NEXT.get(phrase, set()):
                            continue
                        while start_i < end_i - 1 and normalized[start_i] in _PRODUCT_LEADING_NOISE:
                            start_i += 1
                    add(start_i, end_i, label,
                        phrase_priority(90, start_i, end_i), "phrase")

        # 8b. PRODUCT: "Ari Blade brand scooter" = vehicle type + brand cue + proper name.
        for head in _PRODUCT_BRAND_HEADS:
            head_len = len(_tokens(head))
            for _, head_end in _phrase_matches(normalized, head):
                if head_end < len(tokens) and normalized[head_end] == "hiệu":
                    name_end = _consume_capitalized(tokens, normalized, head_end + 1, max_tokens=4)
                    if name_end > head_end + 1:
                        add(head_end - head_len, name_end, "PRODUCT", 95, "product_brand")

        # Select spans by rule priority; for equal priority, prefer the longer span.
        ordered = sorted(
            (
                (start, end, label, priority, rule)
                for (start, end), (label, priority, rule) in candidates.items()
            ),
            key=lambda item: (-item[3], -(item[1] - item[0]), item[0]),
        )

        selected: list[tuple[int, int, str]] = []
        self.last_candidates = []
        for start, end, label, priority, rule in ordered:
            overlaps = any(
                start < prior_end and end > prior_start
                for prior_start, prior_end, _ in selected
            )
            self.last_candidates.append({
                "text": sentence[start:end],
                "label": label,
                "start": start,
                "end": end,
                "priority": priority,
                "rule": rule,
                "selected": not overlaps,
            })
            if not overlaps:
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