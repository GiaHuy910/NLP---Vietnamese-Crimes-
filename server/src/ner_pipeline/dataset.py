import json
import random
import unicodedata
import csv
import difflib
from pathlib import Path

from sympy import sequence

from .alignment import align_example
from .errors import NERPipelineError
from .paths import DATASET_DIR, PROCESSED_DIR, RAW_DIR, SERVER_DIR
from .schema import read_annotated_csv

# Package directory: server/src/ner_pipeline.
PACKAGE_DIR = Path(__file__).resolve().parent

# Server directory.
SERVER_DIR = PACKAGE_DIR.parents[1]

# Baseline rules file.
RULES_PATH = SERVER_DIR / "datasets" / "rules.json"

def safe_save_dataset(dataframe, filename, output_dir=PROCESSED_DIR):
    """Save a dataset safely and never overwrite files in the raw-data directory."""
    out_path = Path(output_dir)
    
    # Check whether the output path could overwrite original data.
    if RAW_DIR in out_path.parents or out_path == RAW_DIR:
        raise PermissionError(f"CRITICAL: KhÃ´ng Ä‘Æ°á»£c phÃ©p ghi Ä‘Ã¨ file vÃ o thÆ° má»¥c raw gá»‘c ({RAW_DIR}).")
        
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / filename
    
    # Save the file (assuming a pandas DataFrame).
    dataframe.to_csv(file_path, index=False, encoding="utf-8")
    print(f"ÄÃ£ lÆ°u an toÃ n: {file_path}")
    
def resolve_input_csv(path: str | None) -> Path:
    if path:
        candidate = Path(path)
        if not candidate.is_absolute():
            if candidate.parts and candidate.parts[0].casefold() == "datasets":
                candidate = SERVER_DIR / candidate
            else:
                candidate = DATASET_DIR / candidate
        candidate = candidate.resolve()
        try:
            candidate.relative_to(DATASET_DIR.resolve())
        except ValueError as exc:
            raise NERPipelineError(
                "Dataset Ä‘áº§u vÃ o pháº£i náº±m trong server/datasets/."
            ) from exc
        if not candidate.is_file() or candidate.suffix.lower() != ".csv":
            raise NERPipelineError(
                f"KhÃ´ng tÃ¬m tháº¥y CSV Ä‘áº§u vÃ o trong server/datasets/: {candidate.name}"
            )
        return candidate

    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    candidates = sorted(DATASET_DIR.glob("*.csv"))
    if not candidates:
        raise NERPipelineError(
            "Dataset chÆ°a Ä‘Æ°á»£c cung cáº¥p, vui lÃ²ng Ä‘áº·t dataset annotation dáº¡ng CSV "
            "vÃ o server/datasets/ trÆ°á»›c khi cháº¡y bÆ°á»›c nÃ y."
        )
    if len(candidates) > 1:
        names = ", ".join(path.name for path in candidates)
        raise NERPipelineError(
            f"CÃ³ nhiá»u file CSV trong server/datasets/ ({names}); "
            "hÃ£y chá»‰ rÃµ báº±ng --input."
        )
    return candidates[0]


def resolve_split_csv(path: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        if candidate.parts and candidate.parts[0].casefold() == "datasets":
            candidate = SERVER_DIR / candidate
        else:
            candidate = DATASET_DIR / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(DATASET_DIR.resolve())
    except ValueError as exc:
        raise NERPipelineError(
            "Dataset Ä‘áº§u vÃ o pháº£i náº±m trong server/datasets/."
        ) from exc
    if not candidate.is_file() or candidate.suffix.lower() != ".csv":
        raise NERPipelineError(
            f"KhÃ´ng tÃ¬m tháº¥y CSV split trong server/datasets/: {candidate.name}"
        )
    return candidate


def create_records(input_csv: Path) -> list[dict[str, object]]:
    examples = read_annotated_csv(input_csv)
    return [
        align_example(example, row_number=index)
        for index, example in enumerate(examples, start=2)
    ]

def sentence_key(sentence: str) -> str:
    normalized = unicodedata.normalize("NFC", sentence)
    return " ".join(normalized.split()).casefold()


def _annotation_key(record: dict[str, object]) -> list[tuple[str, str]]:
    return sorted(
        (
            sentence_key(str(entity["text"])),
            str(entity["label"]),
        )
        for entity in record["entities"]
    )


# --- P0 FIX: Fuzzy string similarity check ---
def _is_similar(str1: str, str2: str, threshold: float = 0.85) -> bool:
    """Return whether two sentences have similarity greater than threshold.

    A threshold of 0.85 captures sentences with small differences such as abbreviations or typos.
    """
    # If either string is shorter than 10 characters, require an exact match.
    if len(str1) < 10 or len(str2) < 10:
        return str1 == str2
    return difflib.SequenceMatcher(None, str1, str2).ratio() > threshold


def deduplicate_records(
    records: list[dict[str, object]],
) -> list[dict[str, object]]:
    unique_records = []
    
    for record in records:
        sentence = str(record["sentence"])
        normalized_sentence = sentence_key(sentence)
        is_duplicate = False
        
        for unique in unique_records:
            unique_normalized = sentence_key(str(unique["sentence"]))
            
            # Check for exact or fuzzy duplicates.
            if normalized_sentence == unique_normalized or _is_similar(normalized_sentence, unique_normalized):
                is_duplicate = True
                
                # Raise an error if identical sentences have conflicting annotations.
                if normalized_sentence == unique_normalized and _annotation_key(unique) != _annotation_key(record):
                    raise NERPipelineError(
                        f"CÃ³ cÃ¢u trÃ¹ng láº·p nhÆ°ng annotation khÃ¡c nhau; hÃ£y xá»­ lÃ½ "
                        f"mÃ¢u thuáº«n trÆ°á»›c khi chia dataset: {sentence!r}"
                    )
                break
                
        if not is_duplicate:
            unique_records.append(record)
            
    return unique_records


def ensure_splits_disjoint(
    splits: dict[str, list[dict[str, object]]],
) -> None:
    seen = [] # Tuples of (normalized_sentence, split_name).
    
    for split_name, records in splits.items():
        for record in records:
            normalized_sentence = sentence_key(str(record["sentence"]))
            
            for seen_sentence, previous_split in seen:
                
                if normalized_sentence == seen_sentence or _is_similar(normalized_sentence, seen_sentence):
                    if previous_split == split_name:
                        raise NERPipelineError(
                            f"Duplicate sentence appears more than once in {split_name}."
                        )
                    
                    raise NERPipelineError(
              f"Sentence appears in both train and test: {sequence!r}"
)
            
            seen.append((normalized_sentence, split_name))


def save_jsonl(records: list[dict[str, object]], path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as file:
            for record in records:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise NERPipelineError(f"KhÃ´ng thá»ƒ ghi split dataset {path}: {exc}") from exc


def save_annotation_csv(records: list[dict[str, object]], path: Path) -> None:
    try:
        with path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["sentence", "entities"])
            writer.writeheader()
            for record in records:
                mentions = sorted(
                    record["entities"], key=lambda entity: (entity["start"], entity["end"])
                )
                entities = "; ".join(
                    f"{entity['text']}|{entity['label']}" for entity in mentions
                ) or "NONE"
                writer.writerow(
                    {"sentence": record["sentence"], "entities": entities}
                )
    except OSError as exc:
        raise NERPipelineError(
            f"KhÃ´ng thá»ƒ ghi annotation CSV {path}: {exc}"
        ) from exc


def save_bio_csv(records: list[dict[str, object]], path: Path) -> None:
    try:
        with path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "sentence_id",
                    "token_index",
                    "token",
                    "label",
                    "start",
                    "end",
                ],
            )
            writer.writeheader()
            for sentence_id, record in enumerate(records, start=1):
                for token_index, (token, label, offset) in enumerate(
                    zip(
                        record["tokens"],
                        record["labels"],
                        record["token_offsets"],
                    ),
                    start=1,
                ):
                    writer.writerow(
                        {
                            "sentence_id": sentence_id,
                            "token_index": token_index,
                            "token": token,
                            "label": label,
                            "start": offset[0],
                            "end": offset[1],
                        }
                    )
    except OSError as exc:
        raise NERPipelineError(f"KhÃ´ng thá»ƒ ghi BIO CSV {path}: {exc}") from exc


def save_dataset_splits(
    splits: dict[str, list[dict[str, object]]],
) -> None:
    output_names = {
        "train": ("train.csv", "train_bio.csv"),
        "validation": ("valid.csv", "valid_bio.csv"),
        "test": ("test.csv", "test_bio.csv"),
    }
    for split_name, records in splits.items():
        annotation_name, bio_name = output_names[split_name]
        save_jsonl(records, PROCESSED_DIR / f"{split_name}.jsonl")
        save_annotation_csv(records, DATASET_DIR / annotation_name)
        save_bio_csv(records, DATASET_DIR / bio_name)



def load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        raise NERPipelineError(
            f"Chưa có split dataset tại {path}. Dataset chưa được cung cấp hoặc "
            "chưa preprocessing; đặt CSV annotation vào server/datasets/ rồi chạy "
            "lệnh prepare."
        )

    try:
        with path.open("r", encoding="utf-8") as file:
            records = []

            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue

                try:
                    record = json.loads(line)

                    # Normalize entity labels in legacy data.
                    for entity in record.get("entities", []):
                        if not isinstance(entity, dict):
                            continue

                        old_label = str(entity.get("label", "")).strip().upper()

                        if old_label in {"TIME", "TIME"}:
                            entity["label"] = "TIME"

                    # Normalize legacy BIO labels.
                    if isinstance(record.get("labels"), list):
                        normalized_labels = []

                        for tag in record["labels"]:
                            if not isinstance(tag, str):
                                normalized_labels.append(tag)
                                continue

                            tag = tag.replace(
                                "B-DATE/TIME", "B-TIME"
                            ).replace(
                                "I-DATE/TIME", "I-TIME"
                            ).replace(
                                "B-DATE_TIME", "B-TIME"
                            ).replace(
                                "I-DATE_TIME", "I-TIME"
                            )

                            normalized_labels.append(tag)

                        record["labels"] = normalized_labels

                    records.append(record)

                except json.JSONDecodeError as exc:
                    raise NERPipelineError(
                        f"JSONL không hợp lệ tại {path.name}, "
                        f"dòng {line_number}: {exc}"
                    ) from exc

    except OSError as exc:
        raise NERPipelineError(
            f"Không thể đọc split dataset {path}: {exc}"
        ) from exc

    if not records:
        raise NERPipelineError(f"Split dataset rỗng: {path}")

    return records

def prepare_dataset(
    input_path: str | None,
    *,
    seed: int,
    test_ratio: float,
    validation_ratio: float,
    train_only_path: str | None = None,
) -> dict[str, int]:
    if test_ratio <= 0 or validation_ratio <= 0 or test_ratio + validation_ratio >= 1:
        raise NERPipelineError(
            "Tá»· lá»‡ test vÃ  validation pháº£i > 0, Ä‘á»“ng thá»i tá»•ng nhá» hÆ¡n 1."
        )
    source = resolve_input_csv(input_path)
    aligned_records = create_records(source)
    records = deduplicate_records(aligned_records) # Remove fuzzy duplicates.
    unique_count = len(records)
    train_only_records: list[dict[str, object]] = []
    
    if train_only_path:
        train_only_source = resolve_split_csv(train_only_path)
        known_records = deduplicate_records(create_records(train_only_source))
        records_by_key = {sentence_key(str(row["sentence"])): row for row in records}
        for known in known_records:
            key = sentence_key(str(known["sentence"]))
            current = records_by_key.get(key)
            if current is None or _annotation_key(current) != _annotation_key(known):
                raise NERPipelineError(
                    f"Training-only sentence {known['sentence']!r} khÃ´ng khá»›p "
                    "corpus nguá»“n."
                )
            train_only_records.append(current)
            
        train_only_keys = {
            sentence_key(str(record["sentence"])) for record in train_only_records
        }
        records = [
            record
            for record in records
            if sentence_key(str(record["sentence"])) not in train_only_keys
        ]

    count = len(records)
    if count < 3:
        raise NERPipelineError(
            f"Chá»‰ cÃ²n {count} cÃ¢u ngoÃ i training-only; cáº§n Ã­t nháº¥t 3 cÃ¢u Ä‘á»ƒ táº¡o "
            "train/validation/test riÃªng biá»‡t."
        )

    shuffled = records.copy()
    random.Random(seed).shuffle(shuffled)
    test_count = max(1, round(count * test_ratio))
    validation_count = max(1, round(count * validation_ratio))
    while test_count + validation_count >= count:
        if validation_count >= test_count and validation_count > 1:
            validation_count -= 1
        elif test_count > 1:
            test_count -= 1
        else:
            raise NERPipelineError(
                "Dataset quÃ¡ nhá» Ä‘á»ƒ giá»¯ riÃªng train, validation vÃ  test."
            )

    test_records = shuffled[:test_count]
    validation_records = shuffled[test_count : test_count + validation_count]
    train_records = train_only_records + shuffled[test_count + validation_count :]
    splits = {
        "train": train_records,
        "validation": validation_records,
        "test": test_records,
    }
    
    # Check for fuzzy leakage between splits before saving.
    ensure_splits_disjoint(splits)
    
    save_dataset_splits(splits)

    return {
        "unique_examples": unique_count,
        "train": len(train_records),
        "validation": len(validation_records),
        "test": len(test_records),
        "duplicates_removed": len(aligned_records) - unique_count,
        "training_only_examples": len(train_only_records),
        "overlapping_entities_removed": sum(
            int(record["overlapping_entities_removed"]) for record in aligned_records
        ),
    }


def prepare_predefined_splits(
    train_path: str, validation_path: str, test_path: str
) -> dict[str, int]:
    input_paths = {
        "train": resolve_split_csv(train_path),
        "validation": resolve_split_csv(validation_path),
        "test": resolve_split_csv(test_path),
    }
    examples = {
        split: read_annotated_csv(path) for split, path in input_paths.items()
    }
    
    ensure_splits_disjoint(
        {
            split: [{"sentence": example.sentence} for example in split_examples]
            for split, split_examples in examples.items()
        }
    )
    
    aligned = {
        split: [
            align_example(example, row_number=index)
            for index, example in enumerate(split_examples, start=2)
        ]
        for split, split_examples in examples.items()
    }
    splits = {
        split: deduplicate_records(records) for split, records in aligned.items()
    }
    
    ensure_splits_disjoint(splits)
    
    for split_name, records in splits.items():
        if not records:
            raise NERPipelineError(f"Split {split_name} khÃ´ng cÃ³ cÃ¢u há»£p lá»‡.")
            
    save_dataset_splits(splits)
    
    return {
        split: len(records)
        for split, records in splits.items()
    } | {
        f"{split}_duplicates_removed": len(aligned[split]) - len(splits[split])
        for split in splits
    }
