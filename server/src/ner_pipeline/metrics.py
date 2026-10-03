from typing import Iterable

from .schema import ENTITY_TYPES


Span = tuple[int, int, str]


def metrics_from_spans(
    gold: Iterable[Span], predicted: Iterable[Span]
) -> dict[str, float | int]:
    gold_set, predicted_set = set(gold), set(predicted)
    true_positive = len(gold_set & predicted_set)
    false_positive = len(predicted_set - gold_set)
    false_negative = len(gold_set - predicted_set)
    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 0.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 0.0
    )
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "support": len(gold_set),
    }


def score_spans(
    gold: list[list[Span]], predicted: list[list[Span]]
) -> dict[str, dict[str, float | int]]:
    if len(gold) != len(predicted):
        raise ValueError("Gold và prediction cần cùng số lượng câu.")

    scores: dict[str, dict[str, float | int]] = {}
    for entity_type in ("overall", *ENTITY_TYPES):
        true_positive = false_positive = false_negative = support = 0
        for gold_spans, predicted_spans in zip(gold, predicted):
            if entity_type == "overall":
                gold_set, predicted_set = set(gold_spans), set(predicted_spans)
            else:
                gold_set = {span for span in gold_spans if span[2] == entity_type}
                predicted_set = {
                    span for span in predicted_spans if span[2] == entity_type
                }
            true_positive += len(gold_set & predicted_set)
            false_positive += len(predicted_set - gold_set)
            false_negative += len(gold_set - predicted_set)
            support += len(gold_set)
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        scores[entity_type] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
    return scores


def spans_from_record(record: dict[str, object]) -> list[Span]:
    entities = record["entities"]
    return [
        (int(item["start"]), int(item["end"]), str(item["label"]))
        for item in entities
    ]


def spans_from_bio(
    offsets: list[list[int]], labels: list[str]
) -> list[Span]:
    spans: list[Span] = []
    start: int | None = None
    end: int | None = None
    current_type: str | None = None

    def close_span() -> None:
        if start is not None and end is not None and current_type is not None:
            spans.append((start, end, current_type))

    for offset, tag in zip(offsets, labels):
        token_start, token_end = int(offset[0]), int(offset[1])
        if tag == "O":
            close_span()
            start = end = current_type = None
            continue
        prefix, entity_type = tag.split("-", maxsplit=1)
        if prefix == "B" or entity_type != current_type:
            close_span()
            start, end, current_type = token_start, token_end, entity_type
        else:
            end = token_end
    close_span()
    return spans
