"""Trích xuất sự kiện cho API (pipeline.py), dùng schema đã thống nhất của luồng 2.

8 loại sự kiện: LUA_DAO, MA_TUY, BAO_LUC, CUOP_TROM, BAT_GIU, THU_GIU, KHOI_TO, XET_XU.
10 vai trò: DOI_TUONG, NAN_NHAN, CO_QUAN, TAI_SAN, TANG_VAT, HUNG_KHI, TOI_DANH, MUC_AN, THOI_GIAN, DIA_DIEM.

Luật trigger và luật nối vai trò dùng chung với src/event_pipeline/baseline.py, nên kết quả API
khớp với kết quả được chấm bằng src/event_pipeline/evaluate.py.
"""
import re

from ..event_pipeline.baseline import TRIGGER_LEXICON, find_triggers, link_arguments

# Giữ tên cũ cho code khác còn dùng: từ khóa -> loại sự kiện
TRIGGER_DICT = {kw: event_type for event_type, kws in TRIGGER_LEXICON.items() for kw in kws}

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def _sentences(text: str):
    """Tách văn bản thành các câu, trả về (start, end) theo ký tự."""
    start = 0
    for m in _SENTENCE_END.finditer(text):
        if m.start() > start:
            yield start, m.start()
        start = m.end()
    if start < len(text):
        yield start, len(text)


def extract_events(text: str, ner_entities: list) -> list:
    """text + thực thể NER (text, label, start, end) -> danh sách sự kiện.

    Mỗi sự kiện: {"event_type", "trigger": {text, event_type, start, end},
                  "arguments": [{"role", "entity"}]}
    Vị trí start/end tính trên toàn bộ text đầu vào.
    """
    entities = sorted(ner_entities, key=lambda e: (e.get("start", 0), e.get("end", 0)))
    events = []
    for s_start, s_end in _sentences(text):
        sentence = text[s_start:s_end]
        local = []
        for i, e in enumerate(entities):
            if e.get("start", -1) >= s_start and e.get("end", -1) <= s_end:
                local.append({"id": f"e{i}", "start": e["start"] - s_start, "end": e["end"] - s_start,
                              "text": e.get("text", text[e["start"]:e["end"]]), "label": e.get("label"),
                              "_orig": e})
        triggers = find_triggers(sentence, local)
        relations = link_arguments(sentence, triggers, local)
        by_id = {e["id"]: e for e in local}
        for t in triggers:
            events.append({
                "event_type": t["label"],
                "trigger": {"text": t["text"], "event_type": t["label"],
                            "start": t["start"] + s_start, "end": t["end"] + s_start},
                "arguments": [{"role": r["role"], "entity": by_id[r["arg_id"]]["_orig"]}
                              for r in relations if r["trigger_id"] == t["id"]],
            })
    return events
