
from __future__ import annotations
from .phobert import predict_sentence
import argparse
import json
from pathlib import Path
from typing import Any


from .event_module import detect_triggers


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load gold examples from a JSONL file."""
    records = []

    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON at {path}:{line_number}: {exc}"
                ) from exc

            if not isinstance(record, dict):
                raise ValueError(
                    f"Expected an object at {path}:{line_number}"
                )

            if not isinstance(record.get("sentence"), str):
                raise ValueError(
                    f"Missing or invalid 'sentence' at "
                    f"{path}:{line_number}"
                )

            records.append(record)

    return records


def find_text_span(
    sentence: str,
    text: str,
    used_spans: set[tuple[int, int]] | None = None,
) -> tuple[int, int] | None:
    """Find a trigger occurrence, preserving repeated occurrences."""
    if not text:
        return None

    if used_spans is None:
        used_spans = set()

    start = 0
    while True:
        start = sentence.find(text, start)
        if start < 0:
            return None

        end = start + len(text)
        if (start, end) not in used_spans:
            return start, end

        start += 1


def normalize_trigger(
    item: dict[str, Any],
    sentence: str,
    used_spans: set[tuple[int, int]] | None = None,
) -> tuple[int, int, str] | None:
    """
    Normalize a trigger into (start, end, event_type).

    Supported span keys: start/end or trigger_start/trigger_end.
    Supported text keys: text or trigger.
    Supported type keys: event_type or type.
    """
    event_type = item.get(
    "event_type",
    item.get("type", item.get("label")),
)
    if not isinstance(event_type, str) or not event_type.strip():
        return None

    start = item.get("start", item.get("trigger_start"))
    end = item.get("end", item.get("trigger_end"))

    if isinstance(start, int) and isinstance(end, int):
        if 0 <= start < end <= len(sentence):
            return start, end, event_type.strip().upper()
        return None

    trigger_text = item.get("text", item.get("trigger"))
    if not isinstance(trigger_text, str):
        return None

    span = find_text_span(sentence, trigger_text, used_spans)
    if span is None:
        return None

    return span[0], span[1], event_type.strip().upper()


def get_gold_triggers(
    record: dict[str, Any],
) -> set[tuple[int, int, str]]:
    """Read gold triggers from record['triggers']."""
    sentence = record["sentence"]
    triggers = record.get("triggers", [])

    if not isinstance(triggers, list):
        raise ValueError("'triggers' must be a list")

    result = set()
    used_spans: set[tuple[int, int]] = set()

    for item in triggers:
        if not isinstance(item, dict):
            raise ValueError("Each gold trigger must be an object")

        trigger = normalize_trigger(item, sentence, used_spans)
        if trigger is None:
            raise ValueError(
        "Invalid gold trigger: "
        f"record sentence={sentence!r}, "
        f"trigger={item!r}"
    )

        start, end, _ = trigger
        used_spans.add((start, end))
        result.add(trigger)

    return result




def get_predicted_triggers(
    sentence: str,
) -> set[tuple[int, int, str]]:
    """Predict triggers using the project's trigger detection rules."""
    triggers = detect_triggers(sentence)

    if not isinstance(triggers, list):
        raise TypeError("detect_triggers(sentence) must return a list")

    result: set[tuple[int, int, str]] = set()

    for trigger in triggers:
        if not isinstance(trigger, dict):
            continue

        start = trigger.get("start")
        end = trigger.get("end")
        event_type = trigger.get("event_type")
        text = trigger.get("text")

        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or not isinstance(event_type, str)
            or not isinstance(text, str)
        ):
            continue

        # Validate that offsets point to the exact trigger text.
        if not (0 <= start < end <= len(sentence)):
            continue

        if sentence[start:end].casefold() != text.casefold():
            continue

        result.add((start, end, event_type.strip().upper()))

    return result



def calculate_metrics(
    gold: set[tuple[int, int, str]],
    predicted: set[tuple[int, int, str]],
) -> dict[str, float | int]:
    """Exact match requires identical span and event type."""
    true_positive = len(gold & predicted)
    false_positive = len(predicted - gold)
    false_negative = len(gold - predicted)

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

    return {
        "tp": true_positive,
        "fp": false_positive,
        "fn": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def evaluate(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate trigger extraction over the whole dataset."""
    all_gold: set[tuple[int, int, str]] = set()
    all_predicted: set[tuple[int, int, str]] = set()
    per_type: dict[str, dict[str, set]] = {}
    errors = []

    for index, record in enumerate(records):
        sentence = record["sentence"]

        try:
            gold = get_gold_triggers(record)
            predicted = get_predicted_triggers(sentence)
        except Exception as exc:
            raise RuntimeError(
                f"Evaluation failed at record {index + 1}: {exc}"
            ) from exc

        # Add record index to avoid matching triggers from different
        # sentences merely because they have the same offsets and type.
        indexed_gold = {
            (index, start, end, event_type)
            for start, end, event_type in gold
        }
        indexed_predicted = {
            (index, start, end, event_type)
            for start, end, event_type in predicted
        }

        all_gold.update(indexed_gold)
        all_predicted.update(indexed_predicted)

        for _, start, end, event_type in indexed_gold:
            per_type.setdefault(
                event_type, {"gold": set(), "predicted": set()}
            )["gold"].add((index, start, end, event_type))

        for _, start, end, event_type in indexed_predicted:
            per_type.setdefault(
                event_type, {"gold": set(), "predicted": set()}
            )["predicted"].add((index, start, end, event_type))

        if indexed_gold != indexed_predicted:
            errors.append({
                "sentence": sentence,
                "gold": [
                    {"start": s, "end": e, "event_type": t}
                    for s, e, t in sorted(gold)
                ],
                "predicted": [
                    {"start": s, "end": e, "event_type": t}
                    for s, e, t in sorted(predicted)
                ],
            })

    overall = calculate_metrics(all_gold, all_predicted)

    # Compute metrics independently for each event type.
    by_type = {}
    for event_type, values in sorted(per_type.items()):
        by_type[event_type] = calculate_metrics(
            values["gold"], values["predicted"]
        )

    return {
        "num_sentences": len(records),
        "num_gold_triggers": len(all_gold),
        "num_predicted_triggers": len(all_predicted),
        "overall": overall,
        "by_type": by_type,
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate event trigger extraction with exact-span F1."
    )
    parser.add_argument(
        "--test",
        type=Path,
        required=True,
        help="Path to gold JSONL test data.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("trigger_evaluation.json"),
        help="Path for the evaluation report.",
    )
    args = parser.parse_args()

    if not args.test.is_file():
        parser.error(f"Test file not found: {args.test}")

    records = load_jsonl(args.test)
    if not records:
        parser.error("The test dataset is empty.")

    report = evaluate(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    overall = report["overall"]
    print(f"Sentences: {report['num_sentences']}")
    print(f"Gold triggers: {report['num_gold_triggers']}")
    print(f"Predicted triggers: {report['num_predicted_triggers']}")
    print(f"Precision: {overall['precision']:.4f}")
    print(f"Recall:    {overall['recall']:.4f}")
    print(f"F1:        {overall['f1']:.4f}")
    print("\nMetrics by event type:")

    for event_type, metrics in report["by_type"].items():
        print(
            f"  {event_type}: "
            f"P={metrics['precision']:.4f} "
            f"R={metrics['recall']:.4f} "
            f"F1={metrics['f1']:.4f}"
        )

    print(f"\nError cases: {len(report['errors'])}")
    print(f"Report saved to: {args.output}")


if __name__ == "__main__":
    main()
