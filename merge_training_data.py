import csv
import json
from pathlib import Path

root = Path("server/datasets")
old_csv = root / "train.csv"
new_csv = root / "draft_labeled.csv"
out_csv = root / "train_expanded.csv"
out_jsonl = root / "processed" / "train_expanded.jsonl"

def norm(text):
    return " ".join((text or "").split()).casefold()

with old_csv.open(encoding="utf-8-sig", newline="") as f:
    old_rows = list(csv.DictReader(f))

with new_csv.open(encoding="utf-8-sig", newline="") as f:
    new_rows = list(csv.DictReader(f))

merged = []
seen = set()

for row in old_rows + new_rows:
    sentence = (row.get("sentence") or "").strip()
    entities = (row.get("entities") or "").strip()

    if not sentence or entities == "PREDICTION_ERROR":
        continue

    key = norm(sentence)
    if key in seen:
        continue

    seen.add(key)
    merged.append({"sentence": sentence, "entities": entities})

with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["sentence", "entities"])
    writer.writeheader()
    writer.writerows(merged)

out_jsonl.parent.mkdir(parents=True, exist_ok=True)
with out_jsonl.open("w", encoding="utf-8") as f:
    for row in merged:
        entities = []
        if row["entities"] != "NONE":
            for item in row["entities"].split(";"):
                item = item.strip()
                if "|" not in item:
                    continue
                text, label = item.rsplit("|", 1)
                entities.append({"text": text.strip(), "label": label.strip()})

        f.write(json.dumps({
            "sentence": row["sentence"],
            "entities": entities
        }, ensure_ascii=False) + "\n")

print("Train cu:", len(old_rows))
print("Du lieu moi:", len(new_rows))
print("Train mo rong:", len(merged))
print("Da tao:", out_jsonl)
