import json
import re
import sys
from pathlib import Path

import pandas as pd

ROLE_TYPES = {"DOI_TUONG": {"PERSON", "ORGANIZATION"}, "NAN_NHAN": {"PERSON", "ORGANIZATION"},
              "CO_QUAN": {"ORGANIZATION"}, "TAI_SAN": {"MONEY", "PRODUCT"}, "TANG_VAT": {"DRUG", "PRODUCT"},
              "HUNG_KHI": {"PRODUCT"}, "TOI_DANH": {"CRIME"}, "MUC_AN": {"TIME", "MONEY"},
              "THOI_GIAN": {"TIME"}, "DIA_DIEM": {"LOCATION"}}
PROCEDURAL = {"BAT_GIU", "THU_GIU", "KHOI_TO", "XET_XU"}
HOME_RE = re.compile(r"(quê|ngụ|trú|cư trú|thường trú|sinh sống|SN \d{4},? ở|tuổi,? ở)[^()]{0,40}$", re.I)
NOT_EVENT_RE = re.compile(r"(ý định|âm mưu|quyết tâm|kế hoạch|nghi ngờ|chưa|không|đánh|truy|nhằm|để|loại hình|tội phạm)\s+$", re.I)
GEO_BEFORE_RE = re.compile(r"(TP\.?|tỉnh|huyện|quận|xã|phường|thị xã|thị trấn|thành phố)\s*$", re.I)
TITLE_BEFORE_RE = re.compile(r"(anh|chị|ông|bà|bị can|bị cáo|đối tượng|nghi phạm|nạn nhân)\s*$", re.I)
PERSON_STOP = {"Song", "Tòa", "Toà", "HĐXX", "Ví", "Tuy", "Nhưng", "Theo"}
MISSING_TRIGGER = {"xử phạt": "XET_XU", "tấn công": "BAO_LUC", "bắt cóc": "BAO_LUC", "giết hại": "BAO_LUC",
                   "lừa đảo chiếm đoạt": "LUA_DAO", "khống chế bắt giữ": "BAT_GIU"}


def get_result(task):
    anns = [a for a in task.get("annotations", []) if not a.get("was_cancelled")]
    if anns:
        return anns[-1]["result"], "annotation"
    preds = task.get("predictions", [])
    return (preds[-1]["result"], "prediction") if preds else ([], "none")


def check(task):
    s = task["data"]["sentence"]
    res, _src = get_result(task)
    spans = {r["id"]: r for r in res if r["type"] == "labels"}
    rels = [r for r in res if r["type"] == "relation"]
    ents = [r for r in spans.values() if r["from_name"] == "entity"]
    trigs = [r for r in spans.values() if r["from_name"] == "trigger"]
    lab = lambda r: r["value"]["labels"][0]
    txt = lambda r: r["value"]["text"]
    before = lambda r, n=30: s[max(0, r["value"]["start"] - n):r["value"]["start"]]
    out = []

    # thực thể
    for e in ents:
        t, L = txt(e), lab(e)
        if t.endswith("."):
            out.append(("SPAN_DAU_CHAM", f"'{t}' ({L}) dính dấu chấm cuối"))
        if L == "ORGANIZATION" and t.strip().lower() in {"công an", "cảnh sát", "tòa", "toà"}:
            out.append(("ORG_CHUNG_CHUNG", f"'{t}' không có tên đơn vị -> xóa"))
        if L == "PERSON" and (t in PERSON_STOP or t[0].islower()):
            out.append(("PERSON_SAI", f"'{t}' có thể không phải tên người"))
        if L == "PERSON" and GEO_BEFORE_RE.search(before(e)):
            out.append(("PERSON_LA_DIA_DANH", f"'{t}' đứng sau cấp hành chính -> có thể là LOCATION"))
        if L == "LOCATION" and TITLE_BEFORE_RE.search(before(e, 15)):
            out.append(("LOC_LA_NGUOI", f"'{t}' đứng sau danh xưng -> có thể là PERSON"))
        if L == "DRUG" and re.search(r"(phòng,? chống|chống|tội phạm về)\s*$", before(e, 20), re.I):
            out.append(("DRUG_TRONG_TEN_DON_VI", f"'{t}' nằm trong tên đơn vị (phòng, chống ma túy) -> xóa"))
        if L == "LOCATION" and len(t.split()) >= 4 and re.search(r"\b(THCS|THPT|trường)\b", t):
            out.append(("LOC_DINH_TEN_NGUOI", f"'{t}' có thể dính tên người -> tách"))
        if L == "LOCATION" and re.fullmatch(r"[A-Z]{1,5}", t):
            out.append(("LOC_VIET_TAT", f"'{t}' là chữ viết tắt -> kiểm tra lại"))
    for a, b in zip(sorted(ents, key=lambda r: r["value"]["start"]), sorted(ents, key=lambda r: r["value"]["start"])[1:]):
        if lab(a) == lab(b) == "TIME" and s[a["value"]["end"]:b["value"]["start"]].strip() == "":
            out.append(("TIME_BI_TACH", f"'{txt(a)}' + '{txt(b)}' -> gộp 1 nhãn TIME"))

    # trigger
    st = sorted(trigs, key=lambda r: r["value"]["start"])
    for a, b in zip(st, st[1:]):
        if s[a["value"]["end"]:b["value"]["start"]].strip() == "" and lab(a) == lab(b):
            out.append(("TRIGGER_BI_TACH", f"'{txt(a)}' + '{txt(b)}' -> gộp 1 trigger {lab(a)}"))
    for t in trigs:
        after = s[t["value"]["end"]:t["value"]["end"] + 4]
        if txt(t).lower() == "giết" and after.startswith(" hại"):
            out.append(("TRIGGER_THIEU_CHU", "'giết' -> mở rộng thành 'giết hại'"))
        if txt(t).lower() == "bắt" and after.startswith(" cóc"):
            out.append(("TRIGGER_SAI_LOAI", "'bắt' trong 'bắt cóc' -> BAO_LUC cho cả 'bắt cóc' (nếu vụ việc có thật)"))
        if NOT_EVENT_RE.search(before(t, 20)):
            out.append(("CO_THE_KHONG_PHAI_SU_KIEN", f"'{txt(t)}' đứng sau '{before(t, 20).strip()[-15:]}' -> sự kiện đã xảy ra chưa?"))
    labeled = {(t["value"]["start"], t["value"]["end"]) for t in trigs}
    for ph, et in MISSING_TRIGGER.items():
        for m in re.finditer(re.escape(ph), s, re.I):
            if not any(a <= m.start() and m.end() <= b for a, b in labeled):
                out.append(("CO_THE_THIEU_TRIGGER", f"'{m.group(0)}' chưa được gán ({et}?)"))

    # quan hệ
    for r in rels:
        a, b = spans.get(r["from_id"]), spans.get(r["to_id"])
        if not a or not b:
            continue
        role = (r.get("labels") or ["(chưa chọn)"])[0]
        if a["from_name"] != "trigger":
            out.append(("QH_NGUOC_CHIEU", f"'{txt(a)}' -> '{txt(b)}' phải đi từ trigger"))
            continue
        if role not in ROLE_TYPES:
            out.append(("QH_CHUA_CHON_VAI_TRO", f"'{txt(a)}' -> '{txt(b)}'"))
            continue
        if lab(b) not in ROLE_TYPES[role]:
            out.append(("QH_SAI_KIEU", f"{role} không nối tới {lab(b)} ('{txt(a)}' -> '{txt(b)}')"))
        if role == "DIA_DIEM" and HOME_RE.search(before(b, 45)):
            out.append(("DIA_DIEM_LA_QUE_NOI_O", f"'{txt(a)}' -> '{txt(b)}' là quê/nơi ở, không phải nơi xảy ra"))
    targets = {r["to_id"] for r in rels}
    if trigs:
        for e in ents:
            if lab(e) == "PERSON" and e["id"] not in targets:
                out.append(("PERSON_CHUA_NOI", f"'{txt(e)}' chưa là DOI_TUONG/NAN_NHAN của trigger nào -> kiểm tra"))
            if lab(e) == "ORGANIZATION" and e["id"] not in targets and \
                    any(lab(t) in PROCEDURAL for t in trigs):
                out.append(("ORG_CHUA_NOI_CO_QUAN", f"'{txt(e)}' chưa nối CO_QUAN với trigger tố tụng"))
    linked = {r["from_id"] for r in rels}
    for t in trigs:
        if t["id"] not in linked and ents:
            out.append(("TRIGGER_CHUA_NOI", f"'{txt(t)}' chưa có quan hệ nào"))
        if lab(t) in PROCEDURAL and t["id"] in linked:
            roles = {(r.get("labels") or [""])[0] for r in rels if r["from_id"] == t["id"]}
            if "CO_QUAN" not in roles and any(lab(e) == "ORGANIZATION" for e in ents):
                out.append(("CO_THE_THIEU_CO_QUAN", f"'{txt(t)}' chưa nối CO_QUAN dù câu có ORGANIZATION"))
    return out


if __name__ == "__main__":
    path = Path(sys.argv[1])
    tasks = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for i, task in enumerate(tasks):
        no = task.get("inner_id", i + 1)
        for kind, detail in dict.fromkeys(check(task)):
            rows.append({"so_task": no, "ann_id": task["data"]["ann_id"], "loai_loi": kind,
                         "chi_tiet": detail, "cau": task["data"]["sentence"]})
    df = pd.DataFrame(rows, columns=["so_task", "ann_id", "loai_loi", "chi_tiet", "cau"])
    out = path.with_name(path.stem + "_issues.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"{len(tasks)} câu, {df['so_task'].nunique()} câu có cảnh báo, {len(df)} cảnh báo -> {out.name}\n")
    print(df["loai_loi"].value_counts().to_string())
