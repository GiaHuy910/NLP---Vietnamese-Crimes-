"""Đọc/ghi file .jsonl của luồng 2.

Mỗi dòng là một câu:
    {"ann_id", "sentence",
     "entities":  [{"id", "start", "end", "text", "label"}],
     "triggers":  [{"id", "start", "end", "text", "label"}],
     "relations": [{"trigger_id", "arg_id", "role"}]}
File gold do data_pipeline/step7_export_dataset.py tạo; file dự đoán (của baseline hoặc mô hình)
dùng đúng định dạng này, chỉ cần có ann_id để ghép với gold.
"""
import json
from pathlib import Path

from .schema import EVENT_TYPES, ROLE_TYPES


def load_jsonl(path):
    rows = []
    with Path(path).open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_no}: JSON không hợp lệ ({exc})") from exc
    return rows


def save_jsonl(rows, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def validate(rows, name="data"):
    """Kiểm tra offset, nhãn và quan hệ; trả về danh sách lỗi (rỗng = hợp lệ)."""
    errors = []
    for r in rows:
        s, aid = r["sentence"], r.get("ann_id", "?")
        ents = {e["id"]: e for e in r.get("entities", [])}
        trigs = {t["id"]: t for t in r.get("triggers", [])}
        for sp in list(ents.values()) + list(trigs.values()):
            if s[sp["start"]:sp["end"]] != sp["text"]:
                errors.append(f"{name} {aid}: offset lệch '{sp['text']}'")
        for t in trigs.values():
            if t["label"] not in EVENT_TYPES:
                errors.append(f"{name} {aid}: loại sự kiện lạ '{t['label']}'")
        for rel in r.get("relations", []):
            t, e = trigs.get(rel["trigger_id"]), ents.get(rel["arg_id"])
            if t is None or e is None:
                errors.append(f"{name} {aid}: quan hệ trỏ tới id không tồn tại {rel}")
            elif rel["role"] not in ROLE_TYPES:
                errors.append(f"{name} {aid}: vai trò lạ '{rel['role']}'")
            elif e["label"] not in ROLE_TYPES[rel["role"]]:
                errors.append(f"{name} {aid}: {rel['role']} không nối tới {e['label']} ('{e['text']}')")
    return errors


def events_of(row):
    """Câu -> danh sách sự kiện dạng span (không phụ thuộc id):
    [{"trigger": (start, end, type), "args": {(start, end, role), ...}}]"""
    ents = {e["id"]: e for e in row.get("entities", [])}
    events = []
    for t in row.get("triggers", []):
        args = set()
        for rel in row.get("relations", []):
            e = ents.get(rel["arg_id"])
            if rel["trigger_id"] == t["id"] and e is not None:
                args.add((e["start"], e["end"], rel["role"]))
        events.append({"trigger": (t["start"], t["end"], t["label"]), "args": args})
    return events
