
from typing import Iterable
from .schema import ENTITY_TYPES, normalize_entity_label
Span = tuple[int, int, str]

def metrics_from_spans(
    gold: Iterable[Span],
    predicted: Iterable[Span]
) -> dict[str, float | int]:
    gold_set = set(gold)
    predicted_set = set(predicted)

    tp = len(gold_set & predicted_set)
    fp = len(predicted_set - gold_set)
    fn = len(gold_set - predicted_set)

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall else 0.0
    )

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "support": len(gold_set),
    }



def score_spans(
    gold: list[list[Span]],
    predicted: list[list[Span]]
) -> dict[str, dict[str, float | int]]:
    if len(gold) != len(predicted):
        raise ValueError("Gold và prediction cần cùng số lượng câu.")

    scores = {}

    for entity_type in ("overall", *ENTITY_TYPES):
        tp = fp = fn = support = 0

        for gold_sentence, predicted_sentence in zip(gold, predicted):
            if entity_type == "overall":
                gold_set = set(gold_sentence)
                predicted_set = set(predicted_sentence)
            else:
                gold_set = {
                    span for span in gold_sentence
                    if span[2] == entity_type
                }
                predicted_set = {
                    span for span in predicted_sentence
                    if span[2] == entity_type
                }

            tp += len(gold_set & predicted_set)
            fp += len(predicted_set - gold_set)
            fn += len(gold_set - predicted_set)
            support += len(gold_set)

        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall else 0.0
        )

        scores[entity_type] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }

    return scores


def spans_from_bio(
    offsets: list[list[int]], labels: list[str]
) -> list[Span]:
    if len(offsets) != len(labels):
        raise ValueError(
            "So luong offsets va BIO labels khong khop."
        )

    spans: list[Span] = []
    start = None
    end = None
    current_type = None

    def close_span():
        nonlocal start, end, current_type

        if start is not None and end is not None and current_type is not None:
            spans.append((start, end, current_type))

        start = end = current_type = None

    for offset, tag in zip(offsets, labels):
        if len(offset) != 2:
            raise ValueError(f"Offset khong hop le: {offset}")

        token_start, token_end = map(int, offset)

        if token_start < 0 or token_end <= token_start:
            raise ValueError(f"Offset khong hop le: {offset}")

        if tag == "O":
            close_span()
            continue

        parts = tag.split("-", maxsplit=1)

        if len(parts) != 2:
            raise ValueError(f"BIO label khong hop le: {tag}")

        prefix, entity_type = parts

        if prefix not in ("B", "I") or entity_type not in ENTITY_TYPES:
            raise ValueError(f"BIO label khong hop le: {tag}")

        if prefix == "B":
            close_span()
            start, end, current_type = (
                token_start, token_end, entity_type
            )

        elif current_type != entity_type or start is None:
            close_span()
            start, end, current_type = (
                token_start, token_end, entity_type
            )

        else:
            if token_start < end:
                raise ValueError(
                    "Offset token trong entity bi chong lan."
                )

            # Cho phep khoang trang giua cac token.
            end = token_end

    close_span()
    return spans

def spans_from_record(record: dict[str, object]) -> list[Span]:
    entities = record.get("entities", [])

    if not isinstance(entities, list):
        raise ValueError("'entities' phải là một danh sách.")

    spans: list[Span] = []

    for entity in entities:
        if not isinstance(entity, dict):
            raise ValueError(f"Entity không hợp lệ: {entity}")

        try:
            start = int(entity["start"])
            end = int(entity["end"])
            raw_label = str(entity["label"]).strip().upper()
            label = normalize_entity_label(raw_label)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Entity thiếu start/end/label hoặc sai định dạng: {entity}"
            ) from exc

        if start < 0 or end <= start:
            raise ValueError(f"Span không hợp lệ: {entity}")

        if label not in ENTITY_TYPES:
            raise ValueError(f"Entity label không hợp lệ: {label}")

        spans.append((start, end, label))

    return spans