import csv
import sys
from pathlib import Path

from server.src.ner_pipeline.phobert import predict_sentence

ROOT = Path(__file__).resolve().parent
INPUT_FILE = ROOT / "server" / "datasets" / "draft_review.csv"
OUTPUT_FILE = ROOT / "server" / "datasets" / "draft_labeled.csv"


def format_entities(entities):
    if not entities:
        return "NONE"

    return "; ".join(
        f"{item['text']}|{item['label']}"
        for item in entities
    )


def main():
    if not INPUT_FILE.exists():
        print(f"Khong tim thay file: {INPUT_FILE}")
        return 1

    with INPUT_FILE.open(
        "r", encoding="utf-8-sig", newline=""
    ) as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames or "sentence" not in reader.fieldnames:
            print("CSV phai co cot sentence.")
            return 1

        rows = list(reader)

    results = []

    for i, row in enumerate(rows, start=1):
        sentence = (row.get("sentence") or "").strip()

        if not sentence:
            entities = "NONE"
        else:
            try:
                predictions = predict_sentence(
                    sentence, max_length=256
                )
                entities = format_entities(predictions)
            except Exception as exc:
                print(f"Loi dong {i}: {exc}")
                entities = "PREDICTION_ERROR"

        results.append({
            "sentence": row.get("sentence", ""),
            "entities": entities,
        })

        if i % 25 == 0 or i == len(rows):
            print(f"Da xu ly {i}/{len(rows)} cau")

    with OUTPUT_FILE.open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=["sentence", "entities"]
        )
        writer.writeheader()
        writer.writerows(results)

    errors = sum(
        row["entities"] == "PREDICTION_ERROR"
        for row in results
    )

    print("\nHoan tat!")
    print(f"Tong so cau: {len(results)}")
    print(f"So cau loi: {errors}")
    print(f"File da tao: {OUTPUT_FILE}")
    print("Nhan du doan can duoc kiem tra truoc khi train tiep.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
