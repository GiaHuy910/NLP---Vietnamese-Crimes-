import re

# Trigger rule: (keyword, event type[, required terms, context scope]).
# - Required terms must appear for the rule to apply.
# - Scope: "clause" (default) checks the clause after the trigger; "sentence" checks the whole sentence.
# Trigger spans follow the agreed gold convention and do not include the object.

DRUG_OBJECTS = (
    "ma túy", "ma tuý", "heroin", "cocaine", "methamphetamine",
    "ketamine", "cần sa", "thuốc lắc", "hồng phiến",
)
DECEPTION_OBJECTS = ("gian dối", "thông tin giả", "giả mạo")
WEAPON_OBJECTS = ("hung khí", "dao", "súng", "gậy", "vũ khí")
MONEY_OBJECTS = ("tiền", "tài sản")

TRIGGER_RULES = [
    # BAO_LUC
    ("tước đoạt", "BAO_LUC", ("mạng", "tính mạng")),
    ("tước đi", "BAO_LUC", ("mạng", "tính mạng")),
    ("ném", "BAO_LUC", ("lựu đạn",)),
    ("giết hại", "BAO_LUC"),
    ("hiếp dâm", "BAO_LUC"),
    ("bắt cóc", "BAO_LUC"),
    ("hành hung", "BAO_LUC"),
    ("đâm", "BAO_LUC"),
    ("chém", "BAO_LUC"),
    ("đánh", "BAO_LUC"),
    ("bắn", "BAO_LUC"),
    ("giết", "BAO_LUC"),
    ("xô xát", "BAO_LUC", WEAPON_OBJECTS, "sentence"),
    ("chống trả", "BAO_LUC", WEAPON_OBJECTS, "sentence"),

    # BAT_GIU
    ("khống chế bắt giữ", "BAT_GIU"),
    ("truy bắt", "BAT_GIU", ("thành công",)),
    ("bắt tạm giam", "BAT_GIU"),
    ("bắt quả tang", "BAT_GIU"),
    ("bắt giữ", "BAT_GIU"),
    ("bắt giam", "BAT_GIU"),
    ("tạm giữ", "BAT_GIU"),
    ("bắt", "BAT_GIU", ("đối tượng",)),

    # CUOP_TROM
    ("trộm cắp", "CUOP_TROM"),
    ("đột nhập", "CUOP_TROM"),
    ("cướp", "CUOP_TROM"),

    # LUA_DAO
    ("lừa đảo chiếm đoạt", "LUA_DAO"),
    ("lừa đảo", "LUA_DAO"),
    ("lừa", "LUA_DAO", MONEY_OBJECTS),
    ("giả giọng", "LUA_DAO"),
    ("tự xưng", "LUA_DAO"),
    ("nhắn tin", "LUA_DAO", ("tiền",)),
    ("đưa ra", "LUA_DAO", DECEPTION_OBJECTS),

    # MA_TUY: generic verbs count only when a drug is mentioned in the sentence.
    ("mua bán", "MA_TUY", DRUG_OBJECTS, "sentence"),
    ("vận chuyển", "MA_TUY", DRUG_OBJECTS, "sentence"),
    ("sản xuất", "MA_TUY", DRUG_OBJECTS, "sentence"),
    ("buôn", "MA_TUY", DRUG_OBJECTS, "sentence"),
    ("mua", "MA_TUY", DRUG_OBJECTS, "sentence", "clause"),
    ("bán sỉ", "MA_TUY", DRUG_OBJECTS, "sentence"),
    # Drug possession is labeled MA_TUY in gold; weapon possession is not this trigger.
    ("tàng trữ", "MA_TUY", DRUG_OBJECTS),
    ("tang trữ", "MA_TUY", DRUG_OBJECTS),  # Common spelling error in gold annotations.

    # XET_XU
    ("đưa ra xét xử", "XET_XU"),
    ("xét xử", "XET_XU"),
    ("tuyên phạt", "XET_XU"),
    ("nhận án", "XET_XU"),

    # Legal proceedings.
    ("khởi tố", "KHOI_TO"),

    # Seizure of evidence.
    ("thu giữ", "THU_GIU"),
]

EXCLUDED_KEYWORDS = {"xử phạt"}

# Non-trigger phrases: ignore keywords that occur within these phrases.
NON_TRIGGER_PATTERNS = [
    r"đánh\s+(?:bạc|dấu|giá|máy|chữ|số|bài)\b",   # These uses of "đánh" do not indicate violence.
    r"đánh\s+bắt",                                  # Fishing.
    r"bắt\s+đầu",                                   # Begin.
    r"truy\s+bắt(?!\s+thành\s+công)",               # Mere pursuit.
    r"giết\s+mổ",                                   # Butchering livestock.
    r"tố\s+giác",
    r"đạn\s+bắn",                                   # "Hit by a bullet" describes an injury, not an action.
    r"loại\s+bắn",                                  # "Bullet-firing type" describes a weapon.
    r"\btội\s+[\"'“‘]?\s*(?:giết|cướp|trộm|lừa|hiếp)[^,.;!?]*",  # A crime name is not an event.
]

# Administrative phrases: administrative penalties do not contain criminal triggers (guideline B.7).
ADMIN_SENTENCE_CUES = ("vi phạm hành chính", "lập biên bản")

# Cues for unrealized or unasserted events (guideline B.1), searched before the trigger in the same clause.
UNREALIZED_CUES = [
    "nảy sinh ý định", "ý định", "quyết tâm",
    "để tiến hành", "để khởi tố", "để truy tố", "để xử lý", "để bắt", "để truy bắt",
    "kế hoạch", "dự kiến", "chuẩn bị", "đề nghị", "kiến nghị", "đề xuất", "xem xét",
    "củng cố hồ sơ", "hoàn tất hồ sơ", "hoàn thiện hồ sơ", "chuẩn bị hồ sơ",
    "nghi ngờ", "bị nghi", "cho rằng", "bị cáo buộc", "cáo buộc",
    "nếu ", "giả sử", "có thể", "có khả năng", "sẽ ",
    "không ", "chưa ", "phủ nhận",
]

# Plans after the trigger in the same sentence (guideline B.1: "plan ... to arrest").
AFTER_PLAN_CUES = ("nằm trong kế hoạch", "theo kế hoạch", "trong kế hoạch")

# Question cues after the trigger in the same clause: "... or not".
QUESTION_CUE = re.compile(r"\bhay\s+không\b|\?", re.IGNORECASE)

CLAUSE_SPLIT = re.compile(r"[,;:]|\bnhưng\b|\bvà\s+sau\s+đó\b", re.IGNORECASE)


def _is_abbreviation_dot(text: str, position: int) -> bool:
    """Return whether a period after a standalone uppercase letter is part of an abbreviation."""
    if position < 1 or text[position] != ".":
        return False
    prev = text[position - 1]
    before = text[position - 2] if position >= 2 else " "
    return prev.isupper() and not before.isalpha()


def _sentence_bounds(text: str, position: int) -> tuple[int, int]:
    """Find the sentence bounds containing position, ignoring abbreviation periods."""
    left = 0
    for mark in (".", "!", "?", "\n"):
        idx = position
        while True:
            idx = text.rfind(mark, 0, idx)
            if idx == -1:
                break
            if mark == "." and _is_abbreviation_dot(text, idx):
                idx -= 1
                continue
            left = max(left, idx + 1)
            break

    right = len(text)
    for idx in range(position, len(text)):
        ch = text[idx]
        if ch == "\n" or (ch in "!?") or (ch == "." and not _is_abbreviation_dot(text, idx)):
            right = idx + 1
            break
    return left, right


def _clause_bounds(text: str, sentence_start: int, position: int) -> int:
    """Return the start of the clause containing position (after the nearest comma/semicolon)."""
    clause_start = sentence_start
    for match in CLAUSE_SPLIT.finditer(text, sentence_start, position):
        clause_start = match.end()
    return clause_start


def _clause_after(text: str, trigger_end: int) -> str:
    """Return the text after the trigger through the end of the current clause."""
    clause_end = len(text)
    for match in CLAUSE_SPLIT.finditer(text, trigger_end):
        clause_end = match.start()
        break
    return text[trigger_end:clause_end].lower()


def _is_unrealized(text: str, sentence_start: int, trigger_start: int, trigger_end: int) -> bool:
    """Reject triggers in clauses with intent, hypothetical, or negation cues.

    Also reject a trigger followed by a plan in the same sentence or by a question such as "... hay không"."""
    clause_start = _clause_bounds(text, sentence_start, trigger_start)
    before = text[clause_start:trigger_start].lower()
    if any(cue in before for cue in UNREALIZED_CUES):
        return True

    sentence_end = _sentence_bounds(text, trigger_start)[1]
    after_sentence = text[trigger_end:sentence_end].lower()
    if any(cue in after_sentence for cue in AFTER_PLAN_CUES):
        return True

    # Apply the question cue only when "or not" immediately follows the trigger, not in another clause.
    after = _clause_after(text, trigger_end)
    match = QUESTION_CUE.search(after)
    if match and match.start() <= 30:
        return True
    return False


def _find_triggers(text: str) -> list[dict]:
    excluded_spans = []
    for pattern in NON_TRIGGER_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            excluded_spans.append((match.start(), match.end()))

    candidates = []
    for rule in TRIGGER_RULES:
        keyword, event_type = rule[0], rule[1]
        required = rule[2] if len(rule) > 2 else None
        scope = rule[3] if len(rule) > 3 else "clause"
        if keyword in EXCLUDED_KEYWORDS:
            continue
        pattern = r"(?<!\w)" + re.escape(keyword) + r"(?!\w)"
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            start, end = match.start(), match.end()
            # Ignore matches inside a non-trigger phrase.
            if any(s <= start and end <= e for s, e in excluded_spans):
                continue
            # Apply rules with required context.
            if required:
                if scope == "sentence":
                    s_start, s_end = _sentence_bounds(text, start)
                    context = text[s_start:s_end].lower()
                else:
                    context = _clause_after(text, end)
                if not any(word in context for word in required):
                    continue
            candidates.append({
                "text": text[start:end],
                "event_type": event_type,
                "start": start,
                "end": end,
            })
    return candidates


def _select_triggers(text: str, candidates: list[dict]) -> list[dict]:
    # Do not assign criminal triggers in administrative sentences (e.g. administrative citations).
    admin_spans = []
    for cue in ADMIN_SENTENCE_CUES:
        for match in re.finditer(re.escape(cue), text, flags=re.IGNORECASE):
            admin_spans.append(_sentence_bounds(text, match.start()))
    candidates = [
        c for c in candidates
        if not any(s <= c["start"] < e for s, e in admin_spans)
    ]

    # Prefer longer phrases when candidates overlap.
    ordered = sorted(candidates, key=lambda t: (-(t["end"] - t["start"]), t["start"]))
    chosen = []
    for trigger in ordered:
        if any(trigger["start"] < c["end"] and trigger["end"] > c["start"] for c in chosen):
            continue
        chosen.append(trigger)
    chosen.sort(key=lambda t: t["start"])

    # Consider only the first mention when an action is repeated in a sentence (guideline B.3).
    # Apply the assertion/unrealized-event check to that first mention.
    first_mentions = []
    seen = set()
    for trigger in chosen:
        sentence_start, _ = _sentence_bounds(text, trigger["start"])
        key = (trigger["text"].lower(), sentence_start)
        if key in seen:
            continue
        seen.add(key)
        first_mentions.append(trigger)

    # Remove unrealized or unasserted triggers.
    result = []
    for trigger in first_mentions:
        sentence_start, _ = _sentence_bounds(text, trigger["start"])
        if _is_unrealized(text, sentence_start, trigger["start"], trigger["end"]):
            continue
        result.append(trigger)
    return result


def detect_triggers(text: str) -> list[dict]:
    """Return triggers filtered according to guideline B, without requiring entities."""
    return _select_triggers(text, _find_triggers(text))


def extract_events(text: str, ner_entities: list) -> list:
    events = []

    # 1. Detect triggers according to the guidelines.
    triggers = detect_triggers(text)

    # 2. Sort entities.
    entities = sorted(
        ner_entities,
        key=lambda e: (e.get("start", 0), e.get("end", 0)),
    )

    # 3. Assign arguments within the sentence containing each trigger.
    for trigger in triggers:
        sentence_start, sentence_end = _sentence_bounds(text, trigger["start"])

        local_entities = [
            entity for entity in entities
            if entity.get("start", 0) >= sentence_start
            and entity.get("end", 0) <= sentence_end
        ]

        arguments = []

        # Agency: nearest organization preceding the trigger.
        organizations = [
            entity for entity in local_entities
            if entity.get("label") == "ORGANIZATION"
            and entity.get("end", 0) <= trigger["start"]
        ]
        if organizations:
            arguments.append({"role": "CO_QUAN", "entity": organizations[-1]})

        # Suspect: PERSON after the trigger in the same sentence, or the nearest preceding PERSON.
        persons_after = [
            entity for entity in local_entities
            if entity.get("label") == "PERSON"
            and entity.get("start", 0) >= trigger["end"]
        ]
        if persons_after:
            selected_persons = persons_after
        else:
            persons_before = [
                entity for entity in local_entities
                if entity.get("label") == "PERSON"
                and entity.get("end", 0) <= trigger["start"]
            ]
            selected_persons = persons_before[-1:] if persons_before else []

        for person in selected_persons:
            arguments.append({"role": "DOI_TUONG", "entity": person})

        # Time or sentence length in the same sentence.
        for entity in local_entities:
            if entity.get("label") != "TIME":
                continue
            entity_text = entity.get("text", "").lower()
            if trigger["event_type"] == "XET_XU" and re.search(r"\b(tù|tù giam|án tù)\b", entity_text):
                role = "MUC_AN"
            else:
                role = "THOI_GIAN"
            arguments.append({"role": role, "entity": entity})

        if arguments:
            events.append({
                "event_type": trigger["event_type"],
                "trigger": trigger,
                "arguments": arguments,
            })

    return events