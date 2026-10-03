import json
import random
import unicodedata
import csv
from pathlib import Path

from .alignment import align_example
from .errors import NERPipelineError
from .paths import DATASET_DIR, PROCESSED_DIR, SERVER_DIR
from .schema import read_annotated_csv


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
                "Dataset đầu vào phải nằm trong server/datasets/."
            ) from exc
        if not candidate.is_file() or candidate.suffix.lower() != ".csv":
            raise NERPipelineError(
                f"Không tìm thấy CSV đầu vào trong server/datasets/: {candidate.name}"
            )
        return candidate

    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    candidates = sorted(DATASET_DIR.glob("*.csv"))
    if not candidates:
        raise NERPipelineError(
            "Dataset chưa được cung cấp, vui lòng đặt dataset annotation dạng CSV "
            "vào server/datasets/ trước khi chạy bước này."
        )
    if len(candidates) > 1:
        names = ", ".join(path.name for path in candidates)
        raise NERPipelineError(
            f"Có nhiều file CSV trong server/datasets/ ({names}); "
            "hãy chỉ rõ bằng --input."
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
            "Dataset đầu vào phải nằm trong server/datasets/."
        ) from exc
    if not candidate.is_file() or candidate.suffix.lower() != ".csv":
        raise NERPipelineError(
            f"Không tìm thấy CSV split trong server/datasets/: {candidate.name}"
        )
    return candidate


def create_records(input_csv: Path) -> list[dict[str, object]]:
    examples = read_annotated_csv(input_csv)
    return [
        align_example(example, row_number=index)
        for index, example in enumerate(examples, start=2)
    ]


def sentence_key(sentence: str) -> str:
    return " ".join(unicodedata.normalize("NFC", sentence).split()).casefold()


def _annotation_key(record: dict[str, object]) -> list[tuple[str, str]]:
    return sorted(
        (
            sentence_key(str(entity["text"])),
            str(entity["label"]),
        )
        for entity in record["entities"]
    )


def deduplicate_records(
    records: list[dict[str, object]],
) -> list[dict[str, object]]:
    unique: dict[str, dict[str, object]] = {}
    for record in records:
        sentence = str(record["sentence"])
        key = sentence_key(sentence)
        previous = unique.get(key)
        if previous is not None:
            if _annotation_key(previous) != _annotation_key(record):
                raise NERPipelineError(
                    "Có câu trùng lặp nhưng annotation khác nhau; hãy xử lý "
                    "mâu thuẫn trước khi chia dataset."
                )
            continue
        unique[key] = record
    return list(unique.values())


def ensure_splits_disjoint(
    splits: dict[str, list[dict[str, object]]],
) -> None:
    seen: dict[str, str] = {}
    for split_name, records in splits.items():
        for record in records:
            key = sentence_key(str(record["sentence"]))
            previous_split = seen.get(key)
            if previous_split is not None:
                if previous_split == split_name:
                    raise NERPipelineError(
                        f"Duplicate sentence appears more than once in {split_name}."
                    )
                raise NERPipelineError(
                    f"Duplicate sentence appears in both {previous_split} and "
                    f"{split_name}; remove cross-split leakage before training."
                )
            seen[key] = split_name


def save_jsonl(records: list[dict[str, object]], path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as file:
            for record in records:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise NERPipelineError(f"Không thể ghi split dataset {path}: {exc}") from exc


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
            f"Không thể ghi annotation CSV {path}: {exc}"
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
        raise NERPipelineError(f"Không thể ghi BIO CSV {path}: {exc}") from exc


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
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise NERPipelineError(
                        f"JSONL không hợp lệ tại {path.name}, dòng {line_number}: {exc}"
                    ) from exc
    except OSError as exc:
        raise NERPipelineError(f"Không thể đọc split dataset {path}: {exc}") from exc
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
            "Tỷ lệ test và validation phải > 0, đồng thời tổng nhỏ hơn 1."
        )
    source = resolve_input_csv(input_path)
    aligned_records = create_records(source)
    records = deduplicate_records(aligned_records)
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
                    f"Training-only sentence {known['sentence']!r} không khớp "
                    "corpus nguồn."
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
            f"Chỉ còn {count} câu ngoài training-only; cần ít nhất 3 câu để tạo "
            "train/validation/test riêng biệt."
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
                "Dataset quá nhỏ để giữ riêng train, validation và test."
            )

    test_records = shuffled[:test_count]
    validation_records = shuffled[test_count : test_count + validation_count]
    train_records = train_only_records + shuffled[test_count + validation_count :]
    splits = {
        "train": train_records,
        "validation": validation_records,
        "test": test_records,
    }
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
            raise NERPipelineError(f"Split {split_name} không có câu hợp lệ.")
    save_dataset_splits(splits)
    return {
        split: len(records)
        for split, records in splits.items()
    } | {
        f"{split}_duplicates_removed": len(aligned[split]) - len(splits[split])
        for split in splits
    }
