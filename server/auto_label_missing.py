import re
import pandas as pd
from pathlib import Path
from collections import Counter

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from server.src.ner_pipeline.baseline import RuleBasedNER

FOLDER = Path("server/datasets")
FILES = ["train_ner.csv", "val_ner.csv"]

ALIASES = {
    "LOCATION": "LOC",
    "ORGANIZATION": "ORG",
    "TIME": "DATE/TIME",
}

VALID_LABELS = {
    "PERSON", "ORG", "LOC", "DATE/TIME", "MONEY",
    "PRODUCT", "DRUG", "LAW", "CRIME"
}

def normalize_label(label):
    label = ALIASES.get(label.strip().upper(), label.strip().upper())
    return label if label in VALID_LABELS else None

def parse_entities(value):
    result = []
    for item in value.split(";"):
        item = item.strip()
        if not item or "|" not in item:
            continue
        text, label = item.rsplit("|", 1)
        label = normalize_label(label)
        if text.strip() and label:
            result.append((text.strip(), label))
    return result

def main():
    # Thu thập thực thể từ các câu đã được gắn nhãn
    known = set()

    for filename in FILES:
        df = pd.read_csv(
            FOLDER / filename,
            encoding="utf-8-sig",
            keep_default_na=False
        )
        for value in df["entities"]:
            value = value.strip()
            if not value or value.upper() == "NONE":
                continue
            known.update(parse_entities(value))

    # Ưu tiên cụm từ dài để hạn chế khớp một phần tên
    known = sorted(known, key=lambda x: len(x[0]), reverse=True)
    baseline = RuleBasedNER()

    for filename in FILES:
        path = FOLDER / filename
        df = pd.read_csv(path, encoding="utf-8-sig", keep_default_na=False)

        output = []
        unresolved = []
        auto_count = 0

        for index, row in df.iterrows():
            sentence = row["sentence"]
            current = row["entities"].strip()

            # Giữ nguyên annotation đã có
            if current:
                output.append(current)
                continue

            candidates = []

            # 1. Tìm thực thể đã xuất hiện trong annotation mẫu
            for entity_text, label in known:
                pattern = re.escape(entity_text)
                for match in re.finditer(pattern, sentence, flags=re.IGNORECASE):
                    candidates.append((
                        match.start(),
                        match.end(),
                        sentence[match.start():match.end()],
                        label,
                        "dictionary"
                    ))

            # 2. Bổ sung dự đoán từ rule-based baseline
            try:
                predictions = baseline.predict(sentence)
            except Exception as exc:
                print(f"Baseline error at {filename}, row {index + 2}: {exc}")
                predictions = []

            for item in predictions:
                start = int(item["start"])
                end = int(item["end"])
                label = normalize_label(str(item["label"]))

                if 0 <= start < end <= len(sentence) and label:
                    candidates.append((
                        start, end, sentence[start:end], label, "baseline"
                    ))

            # Loại dự đoán trùng hoặc chồng lấn; ưu tiên span dài hơn
            candidates.sort(
                key=lambda x: (-(x[1] - x[0]), x[0], x[3])
            )

            selected = []
            for candidate in candidates:
                start, end = candidate[0], candidate[1]

                if any(
                    start < old[1] and old[0] < end
                    for old in selected
                ):
                    continue

                selected.append((start, end, candidate[2], candidate[3]))

            selected.sort(key=lambda x: x[0])

            if selected:
                output.append("; ".join(
                    f"{text}|{label}"
                    for _, _, text, label in selected
                ))
                auto_count += 1
            else:
                # Không tự suy đoán NONE khi chưa có đủ bằng chứng
                output.append("")
                unresolved.append({
                    "row_id": index + 1,
                    "sentence": sentence,
                    "entities": ""
                })

        df["entities"] = output

        out_path = FOLDER / filename.replace(
            ".csv", "_auto.csv"
        )
        df.to_csv(out_path, index=False, encoding="utf-8-sig")

        review_path = FOLDER / filename.replace(
            ".csv", "_unresolved.csv"
        )
        pd.DataFrame(
            unresolved,
            columns=["row_id", "sentence", "entities"]
        ).to_csv(review_path, index=False, encoding="utf-8-sig")

        print(f"\n{filename}")
        print("Auto-labeled:", auto_count)
        print("Still unresolved:", len(unresolved))
        print("Output:", out_path)
        print("Review:", review_path)

if __name__ == "__main__":
    main()
