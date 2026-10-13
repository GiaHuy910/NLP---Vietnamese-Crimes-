import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.src.ner_pipeline.schema import (
    AnnotatedExample,
    Mention,
    parse_entities,
)
from server.src.ner_pipeline.alignment import align_example
from server.src.ner_pipeline.dataset import resolve_split_csv

INPUTS = [
    "ready/overlap_fixed/train_ner_labeled.csv",
    "ready/overlap_fixed/val_ner_labeled.csv",
    "ready/overlap_fixed/test_ner_labeled.csv",
]
REPORT = ROOT / "server" / "ner_errors.txt"


def check_file(relative_path):
    errors = []
    total = 0

    try:
        path = resolve_split_csv(relative_path)
    except Exception as exc:
        return 0, [f"[PATH ERROR] {relative_path}: {exc}\n"]

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            if not reader.fieldnames or not {
                "sentence", "entities"
            }.issubset(reader.fieldnames):
                return 0, [f"[CSV FORMAT] {path}: thiếu cột sentence/entities\n"]

            for row in reader:
                total += 1
                line = reader.line_num
                sentence = (row.get("sentence") or "").strip()
                entity_text = row.get("entities") or ""

                try:
                    if not sentence:
                        raise ValueError("sentence rỗng")

                    parsed = parse_entities(entity_text, row_number=line)
                    mentions = []
                    cursor = 0

                    for text, label in parsed:
                        start = sentence.find(text, cursor)
                        if start < 0:
                            start = sentence.find(text)

                        if start < 0:
                            raise ValueError(
                                f"Entity {text!r} [{label}] không xuất hiện trong câu"
                            )

                        end = start + len(text)
                        mentions.append(
                            Mention(
                                text=text,
                                label=label,
                                start=start,
                                end=end,
                            )
                        )
                        cursor = end

                    example = AnnotatedExample(
                        sentence=sentence,
                        mentions=tuple(mentions),
                    )
                    align_example(example, row_number=line)

                except Exception as exc:
                    errors.append(
                        f"\n[ERROR]\nFile: {path}\n"
                        f"CSV line: {line}\n"
                        f"Sentence: {sentence!r}\n"
                        f"Entities: {entity_text!r}\n"
                        f"Error: {type(exc).__name__}: {exc}\n"
                    )

    except Exception as exc:
        errors.append(f"\n[FILE ERROR] {path}\n{type(exc).__name__}: {exc}\n")

    return total, errors


def main():
    all_errors = []
    total_rows = 0

    for item in INPUTS:
        print(f"\nChecking: {item}")
        count, errors = check_file(item)
        total_rows += count
        all_errors.extend(errors)
        print(f"Rows checked: {count} | Errors: {len(errors)}")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", encoding="utf-8") as f:
        f.write(f"Total rows checked: {total_rows}\n")
        f.write(f"Total errors: {len(all_errors)}\n")
        f.write("=" * 80 + "\n")
        f.writelines(all_errors)

    print("\n===== SUMMARY =====")
    print(f"Total rows: {total_rows}")
    print(f"Total errors: {len(all_errors)}")
    print(f"Report saved to: {REPORT}")


if __name__ == "__main__":
    main()
