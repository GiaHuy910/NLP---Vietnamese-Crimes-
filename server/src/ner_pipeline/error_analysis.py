
import re
from collections import Counter

from .metrics import Span, spans_from_record


_ABBREVIATION = re.compile(
    r"(?:\b[A-ZĐ]{2,}\b|(?:[A-Za-zÀ-ỹĐđ]\.){2,})"
)


def analyze_sentence(
    record: dict[str, object], predicted: list[Span]
) -> dict[str, object]:
    gold = spans_from_record(record)
    sentence = str(record["sentence"])

    # Sort spans so matching and reporting are deterministic.
    gold = sorted(gold)
    predicted = sorted(predicted)

    gold_set = set(gold)
    predicted_set = set(predicted)

    gold_unmatched = gold_set - predicted_set
    predicted_unmatched = predicted_set - gold_set

    categories: set[str] = set()

    if gold_unmatched:
        categories.add("entity_missing")
    if predicted_unmatched:
        categories.add("entity_extra")

    for gold_span in gold_unmatched:
        for predicted_span in predicted_unmatched:
            overlap = (
                gold_span[0] < predicted_span[1]
                and predicted_span[0] < gold_span[1]
            )
            if not overlap:
                continue

            if gold_span[2] != predicted_span[2]:
                categories.add("entity_type_mismatch")

            if gold_span[2] == predicted_span[2]:
                categories.add("entity_boundary_mismatch")

            if (
                gold_span[2] == "ORGANIZATION"
                and predicted_span[2] == "LOCATION"
            ):
                categories.add("organization_predicted_as_location")

            if (
                gold_span[2] == "LOCATION"
                and predicted_span[2] == "PERSON"
            ):
                categories.add("location_predicted_as_person")

            if (
                gold_span[2] == "PERSON"
                or predicted_span[2] == "PERSON"
            ):
                categories.add("person_misrecognized")

    # Count multiple entities as descriptive information, not an error.
    if len(gold) > 1:
        categories.add("multiple_entities")

    entity_texts = [
        sentence[start:end]
        for start, end, _ in [*gold, *predicted]
    ]

    if any(_ABBREVIATION.search(text) for text in entity_texts):
        categories.add("abbreviation")

    if any(
        any(char in text for char in ".,;:/()-")
        for text in entity_texts
    ):
        categories.add("punctuation")

    # Repeated entity is an error only when the same predicted span
    # occurs more than once, not when a name repeats naturally in text.
    if len(predicted) != len(set(predicted)):
        categories.add("repeated_prediction")

    return {
        "sentence": sentence,
        "categories": sorted(categories),
        "gold": [
            {"text": sentence[start:end], "label": label}
            for start, end, label in gold
        ],
        "predicted": [
            {"text": sentence[start:end], "label": label}
            for start, end, label in predicted
        ],
    }


def summarize(
    analyses: list[dict[str, object]]
) -> dict[str, object]:
    counts: Counter[str] = Counter()

    for analysis in analyses:
        counts.update(analysis["categories"])

    return {
        "sentence_count": len(analyses),
        "category_counts": dict(sorted(counts.items())),
        "sentences": analyses,
    }
