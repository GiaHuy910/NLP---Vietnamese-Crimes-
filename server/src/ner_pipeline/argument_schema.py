import json
from pathlib import Path
from typing import Any

from .errors import NERPipelineError
from .paths import DATASET_DIR
from .schema import ENTITY_TYPES


SCHEMA_PATH = DATASET_DIR / "argument_ner_schema.json"

LEGACY_TO_CANONICAL = {
    "PERSON": "PERSON",
    "ORGANIZATION": "ORG",
    "ORG": "ORG",
    "LOCATION": "LOC",
    "LOC": "LOC",
}

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


def load_argument_schema(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NERPipelineError(
            f"Khong doc duoc argument schema {path}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise NERPipelineError("Argument schema phai la JSON object.")

    ner_labels = payload.get("ner_labels")
    mapping = payload.get("argument_mapping")

    if not isinstance(ner_labels, list) or not all(
        isinstance(label, str) for label in ner_labels
    ):
        raise NERPipelineError("ner_labels phai la danh sach chuoi.")

    if not isinstance(mapping, dict):
        raise NERPipelineError("argument_mapping phai la JSON object.")

    if set(mapping) != set(ARGUMENT_TYPES):
        raise NERPipelineError(
            "argument_mapping phai co dung 10 loai Argument da quy dinh."
        )

    canonical_labels = {
        LEGACY_TO_CANONICAL.get(label, label) for label in ner_labels
    }

    for argument, labels in mapping.items():
        if not isinstance(labels, list) or not all(
            isinstance(label, str) for label in labels
        ):
            raise NERPipelineError(
                f"Mapping cua {argument} phai la danh sach nhan."
            )

        unknown = set(labels) - canonical_labels
        if unknown:
            raise NERPipelineError(
                f"Nhan khong duoc khai bao trong ner_labels: {sorted(unknown)}"
            )

    return payload



def normalize_ner_label(label: str) -> str:
    raw_label = label.strip().upper()
    normalized = LEGACY_TO_CANONICAL.get(raw_label, raw_label)

    schema = load_argument_schema()
    declared_labels = {
        LEGACY_TO_CANONICAL.get(item.upper(), item.upper())
        for item in schema["ner_labels"]
    }

    if normalized not in declared_labels:
        raise NERPipelineError(f"Nhãn NER không hỗ trợ: {label}")

    return normalized



def arguments_for_ner_label(
    label: str, path: Path = SCHEMA_PATH
) -> list[str]:
    canonical = normalize_ner_label(label)
    schema = load_argument_schema(path)
    result = []

    for argument, labels in schema["argument_mapping"].items():
        canonical_labels = {
            LEGACY_TO_CANONICAL.get(item.upper(), item.upper())
            for item in labels
        }
        if canonical in canonical_labels:
            result.append(argument)

    return result
