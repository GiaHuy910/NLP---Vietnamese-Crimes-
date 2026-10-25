import json
from pathlib import Path
from .errors import NERPipelineError
from .schema import ENTITY_TYPES

ARGUMENT_TYPES = (
    "DOI_TUONG",
    "NAN_NHAN",
    "CO_QUAN",
    "TAI_SAN",
    "TANG_VAT",
    "HUNG_KHI",
    "TOI_DANH",
    "MUC_AN",
    "THOI_GIAN",
    "DIA_DIEM",
)


_DEFAULT_MAPPING = {   # Match the event-pipeline schema (src/event_pipeline/schema.py, ROLE_TYPES).
    "DOI_TUONG": ["PERSON", "ORGANIZATION"],
    "NAN_NHAN": ["PERSON", "ORGANIZATION"],
    "CO_QUAN": ["ORGANIZATION"],
    "TAI_SAN": ["MONEY", "PRODUCT"],
    "TANG_VAT": ["DRUG", "PRODUCT"],
    "HUNG_KHI": ["PRODUCT"],
    "TOI_DANH": ["CRIME"],
    "MUC_AN": ["TIME", "MONEY"],
    "THOI_GIAN": ["TIME"],
    "DIA_DIEM": ["LOCATION"],
}

_SCHEMA_PATH = Path(__file__).with_name("argument_schema.json")

def normalize_ner_label(label):
    from .schema import normalize_entity_label

    if not isinstance(label, str):
        raise NERPipelineError(f"Invalid NER label: {label!r}")

    normalized = normalize_entity_label(label)

    if normalized not in ENTITY_TYPES:
        raise NERPipelineError(f"Unknown NER label: {label}")

    return normalized

def load_argument_schema(path=None):
    schema_path = Path(path) if path is not None else _SCHEMA_PATH

    if schema_path.exists():
        try:
            with schema_path.open("r", encoding="utf-8-sig") as file:
                schema = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            raise NERPipelineError(
                f"Cannot load argument schema: {exc}"
            ) from exc
    else:
        schema = {
            "ner_labels": list(ENTITY_TYPES),
            "argument_mapping": _DEFAULT_MAPPING,
        }

    if not isinstance(schema, dict):
        raise NERPipelineError("Schema must be a JSON object")

    ner_labels = schema.get("ner_labels")
    mapping = schema.get("argument_mapping")

    if not isinstance(ner_labels, list) or len(ner_labels) != len(ENTITY_TYPES):
     raise NERPipelineError(f"Schema must contain exactly {len(ENTITY_TYPES)} NER labels")

    try:
        normalized_labels = [normalize_ner_label(label) for label in ner_labels]
    except NERPipelineError:
        raise

    if len(set(normalized_labels)) != len(ENTITY_TYPES) or set(normalized_labels) != set(ENTITY_TYPES):
        raise NERPipelineError("Schema NER labels do not match ENTITY_TYPES")

    if not isinstance(mapping, dict) or set(mapping) != set(ARGUMENT_TYPES):
        raise NERPipelineError("Invalid argument_mapping keys")

    normalized_mapping = {}
    for argument_type, labels in mapping.items():
        if not isinstance(labels, list):
            raise NERPipelineError(
                f"Mapping for {argument_type} must be a list"
            )

        try:
            normalized_mapping[argument_type] = [
                normalize_ner_label(label) for label in labels
            ]
        except NERPipelineError as exc:
            raise NERPipelineError(
                f"Invalid mapping for {argument_type}: {exc}"
            ) from exc

    return {
        "ner_labels": normalized_labels,
        "argument_mapping": normalized_mapping,
    }


def arguments_for_ner_label(label):
    normalized_label = normalize_ner_label(label)
    schema = load_argument_schema()

    return [
        argument_type
        for argument_type, ner_labels in schema["argument_mapping"].items()
        if normalized_label in ner_labels
    ]

