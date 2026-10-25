import re

# Luật trigger: (từ khóa, loại sự kiện[, từ bắt buộc, phạm vi kiểm tra]).
# - Từ bắt buộc: phải xuất hiện để luật được áp dụng.
# - Phạm vi: "clause" (mặc định) = mệnh đề sau trigger; "sentence" = toàn câu.
# Span trigger theo quy ước gold đã thống nhất (không mở rộng sang tân ngữ).

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

    # MA_TUY: động từ chung chung, chỉ tính khi có chất ma túy trong câu.
    ("mua bán", "MA_TUY", DRUG_OBJECTS, "sentence"),
    ("vận chuyển", "MA_TUY", DRUG_OBJECTS, "sentence"),
    ("sản xuất", "MA_TUY", DRUG_OBJECTS, "sentence"),
    ("buôn", "MA_TUY", DRUG_OBJECTS, "sentence"),
    ("mua", "MA_TUY", DRUG_OBJECTS, "sentence", "clause"),
    ("bán sỉ", "MA_TUY", DRUG_OBJECTS, "sentence"),
    # Tàng trữ ma túy (gold gán MA_TUY); tàng trữ vũ khí không phải trigger này.
    ("tàng trữ", "MA_TUY", DRUG_OBJECTS),
    ("tang trữ", "MA_TUY", DRUG_OBJECTS),  # lỗi chính tả thường gặp trong gold

    # XET_XU
    ("đưa ra xét xử", "XET_XU"),
    ("xét xử", "XET_XU"),
    ("tuyên phạt", "XET_XU"),
    ("nhận án", "XET_XU"),

    # Thủ tục tố tụng
    ("khởi tố", "KHOI_TO"),

    # Thu giữ tang vật
    ("thu giữ", "THU_GIU"),
]

EXCLUDED_KEYWORDS = {"xử phạt"}

# Cụm không phải trigger: nếu từ khóa nằm trong các cụm này thì bỏ qua.
NON_TRIGGER_PATTERNS = [
    r"đánh\s+(?:bạc|dấu|giá|máy|chữ|số|bài)\b",   # "đánh" không phải bạo lực
    r"đánh\s+bắt",                                  # đánh bắt cá
    r"bắt\s+đầu",                                   # bắt đầu
    r"truy\s+bắt(?!\s+thành\s+công)",               # truy bắt đơn thuần
    r"giết\s+mổ",                                   # giết mổ gia súc
    r"tố\s+giác",
    r"đạn\s+bắn",                                   # "bị đạn bắn": nạn nhân bị thương, không phải hành vi
    r"loại\s+bắn",                                  # "súng loại bắn đạn chì": mô tả vũ khí
    r"\btội\s+[\"'“‘]?\s*(?:giết|cướp|trộm|lừa|hiếp)[^,.;!?]*",  # tên tội danh, không phải sự kiện
]

# Cụm hành chính: câu mô tả xử phạt hành chính không chứa trigger hình sự (guide B.7).
ADMIN_SENTENCE_CUES = ("vi phạm hành chính", "lập biên bản")

# Dấu hiệu sự kiện chưa xảy ra / không khẳng định (guide B.1), tìm trong cùng mệnh đề trước trigger.
UNREALIZED_CUES = [
    "nảy sinh ý định", "ý định", "quyết tâm",
    "để tiến hành", "để khởi tố", "để truy tố", "để xử lý", "để bắt", "để truy bắt",
    "kế hoạch", "dự kiến", "chuẩn bị", "đề nghị", "kiến nghị", "đề xuất", "xem xét",
    "củng cố hồ sơ", "hoàn tất hồ sơ", "hoàn thiện hồ sơ", "chuẩn bị hồ sơ",
    "nghi ngờ", "bị nghi", "cho rằng", "bị cáo buộc", "cáo buộc",
    "nếu ", "giả sử", "có thể", "có khả năng", "sẽ ",
    "không ", "chưa ", "phủ nhận",
]

# Kế hoạch nằm sau trigger trong cùng câu (guide B.1: "nằm trong kế hoạch... bắt giữ").
AFTER_PLAN_CUES = ("nằm trong kế hoạch", "theo kế hoạch", "trong kế hoạch")

# Dấu hiệu nghi vấn sau trigger trong cùng mệnh đề: "... hay không".
QUESTION_CUE = re.compile(r"\bhay\s+không\b|\?", re.IGNORECASE)

CLAUSE_SPLIT = re.compile(r"[,;:]|\bnhưng\b|\bvà\s+sau\s+đó\b", re.IGNORECASE)


def _is_abbreviation_dot(text: str, position: int) -> bool:
    """Dấu chấm sau chữ cái viết hoa đơn lẻ (Y., T.M.H, Q.2) không kết thúc câu."""
    if position < 1 or text[position] != ".":
        return False
    prev = text[position - 1]
    before = text[position - 2] if position >= 2 else " "
    return prev.isupper() and not before.isalpha()


def _sentence_bounds(text: str, position: int) -> tuple[int, int]:
    """Tìm phạm vi câu chứa vị trí position (bỏ qua dấu chấm viết tắt)."""
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
    """Vị trí bắt đầu mệnh đề chứa position (sau dấu phẩy/chấm phẩy gần nhất)."""
    clause_start = sentence_start
    for match in CLAUSE_SPLIT.finditer(text, sentence_start, position):
        clause_start = match.end()
    return clause_start


def _clause_after(text: str, trigger_end: int) -> str:
    """Phần văn bản sau trigger, đến hết mệnh đề hiện tại."""
    clause_end = len(text)
    for match in CLAUSE_SPLIT.finditer(text, trigger_end):
        clause_end = match.start()
        break
    return text[trigger_end:clause_end].lower()


def _is_unrealized(text: str, sentence_start: int, trigger_start: int, trigger_end: int) -> bool:
    """Trigger không được gán nếu mệnh đề chứa nó có cue ý định/giả định/phủ định,
    nếu sau trigger trong câu có kế hoạch, hoặc nếu sau trigger là câu hỏi "... hay không"."""
    clause_start = _clause_bounds(text, sentence_start, trigger_start)
    before = text[clause_start:trigger_start].lower()
    if any(cue in before for cue in UNREALIZED_CUES):
        return True

    sentence_end = _sentence_bounds(text, trigger_start)[1]
    after_sentence = text[trigger_end:sentence_end].lower()
    if any(cue in after_sentence for cue in AFTER_PLAN_CUES):
        return True

    # Câu hỏi chỉ áp dụng khi "hay không" nằm ngay sau trigger (không phải mệnh đề hỏi việc khác).
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
            # Bỏ qua nếu nằm trong cụm không phải trigger.
            if any(s <= start and end <= e for s, e in excluded_spans):
                continue
            # Luật có ngữ cảnh bắt buộc.
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
    # Câu hành chính (lập biên bản, vi phạm hành chính): không gán trigger hình sự.
    admin_spans = []
    for cue in ADMIN_SENTENCE_CUES:
        for match in re.finditer(re.escape(cue), text, flags=re.IGNORECASE):
            admin_spans.append(_sentence_bounds(text, match.start()))
    candidates = [
        c for c in candidates
        if not any(s <= c["start"] < e for s, e in admin_spans)
    ]

    # Ưu tiên cụm dài hơn khi chồng lấn.
    ordered = sorted(candidates, key=lambda t: (-(t["end"] - t["start"]), t["start"]))
    chosen = []
    for trigger in ordered:
        if any(trigger["start"] < c["end"] and trigger["end"] > c["start"] for c in chosen):
            continue
        chosen.append(trigger)
    chosen.sort(key=lambda t: t["start"])

    # Cùng một hành động nhắc nhiều lần trong câu: chỉ xét lần đầu (guide B.3).
    # Quyết định khẳng định/chưa xảy ra áp dụng cho lần đầu đó.
    first_mentions = []
    seen = set()
    for trigger in chosen:
        sentence_start, _ = _sentence_bounds(text, trigger["start"])
        key = (trigger["text"].lower(), sentence_start)
        if key in seen:
            continue
        seen.add(key)
        first_mentions.append(trigger)

    # Loại trigger chưa xảy ra hoặc không khẳng định.
    result = []
    for trigger in first_mentions:
        sentence_start, _ = _sentence_bounds(text, trigger["start"])
        if _is_unrealized(text, sentence_start, trigger["start"], trigger["end"]):
            continue
        result.append(trigger)
    return result


def detect_triggers(text: str) -> list[dict]:
    """Trả về các trigger đã được lọc theo guide mục B (không cần thực thể)."""
    return _select_triggers(text, _find_triggers(text))


def extract_events(text: str, ner_entities: list) -> list:
    events = []

    # 1. Tìm Trigger theo guide
    triggers = detect_triggers(text)

    # 2. Chuẩn hóa thứ tự thực thể
    entities = sorted(
        ner_entities,
        key=lambda e: (e.get("start", 0), e.get("end", 0)),
    )

    # 3. Gán arguments trong phạm vi câu chứa Trigger
    for trigger in triggers:
        sentence_start, sentence_end = _sentence_bounds(text, trigger["start"])

        local_entities = [
            entity for entity in entities
            if entity.get("start", 0) >= sentence_start
            and entity.get("end", 0) <= sentence_end
        ]

        arguments = []

        # Cơ quan: tổ chức xuất hiện trước Trigger gần nhất.
        organizations = [
            entity for entity in local_entities
            if entity.get("label") == "ORGANIZATION"
            and entity.get("end", 0) <= trigger["start"]
        ]
        if organizations:
            arguments.append({"role": "CO_QUAN", "entity": organizations[-1]})

        # Đối tượng: PERSON phía sau Trigger trong cùng câu; nếu không có thì PERSON gần nhất phía trước.
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

        # Thời gian / mức án trong cùng câu.
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