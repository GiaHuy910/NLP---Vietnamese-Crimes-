"""Baseline luồng 2 bằng luật / từ khóa (không học máy).

Trigger : khớp từ khóa theo TRIGGER_LEXICON, bỏ các trường hợp quy ước không gán
          (ý định, phủ định, đề nghị, tên tội sau "tội"/"hành vi", danh từ chỉ người...).
Argument: nối trigger tới thực thể trong cùng mệnh đề theo luật vai trò đơn giản.
Thực thể : lấy từ file đầu vào (gold NER hoặc dự đoán của luồng 1), baseline không tự nhận diện.

Hàm chính: predict_row(row) -> row dự đoán cùng định dạng jsonl.
"""
import re

from .schema import CRIME_EVENTS, ROLE_TYPES

# Cụm dài đặt trước cụm ngắn để khớp cụm dài nhất
TRIGGER_LEXICON = {
    "BAT_GIU": ["khống chế bắt giữ", "bắt quả tang", "bắt khẩn cấp", "bắt tạm giam", "bắt giữ",
                "tạm giữ", "tạm giam", "khống chế", "bắt"],
    "KHOI_TO": ["khởi tố", "truy tố"],
    "XET_XU": ["xét xử", "tuyên phạt", "tuyên án", "kết án", "lãnh án", "xử phạt"],
    "THU_GIU": ["thu giữ", "tịch thu", "thu được"],
    "LUA_DAO": ["lừa đảo chiếm đoạt", "lừa đảo", "chiếm đoạt", "lừa"],
    "CUOP_TROM": ["cướp giật", "trộm cắp", "cướp", "trộm", "đột nhập"],
    "BAO_LUC": ["giết hại", "sát hại", "đánh đập", "hành hung", "tấn công", "giết", "đâm", "chém",
                "bắn", "hiếp dâm"],
    "MA_TUY": ["mua bán", "buôn bán", "tàng trữ", "vận chuyển", "sử dụng", "đặt mua"],
}
DRUG_RE = re.compile(r"ma t[uú]y|ma tuý|heroin|ketamin|thuốc lắc|cần sa|methamphetamin|mdma|hồng phiến",
                     re.IGNORECASE)

# Cụm chứa từ khóa nhưng không phải trigger
STOP_PHRASES = ["bắt đầu", "bắt buộc", "bắt tay", "bắt gặp", "bắt kịp", "bắt nguồn", "bắt chước", "bắt cóc",
                "đánh bắt", "truy bắt", "đâm vào", "đâm sầm", "đâm xe", "trại tạm giam", "nhà tạm giữ",
                "kẻ trộm", "tên trộm", "siêu trộm", "nhóm cướp", "băng cướp", "siêu lừa", "lừa đảo qua mạng",
                "sử dụng mạng"]
# Từ đứng ngay trước trigger cho thấy sự kiện chưa/không xảy ra (theo quy ước gán nhãn)
NOT_HAPPENED_RE = re.compile(
    r"(?:ý định|kế hoạch|dự kiến|sẽ|để|nhằm|nếu|không|chưa|đề nghị|kiến nghị|mong|muốn|"
    r"có thể|nghi|quyết tâm|kiên quyết|dọa|tìm cách|âm mưu)\s+(?:\S+\s+){0,2}$", re.IGNORECASE)
CRIME_NAME_BEFORE_RE = re.compile(r"(?:tội|hành vi|tội danh)\s*[\"“]?\s*$", re.IGNORECASE)
HOME_BEFORE_RE = re.compile(r"(?:quê|ngụ|trú|cư trú|thường trú|sinh sống|ở)\b[^,()]{0,40}$", re.IGNORECASE)

_W = r"[^\W\d_]"
_LEX = [(et, ph, re.compile(rf"(?<!{_W}){re.escape(ph)}(?!{_W})", re.IGNORECASE))
        for et, phrases in TRIGGER_LEXICON.items() for ph in phrases]
_STOP = [re.compile(rf"(?<!{_W}){re.escape(p)}(?!{_W})", re.IGNORECASE) for p in STOP_PHRASES]


def find_triggers(sentence, entities=()):
    blocked = [(m.start(), m.end()) for rx in _STOP for m in rx.finditer(sentence)]
    blocked += [(e["start"], e["end"]) for e in entities if e["label"] in ("CRIME", "ORGANIZATION")]
    has_drug = bool(DRUG_RE.search(sentence))
    cands = []
    for etype, _ph, rx in _LEX:
        if etype == "MA_TUY" and not has_drug:
            continue
        for m in rx.finditer(sentence):
            a, b = m.start(), m.end()
            if any(a < be and b > bs for bs, be in blocked):
                continue
            before = sentence[max(0, a - 40):a]
            if NOT_HAPPENED_RE.search(before) or CRIME_NAME_BEFORE_RE.search(before):
                continue
            cands.append({"start": a, "end": b, "text": sentence[a:b], "label": etype})
    # bỏ span chồng lấn, ưu tiên span dài
    kept = []
    for c in sorted(cands, key=lambda x: (-(x["end"] - x["start"]), x["start"])):
        if all(c["end"] <= k["start"] or c["start"] >= k["end"] for k in kept):
            kept.append(c)
    # một sự kiện nhắc lại nhiều lần ("khởi tố vụ án, khởi tố bị can") -> giữ lần đầu
    out, seen = [], set()
    for c in sorted(kept, key=lambda x: x["start"]):
        key = (c["label"], c["text"].lower())
        if c["label"] == "KHOI_TO" and key in seen:
            continue
        seen.add(key)
        out.append(c)
    return [dict(c, id=f"t{i}") for i, c in enumerate(out)]


def _clause_bounds(sentence, pos):
    """Mệnh đề quanh vị trí pos: cắt theo ; và các dấu chấm câu."""
    left = max(sentence.rfind(ch, 0, pos) for ch in ";.!?") + 1
    rights = [i for i in (sentence.find(ch, pos) for ch in ";.!?") if i != -1]
    return left, (min(rights) if rights else len(sentence))


def _role_for(trigger, ent, sentence):
    lab, et = ent["label"], trigger["label"]
    after = ent["start"] >= trigger["end"]
    if lab == "CRIME":
        return "TOI_DANH"
    if lab == "LOCATION":
        return None if HOME_BEFORE_RE.search(sentence[max(0, ent["start"] - 45):ent["start"]]) else "DIA_DIEM"
    if lab == "TIME":
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
        # CO_QUAN: chỉ lấy tổ chức gần trigger nhất phía trước
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
