
import re

TRIGGER_DICT = {
    "bắt tạm giam": "ARREST",
    "bắt giữ": "ARREST",
    "bắt giam": "ARREST",
    "bắt": "ARREST",
    "khởi tố": "PROSECUTE",
    "tuyên phạt": "SENTENCE",
    "xử phạt": "FINE",
    "tạm giữ": "DETAIN",
}


import re


def _sentence_bounds(text: str, position: int) -> tuple[int, int]:
    """Tìm phạm vi câu chứa vị trí position."""
    left = max(
        text.rfind(".", 0, position),
        text.rfind("!", 0, position),
        text.rfind("?", 0, position),
        text.rfind("\n", 0, position),
    ) + 1

    ends = [
        p for p in (
            text.find(".", position),
            text.find("!", position),
            text.find("?", position),
            text.find("\n", position),
        )
        if p != -1
    ]
    right = min(ends) + 1 if ends else len(text)

    return left, right


def extract_events(text: str, ner_entities: list) -> list:
    events = []
    found_triggers = []

    # 1. Tìm Trigger
    for keyword, event_type in TRIGGER_DICT.items():
        pattern = r"(?<!\w)" + re.escape(keyword) + r"(?!\w)"

        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            found_triggers.append({
                "text": text[match.start():match.end()],
                "event_type": event_type,
                "start": match.start(),
                "end": match.end(),
            })

    # Ưu tiên Trigger dài hơn khi các Trigger chồng lấn
    found_triggers.sort(
        key=lambda t: (-(t["end"] - t["start"]), t["start"])
    )

    filtered_triggers = []

    for trigger in found_triggers:
        overlaps = any(
            trigger["start"] < existing["end"]
            and trigger["end"] > existing["start"]
            for existing in filtered_triggers
        )

        if not overlaps:
            filtered_triggers.append(trigger)

    filtered_triggers.sort(key=lambda t: t["start"])

    # 2. Chuẩn hóa thứ tự thực thể
    entities = sorted(
        ner_entities,
        key=lambda e: (e.get("start", 0), e.get("end", 0)),
    )

    # 3. Gán arguments trong phạm vi câu chứa Trigger
    for trigger in filtered_triggers:
        sentence_start, sentence_end = _sentence_bounds(
            text, trigger["start"]
        )

        local_entities = [
            entity for entity in entities
            if entity.get("start", 0) >= sentence_start
            and entity.get("end", 0) <= sentence_end
        ]

        arguments = []

        # Cơ quan: ưu tiên tổ chức xuất hiện trước Trigger
        organizations = [
            entity for entity in local_entities
            if entity.get("label") == "ORGANIZATION"
            and entity.get("end", 0) <= trigger["start"]
        ]

        if organizations:
            arguments.append({
                "role": "CO_QUAN",
                "entity": organizations[-1],
            })

        # Đối tượng: lấy tất cả PERSON phía sau Trigger
        # trong cùng câu; nếu không có thì lấy PERSON gần nhất phía trước.
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
            arguments.append({
                "role": "DOI_TUONG",
                "entity": person,
            })

        # Thời gian / mức án: chỉ lấy trong cùng câu.
        for entity in local_entities:
            if entity.get("label") not in ("TIME", "DATE/TIME"):
                continue

            entity_text = entity.get("text", "").lower()

            if (
                trigger["event_type"] == "SENTENCE"
                and re.search(r"\b(tù|tù giam|án tù)\b", entity_text)
            ):
                role = "MUC_AN"
            else:
                role = "THOI_GIAN"

            # Chỉ thêm thời gian gần Trigger nhất nếu có nhiều ứng viên
            arguments.append({
                "role": role,
                "entity": entity,
            })

        if arguments:
            events.append({
                "event_type": trigger["event_type"],
                "trigger": trigger,
                "arguments": arguments,
            })

    return events