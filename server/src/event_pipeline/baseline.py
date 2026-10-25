"""Part 2 rule/keyword baseline (no machine learning).

Trigger: match keywords from TRIGGER_LEXICON and exclude conventionally unannotated cases
         (intent, negation, requests, crime names after "tội"/"hành vi", person nouns, etc.).
Argument: link triggers to entities in the same clause using simple role rules.
Entities: read from input (gold NER or Part 1 predictions); the baseline does not recognize entities.

Main function: predict_row(row) -> a prediction record in the same JSONL format.
"""
import re

from .schema import CRIME_EVENTS, ROLE_TYPES

# Longer phrases come before shorter ones so the longest match is selected.
TRIGGER_LEXICON = {
    "BAT_GIU": ["khống chế bắt giữ", "bắt quả tang", "bắt khẩn cấp", "bắt tạm giam", "bắt giữ",
                "tạm giữ", "tạm giam", "khống chế", "bắt"],
    "KHOI_TO": ["khởi tố", "truy tố"],
    "XET_XU": ["xét xử", "tuyên phạt", "tuyên án", "kết án", "lãnh án", "xử phạt", "giảm án"],
    "THU_GIU": ["thu giữ", "tịch thu", "thu được"],
    "LUA_DAO": ["lừa đảo chiếm đoạt", "lừa đảo", "chiếm đoạt", "lừa", "giả giọng", "tự xưng",
                "giả danh", "mạo danh"],
    "CUOP_TROM": ["cướp giật", "trộm cắp", "cướp", "trộm", "đột nhập"],
    "BAO_LUC": ["giết hại", "sát hại", "đánh đập", "hành hung", "tấn công", "hiếp dâm", "xâm hại",
                "ẩu đả", "giết", "đâm", "chém", "bắn", "đánh", "gí"],
    # "Strong" drug verbs require only a drug mention somewhere in the sentence.
    "MA_TUY": ["mua bán", "buôn bán", "tàng trữ", "vận chuyển", "sản xuất", "sử dụng", "đặt mua"],
}
# "Weak" drug verbs (deliver, hide, store, etc.) count only when a drug is mentioned immediately afterward.
WEAK_DRUG_VERBS = ["giao", "giấu", "cất", "chuyển", "trồng", "bán", "mua", "lấy"]
DRUG_RE = re.compile(r"ma t[uú]y|ma tuý|heroin|ketamin|thuốc lắc|cần sa|methamphetamin|mdma|hồng phiến|"
                     r"thuốc phiện|cây thuốc phiện", re.IGNORECASE)

# Phrases that contain trigger keywords but are not triggers.
STOP_PHRASES = ["bắt đầu", "bắt buộc", "bắt tay", "bắt gặp", "bắt kịp", "bắt nguồn", "bắt chước", "bắt cóc",
                "bắt xe", "bắt nạt", "bắt con", "đánh bắt", "truy bắt", "đâm sầm", "đâm xe", "đâm vào xe",
                "đâm vào cột", "đâm vào tường", "trại tạm giam", "nhà tạm giữ", "kẻ trộm", "tên trộm",
                "siêu trộm", "nhóm cướp", "băng cướp", "tên cướp", "kẻ cướp", "siêu lừa", "lừa đảo qua mạng",
                "sử dụng mạng", "đánh bạc", "đánh giá", "đánh dấu", "đánh máy", "đánh thuế", "đánh đồng",
                "đánh số", "đánh bóng", "mũi tấn công", "săn bắt", "nắm bắt", "cướp cò", "đọc trộm",
                "theo truy tố", "nhóm đối tượng lừa đảo", "phương thức lừa đảo", "thủ đoạn lừa đảo", "xét xử vắng mặt", "tấn công mạng", "bắn chỉ thiên",
                "đạn bắn", "khống chế ngọn lửa", "khống chế toàn bộ"]
# Cues that an event has not happened or is not asserted; search before the trigger within the same clause (guideline B.1).
NOT_HAPPENED_RE = re.compile(
    r"(?:ý định|kế hoạch|dự kiến|\bsẽ\b|\bđể\b|\bnhằm\b|\bnếu\b|\bkhông\b|\bchưa\b|đề nghị|"
    r"kiến nghị|\bmong\b|\bmuốn\b|có thể|\bnghi\b|quyết tâm|kiên quyết|dọa|tìm cách|âm mưu|"
    r"\brủ\b|chuẩn bị|lên kế hoạch)\s+(?:\S+\s+){0,2}$", re.IGNORECASE)
CLAUSE_CUE_RE = re.compile(r"(?:nảy sinh ý định|lên kế hoạch|dự kiến|đề nghị|kiến nghị|chưa có|"
                           r"nằm trong kế hoạch|có dấu hiệu|không phê chuẩn|dự thảo|\bmong\b|\bxin\b|"
                           r"\bhỏi\b|\bcần\b|\bnghi\b(?! phạm| can))", re.IGNORECASE)
CRIME_NAME_BEFORE_RE = re.compile(r"(?:tội|hành vi|tội danh)\s*[\"“]?\s*$", re.IGNORECASE)
HOME_BEFORE_RE = re.compile(r"(?:quê|ngụ|trú|cư trú|thường trú|sinh sống|ở)\b[^,()]{0,40}$", re.IGNORECASE)

_W = r"[^\W\d_]"
def _rx(phrase):
    return re.compile(rf"(?<!{_W}){re.escape(phrase)}(?!{_W})", re.IGNORECASE)
_LEX = [(et, ph, _rx(ph)) for et, phrases in TRIGGER_LEXICON.items() for ph in phrases]
_WEAK = [(ph, _rx(ph)) for ph in WEAK_DRUG_VERBS]
_STOP = [_rx(p) for p in STOP_PHRASES]
_CLAUSE_SPLIT = re.compile(r"[,;:]")


def _clause_before(sentence, pos):
    starts = [m.end() for m in _CLAUSE_SPLIT.finditer(sentence, 0, pos)]
    return sentence[(starts[-1] if starts else 0):pos]


def find_triggers(sentence, entities=()):
    blocked = [(m.start(), m.end()) for rx in _STOP for m in rx.finditer(sentence)]
    blocked += [(e["start"], e["end"]) for e in entities if e["label"] in ("CRIME", "ORGANIZATION")]
    has_drug = bool(DRUG_RE.search(sentence))
    cands = []

    def add(a, b, etype):
        if any(a < be and b > bs for bs, be in blocked):
            return
        before = sentence[max(0, a - 40):a]
        if NOT_HAPPENED_RE.search(before) or CRIME_NAME_BEFORE_RE.search(before):
            return
        if CLAUSE_CUE_RE.search(_clause_before(sentence, a)):
            return
        cands.append({"start": a, "end": b, "text": sentence[a:b], "label": etype})

    for etype, _ph, rx in _LEX:
        if etype == "MA_TUY" and not has_drug:
            continue
        for m in rx.finditer(sentence):
            add(m.start(), m.end(), etype)
    # Strong drug verbs require a drug mention in the same clause, not only in an organization name.
    cands[:] = [c for c in cands if c["label"] != "MA_TUY"
                or DRUG_RE.search(sentence[max(0, c["start"] - 40):c["end"] + 60])]
    if has_drug:
        for _ph, rx in _WEAK:
            for m in rx.finditer(sentence):
                if DRUG_RE.search(sentence[m.end():m.end() + 25]):
                    add(m.start(), m.end(), "MA_TUY")
    # Remove overlapping spans, preferring the longer span.
    kept = []
    for c in sorted(cands, key=lambda x: (-(x["end"] - x["start"]), x["start"])):
        if all(c["end"] <= k["start"] or c["start"] >= k["end"] for k in kept):
            kept.append(c)
    kept.sort(key=lambda x: x["start"])
    # Treat "restrain, arrest" as one action and keep "arrest".
    kept = [c for i, c in enumerate(kept)
            if not (c["text"].lower() == "khống chế" and i + 1 < len(kept)
                    and kept[i + 1]["label"] == "BAT_GIU" and kept[i + 1]["start"] - c["end"] <= 3)]
    # Keep the first mention when the same event is repeated ("charge the case, charge the suspect").
    # Treat a sequence of fraud tactics ("impersonated ..., claimed to be ...") as one event.
    out, seen = [], set()
    for c in kept:
        key = (c["label"], c["text"].lower())
        if (c["label"] == "KHOI_TO" and key in seen) or (c["label"] == "LUA_DAO" and "LUA_DAO" in seen):
            continue
        seen.add(c["label"])
        seen.add(key)
        out.append(c)
    return [dict(c, id=f"t{i}") for i, c in enumerate(out)]


def _clause_bounds(sentence, pos):
    """Return the clause around pos, split on semicolons and sentence punctuation."""
    left = max(sentence.rfind(ch, 0, pos) for ch in ";.!?") + 1
    rights = [i for i in (sentence.find(ch, pos) for ch in ";.!?") if i != -1]
    return left, (min(rights) if rights else len(sentence))


HOME_CUE_RE = re.compile(r"(?:quê|ngụ|trú|cư trú|thường trú|sinh sống|\bSN\b|sinh năm|\bở\b)", re.IGNORECASE)
REPORT_RE = re.compile(r"cho biết|thông tin|tin từ|xác nhận|thông báo", re.IGNORECASE)


def _is_home(sentence, start):
    """Return whether a place describes a hometown or residence.

    Cues such as quê, ngụ, trú, and SN must precede it in the same parenthetical
    expression or address sequence (separated only by commas).
    """
    window = sentence[max(0, start - 80):start]
    cut = max(window.rfind(")"), window.rfind(";"), window.rfind("."))
    window = window[cut + 1:]
    if "(" in window:                                  # If inside parentheses, search from the nearest opening parenthesis.
        window = window[window.rfind("("):]
    m = None
    for m in HOME_CUE_RE.finditer(window):
        pass
    if m is None:
        return False
    if m.group(0).lower() == "ở":                      # Count "in/at" only when it immediately precedes a location.
        return len(window[m.end():].split()) <= 1
    return True


def _is_report_date(sentence, ent, trigger):
    """Return whether a time span is the reporting date, not the event date."""
    if ent["end"] > trigger["start"]:
        return False
    return bool(REPORT_RE.search(sentence[ent["end"]:trigger["start"]]))


def _role_for(trigger, ent, sentence):
    lab, et = ent["label"], trigger["label"]
    after = ent["start"] >= trigger["end"]
    if lab == "CRIME":
        return "TOI_DANH"
    if lab == "LOCATION":
        return None if _is_home(sentence, ent["start"]) else "DIA_DIEM"
    if lab == "TIME":
        if _is_report_date(sentence, ent, trigger):
            return None
        if et == "XET_XU" and re.search(r"tù|tử hình|chung thân", ent["text"], re.IGNORECASE):
            return "MUC_AN"
        if re.search(r"tù|tử hình|chung thân", ent["text"], re.IGNORECASE):
            return None
        return "THOI_GIAN"
    if lab == "DRUG":
        return "TANG_VAT" if et in ("MA_TUY", "THU_GIU") else None
    if lab == "MONEY":
        return "TAI_SAN" if et in ("LUA_DAO", "CUOP_TROM") else None
    if lab == "PRODUCT":
        return {"THU_GIU": "TANG_VAT", "MA_TUY": "TANG_VAT", "CUOP_TROM": "TAI_SAN",
                "LUA_DAO": "TAI_SAN", "BAO_LUC": "HUNG_KHI"}.get(et)
    if lab == "ORGANIZATION":
        if et not in CRIME_EVENTS and not after:
            return "CO_QUAN"
        return None
    if lab == "PERSON":
        if et in CRIME_EVENTS:
            return "NAN_NHAN" if after else "DOI_TUONG"
        return "DOI_TUONG" if after else None
    return None


def link_arguments(sentence, triggers, entities):
    relations = []
    for t in triggers:
        cs, ce = _clause_bounds(sentence, t["start"])
        local = [e for e in entities if e["start"] >= cs and e["end"] <= ce]
        # AGENCY: use only the nearest preceding organization.
        orgs = [e for e in local if e["label"] == "ORGANIZATION" and e["end"] <= t["start"]]
        for e in local:
            role = _role_for(t, e, sentence)
            if role is None or e["label"] not in ROLE_TYPES[role]:
                continue
            if role == "CO_QUAN" and e is not orgs[-1]:
                continue
            relations.append({"trigger_id": t["id"], "arg_id": e["id"], "role": role})
    return relations


def predict_row(row):
    s = row["sentence"]
    ents = row.get("entities", [])
    trigs = find_triggers(s, ents)
    return {"ann_id": row["ann_id"], "sentence": s, "entities": ents, "triggers": trigs,
            "relations": link_arguments(s, trigs, ents)}
