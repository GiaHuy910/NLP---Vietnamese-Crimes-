
import argparse
import csv
import re
from pathlib import Path

from .event_module import TRIGGER_DICT


def predict_triggers(text: str) -> set[tuple[int, int, str]]:
    """Tra ve tap (start, end, event_type) du doan."""
    found = []

    for keyword, event_type in TRIGGER_DICT.items():
        pattern = r"(?<!\w)" + re.escape(keyword.lower()) + r"(?!\w)"

        for match in re.finditer(pattern, text.lower()):
            found.append((
                match.start(),
                match.end(),
                event_type,
            ))

    # Uu tien trigger dai hon va loai bo cac span chong lan
    found.sort(key=lambda x: (-(x[1] - x[0]), x[0]))

    selected = []
    for item in found:
        start, end, _ = item
        overlaps = any(
            start < old_end and end > old_start
            for old_start, old_end, _ in selected
        )
        if not overlaps:
            selected.append(item)

    return set(selected)


def gold_triggers(text: str, trigger_text: str, event_type: str):
    """Chuyen nhan gold thanh span va event type."""
    if trigger_text.strip().upper() == "NONE":
        return set()

    if event_type.strip().upper() == "NONE":
        raise ValueError(
            f"Trigger '{trigger_text}' co event_type=NONE"
        )

    spans = set()
    start = 0

    while True:
        pos = text.find(trigger_text, start)
        if pos == -1:
            break

        spans.add((pos, pos + len(trigger_text), event_type.strip()))
        start = pos + 1

    if not spans:
        raise ValueError(
            f"Khong tim thay trigger '{trigger_text}' trong: {text}"
        )

    return spans


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        default="server/datasets/trigger_test.csv",
    )
    args = parser.parse_args()

    path = Path(args.data)
    tp = fp = fn = 0

    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        required = {"sentence", "trigger_text", "event_type"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(
                "CSV phai co cac cot: sentence, trigger_text, event_type"
            )

        for row_no, row in enumerate(reader, start=2):
            text = row["sentence"]
            gold = gold_triggers(
                text,
                row["trigger_text"],
                row["event_type"],
            )
            pred = predict_triggers(text)

            correct = pred & gold
            tp += len(correct)
            fp += len(pred - gold)
            fn += len(gold - pred)

            if pred != gold:
                print(f"\nSai khac tai dong {row_no}: {text}")
                print("  Gold:", sorted(gold))
                print("  Pred:", sorted(pred))

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall else 0.0
    )

    print("\n===== TRIGGER EVALUATION =====")
    print(f"TP:        {tp}")
    print(f"FP:        {fp}")
    print(f"FN:        {fn}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1:        {f1:.4f}")


if __name__ == "__main__":
    main()
