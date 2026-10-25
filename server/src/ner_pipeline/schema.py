import csv
from dataclasses import dataclass
from pathlib import Path

from .errors import NERPipelineError

ENTITY_TYPES = (
    "PERSON",
    "ORGANIZATION",
    "LOCATION",
    "TIME",
    "MONEY",
    "PRODUCT",
    "DRUG",
    "CRIME",
)

LABEL_ALIASES = {
    "PER": "PERSON",
    "ORG": "ORGANIZATION",
    "LOC": "LOCATION",
    "TIME": "TIME",
    "DATE_TIME": "TIME",
}

NER_LABELS = ENTITY_TYPES

LABELS = (
    "O",
    *(f"{prefix}-{entity}" for entity in ENTITY_TYPES
      for prefix in ("B", "I")),
)

def normalize_entity_label(label: str) -> str:
    label = label.strip().upper()

    aliases = {
        "PER": "PERSON",
        "ORG": "ORGANIZATION",
        "LOC": "LOCATION",
        "TIME": "TIME",
        "DATE/TIME": "TIME",
        "DATE_TIME": "TIME",
    }

    return aliases.get(label, label)


def normalize_bio_label(label: str) -> str:
    label = label.strip()

    if label.upper() == "O":
        return "O"

    if "-" not in label:
        return normalize_entity_label(label)

    prefix, entity = label.split("-", 1)

    if prefix.upper() in {"B", "I"}:
        return f"{prefix.upper()}-{normalize_entity_label(entity)}"

    return normalize_entity_label(label)

# Generate BIO tags automatically.
LABELS = ["O"]
for ent in ENTITY_TYPES:
    LABELS.append(f"B-{ent}")
    LABELS.append(f"I-{ent}")

LABEL2ID = {label: i for i, label in enumerate(LABELS)}
ID2LABEL = {i: label for i, label in enumerate(LABELS)}
NUM_LABELS = len(LABELS)

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
            f"DÃ²ng {row_number}: entities pháº£i lÃ  NONE hoáº·c danh sÃ¡ch TEXT|LABEL."
        )

    parsed: list[tuple[str, str]] = []
    for item in value.split(";"):
        item = item.strip()
        if not item or "|" not in item:
            raise NERPipelineError(
                f"DÃ²ng {row_number}: entity pháº£i cÃ³ Ä‘á»‹nh dáº¡ng TEXT|LABEL."
            )
        text, label = item.rsplit("|", maxsplit=1)
        text = text.strip()
        label = label.strip().upper()

        label = normalize_entity_label(label)
        if not text:
            raise NERPipelineError(f"DÃ²ng {row_number}: entity khÃ´ng Ä‘Æ°á»£c Ä‘á»ƒ trá»‘ng.")
        if label not in ENTITY_TYPES:
            raise NERPipelineError(
                f"DÃ²ng {row_number}: nhÃ£n {label!r} khÃ´ng há»£p lá»‡; "
                f"chá»‰ cháº¥p nháº­n {', '.join(ENTITY_TYPES)}."
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
                    f"{path.name}: CSV cáº§n cÃ³ hai cá»™t sentence,entities."
                )

            for row in reader:
                row_number = reader.line_num
                sentence = (row.get("sentence") or "").strip()
                if not sentence:
                    raise NERPipelineError(
                        f"{path.name}, dÃ²ng {row_number}: sentence khÃ´ng Ä‘Æ°á»£c Ä‘á»ƒ trá»‘ng."
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
        raise NERPipelineError(f"KhÃ´ng thá»ƒ Ä‘á»c dataset {path}: {exc}") from exc
    except csv.Error as exc:
        raise NERPipelineError(
            f"CSV khÃ´ng há»£p lá»‡ táº¡i {path.name}, gáº§n dÃ²ng {reader.line_num}: {exc}"
        ) from exc

    if not examples:
        raise NERPipelineError(
            f"{path.name}: CSV khÃ´ng cÃ³ dÃ²ng annotation nÃ o Ä‘á»ƒ xá»­ lÃ½."
        )
    return examples

