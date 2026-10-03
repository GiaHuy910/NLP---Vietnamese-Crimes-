import csv
from dataclasses import dataclass
from pathlib import Path

from .errors import NERPipelineError


ENTITY_TYPES = ("PERSON", "ORGANIZATION", "LOCATION")
LABELS = (
    "O",
    "B-PERSON",
    "I-PERSON",
    "B-ORGANIZATION",
    "I-ORGANIZATION",
    "B-LOCATION",
    "I-LOCATION",
)


@dataclass(frozen=True)
class Mention:
    text: str
    label: str
    start: int
    end: int


@dataclass(frozen=True)
class AnnotatedExample:
    sentence: str
    mentions: tuple[Mention, ...]


def parse_entities(value: str, *, row_number: int) -> tuple[tuple[str, str], ...]:
    value = value.strip()
    if value.upper() == "NONE":
        return ()
    if not value:
        raise NERPipelineError(
            f"Dòng {row_number}: entities phải là NONE hoặc danh sách TEXT|LABEL."
        )

    parsed: list[tuple[str, str]] = []
    for item in value.split(";"):
        item = item.strip()
        if not item or "|" not in item:
            raise NERPipelineError(
                f"Dòng {row_number}: entity phải có định dạng TEXT|LABEL."
            )
        text, label = item.rsplit("|", maxsplit=1)
        text, label = text.strip(), label.strip().upper()
        if not text:
            raise NERPipelineError(f"Dòng {row_number}: entity không được để trống.")
        if label not in ENTITY_TYPES:
            raise NERPipelineError(
                f"Dòng {row_number}: nhãn {label!r} không hợp lệ; "
                f"chỉ chấp nhận {', '.join(ENTITY_TYPES)}."
            )
        parsed.append((text, label))
    return tuple(parsed)


def read_annotated_csv(path: Path) -> list[AnnotatedExample]:
    examples: list[AnnotatedExample] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None or not {"sentence", "entities"}.issubset(
                reader.fieldnames
            ):
                raise NERPipelineError(
                    f"{path.name}: CSV cần có hai cột sentence,entities."
                )

            for row in reader:
                row_number = reader.line_num
                sentence = (row.get("sentence") or "").strip()
                if not sentence:
                    raise NERPipelineError(
                        f"{path.name}, dòng {row_number}: sentence không được để trống."
                    )
                entities = parse_entities(
                    row.get("entities") or "", row_number=row_number
                )
                examples.append(
                    AnnotatedExample(
                        sentence=sentence,
                        mentions=tuple(
                            Mention(text=text, label=label, start=-1, end=-1)
                            for text, label in entities
                        ),
                    )
                )
    except OSError as exc:
        raise NERPipelineError(f"Không thể đọc dataset {path}: {exc}") from exc
    except csv.Error as exc:
        raise NERPipelineError(
            f"CSV không hợp lệ tại {path.name}, gần dòng {reader.line_num}: {exc}"
        ) from exc

    if not examples:
        raise NERPipelineError(
            f"{path.name}: CSV không có dòng annotation nào để xử lý."
        )
    return examples
