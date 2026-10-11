import json
from pathlib import Path

from server.src.ner_pipeline.dataset import create_records, deduplicate_records
from server.src.ner_pipeline.paths import DATASET_DIR

source = DATASET_DIR / "draft_labeled.csv"
output = DATASET_DIR / "processed" / "train_expanded.jsonl"

if not source.is_file():
    raise FileNotFoundError(f"Khong tim thay file: {source}")

records = create_records(source)
records = deduplicate_records(records)

output.parent.mkdir(parents=True, exist_ok=True)

with output.open("w", encoding="utf-8", newline="\n") as f:
    for record in records:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

print("So cau:", len(records))
print("Da tao:", output)
print("Truong du lieu:", list(records[0].keys()) if records else "Rong")
