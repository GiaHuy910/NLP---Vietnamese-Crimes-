import re

from config import DRUG_WORDS, TRIGGER_LEXICON, TRIGGER_STOP

W = r"[^\W\d_]"


def _word_re(phrase):
    # Khớp nguyên cụm, không dính vào chữ khác: 'bắt' không khớp trong 'bắtđầu'
    return re.compile(rf"(?<!{W}){re.escape(phrase)}(?!{W})", re.IGNORECASE)


# Thực thể
TIME_RE = re.compile(
    r"(?:(?:rạng sáng|sáng|trưa|chiều|tối|đêm|khuya)\s+(?:ngày\s+)?)?"
    r"(?:ngày\s+)?\d{1,2}/\d{1,2}(?:/\d{2,4})?"
    r"|(?:ngày\s+)?\d{1,2}\s+tháng\s+\d{1,2}(?:\s+năm\s+\d{4})?"
    r"|(?:tháng\s+\d{1,2}/)?năm\s+\d{4}"
    r"|\d+\s+(?:năm|tháng)\s+tù(?:\s+treo)?|tù chung thân|tử hình",
    re.IGNORECASE)
MONEY_RE = re.compile(
    r"\d+(?:[.,]\d+)*\s*(?:triệu|tỷ|tỉ|nghìn|ngàn)?\s*(?:đồng|USD|VNĐ|VND)"
    r"|\d+(?:[.,]\d+)*\s*(?:triệu|tỷ|tỉ)(?!\s*(?:người|năm))",
    re.IGNORECASE)
DRUG_RE = re.compile(
    r"(?:\d+(?:[.,]\d+)*\s*(?:gam|gram|g|kg|viên|bánh|gói|liều|tép|túi)\s+)?"
    r"(?:ma túy|ma tuý|heroin|ketamin|thuốc lắc|cần sa|methamphetamine|MDMA)(?:\s+(?:tổng hợp|đá))?",
    re.IGNORECASE)
CRIME_PATTERNS = [
    # "tội Lừa đảo chiếm đoạt tài sản", "tội Bắt, giữ, giam người trái pháp luật và Cướp tài sản"
    re.compile(r"(?<=tội\s)[\"“]?([A-ZĐÀ-Ỹ][^.;:()\"”]{2,80}?)[\"”]?(?=\s*[.;:()]|\s+(?:theo|tại|với|đối với|xảy ra|khi|nhưng)\s|$)"),
    # hành vi / về tội ... trong ngoặc kép: “Lừa đảo chiếm đoạt tài sản”
    re.compile(r"(?:hành vi|tội danh|về tội|tội)\s*[\"“]([^\"”]{3,80})[\"”]"),
]


def _crime_spans(s):
    spans = []
    for rx in CRIME_PATTERNS:
        for m in rx.finditer(s):
            start, text = m.start(1), m.group(1)
            # tách "X và Y" khi Y là tên tội viết hoa
            offset = 0
            for part in re.split(r"(\s+và\s+)(?=[A-ZĐÀ-Ỹ])", text):
                if part.strip() and not re.fullmatch(r"\s+và\s+", part):
                    spans.append({"start": start + offset, "end": start + offset + len(part.rstrip()),
                                  "text": part.rstrip(), "label": "CRIME"})
                offset += len(part)
    return spans


ORG_HEADS = ["Cơ quan Cảnh sát điều tra", "Cơ quan CSĐT", "Cơ quan An ninh điều tra", "Cơ quan điều tra",
             "Viện kiểm sát nhân dân", "VKSND", "Tòa án nhân dân", "Toà án nhân dân", "TAND",
             "Công an", "công an", "Phòng Cảnh sát", "Đội Cảnh sát", "Cục Cảnh sát", "Bộ Công an",
             "Công ty", "Ngân hàng", "UBND", "Ủy ban nhân dân"]
ORG_RE = re.compile("|".join(re.escape(h) for h in sorted(ORG_HEADS, key=len, reverse=True)))
ORG_CONT_LOWER = {"tỉnh", "thành", "phố", "quận", "huyện", "thị", "trấn", "xã", "phường", "an", "nhân",
                  "dân", "tối", "cao", "cảnh", "sát", "điều", "tra", "kiểm", "hình", "sự", "kinh", "tế",
                  "ma", "túy", "tuý", "trật", "tự", "hội", "cấp"}
TRAIL_PUNCT = ",.;:()\"“”'!?"


def _org_spans(s):
    spans = []
    for m in ORG_RE.finditer(s):
        end = m.end()
        for tok in re.finditer(r"\S+", s[m.end():]):
            word = tok.group(0)
            core = word.strip(TRAIL_PUNCT)
            if not core or word[0] in TRAIL_PUNCT:
                break
            if core[0].isupper() or core.lower() in ORG_CONT_LOWER or core in {"TP", "Q"}:
                end = m.end() + tok.start() + word.find(core) + len(core)
                if core != word.rstrip(".") and word.endswith(tuple(TRAIL_PUNCT)) and core not in {"TP", "Q"}:
                    break                                 # dấu câu ngay sau từ -> hết tên
            else:
                break
        # bỏ chữ thường thừa ở cuối ("Công an thị" khi không có tên sau)
        text = s[m.start():end]
        while text.split()[-1].lower() in ORG_CONT_LOWER and len(text.split()) > len(m.group(0).split()):
            text = text[: text.rfind(" ")]
        spans.append({"start": m.start(), "end": m.start() + len(text), "text": text, "label": "ORGANIZATION"})
    return spans


def _regex_spans(s, rx, label, group=0):
    return [{"start": m.start(group), "end": m.end(group), "text": m.group(group), "label": label}
            for m in rx.finditer(s) if m.group(group).strip()]


LOC_HEADS = {"xã", "huyện", "tỉnh", "quận", "phường", "thị", "thành", "tp.", "q.", "thôn", "ấp", "phố", "đường"}
PERSON_TITLES = ["anh", "chị", "ông", "bà", "em", "cháu", "nghi phạm", "nghi can", "đối tượng", "bị can",
                 "bị cáo", "nạn nhân", "tên", "cô", "thầy", "vợ", "chồng"]


def _ner_spans(s):
    # PERSON / LOCATION từ underthesea.ner (nhãn BIO trên từ).
    from underthesea import ner
    spans, cursor, cur = [], 0, None
    for tok, _pos, _chunk, tag in ner(s):
        i = s.find(tok, cursor)
        if i < 0:
            cur = None
            continue
        cursor = i + len(tok)
        kind = tag[2:] if tag != "O" else None
        label = {"PER": "PERSON", "LOC": "LOCATION"}.get(kind)
        if tag.startswith("B-") and label:
            cur = {"start": i, "end": cursor, "label": label}
            spans.append(cur)
        elif tag.startswith("I-") and label and cur and cur["label"] == label:
            cur["end"] = cursor
        else:
            cur = None
    out = []
    for sp in spans:
        text = s[sp["start"]:sp["end"]]
        words = text.split()
        # bỏ chữ thường ở đầu ("nghi phạm Vũ Quang Vinh"), trừ cấp hành chính của địa danh
        while words and words[0][0].islower() and words[0].lower() not in LOC_HEADS:
            sp["start"] += len(words[0]) + 1
            words = words[1:]
        if not words or not any(w[0].isupper() for w in words):
            continue                                  # không có tên riêng -> bỏ
        before = s[:sp["start"]].lower().rstrip()
        if any(before.endswith(t) for t in PERSON_TITLES):
            sp["label"] = "PERSON"
        sp["text"] = s[sp["start"]:sp["end"]]
        out.append(sp)
    return out


def _remove_overlaps(spans):
    #Giữ span ưu tiên cao hơn, rồi dài hơn; bỏ span chồng lên span đã giữ.
    kept = []
    for sp in sorted(spans, key=lambda x: (x["prio"], -(x["end"] - x["start"]))):
        if all(sp["end"] <= k["start"] or sp["start"] >= k["end"] for k in kept):
            kept.append(sp)
    return sorted(kept, key=lambda x: x["start"])


def find_entities(s, use_ner=True):
    groups = [  # (span list, priority: số nhỏ = ưu tiên cao)
        (_crime_spans(s), 0),
        (_org_spans(s), 1),
        (_regex_spans(s, MONEY_RE, "MONEY"), 2),
        (_regex_spans(s, TIME_RE, "TIME"), 2),
        (_regex_spans(s, DRUG_RE, "DRUG"), 2),
        (_ner_spans(s) if use_ner else [], 3),
    ]
    spans = [dict(sp, prio=p) for lst, p in groups for sp in lst]
    return [{k: v for k, v in sp.items() if k != "prio"} for sp in _remove_overlaps(spans)]


# Trigger
LEXICON_RE = [(etype, ph, _word_re(ph)) for etype, phrases in TRIGGER_LEXICON.items() for ph in phrases]
STOP_RE = [_word_re(p) for p in TRIGGER_STOP]
HAS_DRUG = re.compile("|".join(re.escape(w) for w in DRUG_WORDS), re.IGNORECASE)


def find_triggers(s, entities=()):
    blocked = [(m.start(), m.end()) for rx in STOP_RE for m in rx.finditer(s)]
    blocked += [(e["start"], e["end"]) for e in entities if e["label"] in ("CRIME", "ORGANIZATION")]
    drug_ok = bool(HAS_DRUG.search(s))
    cands = []
    for etype, _ph, rx in LEXICON_RE:
        if etype == "MA_TUY" and not drug_ok:
            continue
        for m in rx.finditer(s):
            if any(m.start() < b_end and m.end() > b_start for b_start, b_end in blocked):
                continue
            cands.append({"start": m.start(), "end": m.end(), "text": m.group(0), "label": etype, "prio": 0})
    return [{k: v for k, v in sp.items() if k != "prio"} for sp in _remove_overlaps(cands)]


def has_trigger_keyword(s):
    return bool(find_triggers(s))
