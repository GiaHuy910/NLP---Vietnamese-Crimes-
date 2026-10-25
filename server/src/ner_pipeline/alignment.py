import re
import unicodedata
from typing import Callable
import logging


from .errors import NERPipelineError
from .schema import AnnotatedExample, LABELS, Mention, normalize_entity_label

logger = logging.getLogger(__name__)
_SURFACE_TOKEN = re.compile(r"[^\W_]+|[^\w\s]", flags=re.UNICODE)
_SEGMENT_TOKEN = re.compile(r"[^\W_]+(?:_[^\W_]+)*|[^\w\s]", flags=re.UNICODE)


def surface_tokens(text: str) -> list[tuple[str, int, int]]:
    """Tokenize orthographic words and punctuation while retaining source offsets."""
    return [
        (match.group(), match.start(), match.end())
        for match in _SURFACE_TOKEN.finditer(text)
    ]


def _normalized_token(value: str) -> str:
    value = value.replace("Ð", "Đ").replace("ð", "đ")
    return unicodedata.normalize("NFC", value.replace("_", " ")).casefold()

def _fold_with_offsets(value: str) -> tuple[str, list[int], list[int]]:
    folded: list[str] = []
    starts: list[int] = []
    ends: list[int] = []

    for index, character in enumerate(value):
        character = character.replace("Ð", "Đ").replace("ð", "đ")
        normalized = unicodedata.normalize("NFD", character.casefold())

        for result in normalized:
            if unicodedata.category(result) == "Mn":
                continue

            folded.append(result)
            starts.append(index)
            ends.append(index + 1)

    return "".join(folded), starts, ends

def _find_mentions(
    sentence: str,
    mention_texts: tuple[tuple[str, str], ...],
    *,
    row_number: int,
) -> list[Mention]:
    sentence_tokens = surface_tokens(sentence)
    normalized_sentence = [
        _normalized_token(token)
        for token, _, _ in sentence_tokens
    ]

    found: list[Mention] = []
    raw_candidates: list[Mention] = []

    for text, label in mention_texts:
        entity_tokens = surface_tokens(text)
        needle = [
            _normalized_token(token)
            for token, _, _ in entity_tokens
        ]

        if not needle:
            raise NERPipelineError(
                f"Dòng {row_number}: entity không có token hợp lệ."
            )

        matches: list[tuple[int, int]] = []

        for index in range(len(normalized_sentence) - len(needle) + 1):
            if normalized_sentence[index:index + len(needle)] != needle:
                continue

            start = sentence_tokens[index][1]
            end = sentence_tokens[index + len(needle) - 1][2]
            matches.append((start, end))

            if not matches:
              raise NERPipelineError(
                  f"Dòng {row_number}: không tìm thấy entity "
                  f"{text!r} trong sentence. "
                  f"Sentence={sentence!r}; "
                  f"Entity tokens={entity_tokens!r}"
              )

        for start, end in matches:
            raw_candidates.append(
                Mention(sentence[start:end], label, start, end)
            )

    # Remove exact duplicate spans with the same label.
    # Do not automatically remove nested spans with different labels.
    seen: set[tuple[int, int, str]] = set()

    for mention in raw_candidates:
        key = (mention.start, mention.end, mention.label)
        if key in seen:
            continue

        seen.add(key)
        found.append(mention)

    return found


def _underthesea_segments(sentence: str) -> list[str]:
    from underthesea import word_tokenize

    segmented = word_tokenize(sentence, format="text")
    return segmented.split()


def _segment_offsets(
    sentence: str,
    segments: list[str],
) -> list[tuple[str, int, int]]:
    tokens: list[tuple[str, int, int]] = []
    cursor = 0

    folded_sentence, folded_starts, folded_ends = _fold_with_offsets(sentence)

    for segment in segments:
        folded_segment, _, _ = _fold_with_offsets(segment)

        # Allow underscore-joined tokens to match syllables separated by
        # whitespace or underscores in the original sentence.
        parts = segment.split("_")
        flexible = r"[\s_]*".join(
            re.escape(part) for part in parts
        )

        folded_parts = folded_segment.split("_")
        folded_pattern = r"[\s_]*".join(
            re.escape(part) for part in folded_parts
        )

        candidates: list[tuple[int, int]] = []

        # 1. Try a direct match in the original sentence.
        for match in re.finditer(
            flexible, sentence[cursor:], flags=re.IGNORECASE
        ):
            candidates.append(
                (cursor + match.start(), cursor + match.end())
            )
            break

        # 2. Try again after Unicode normalization and accent folding.
        if not candidates and folded_pattern:
            for match in re.finditer(
                folded_pattern,
                folded_sentence,
                flags=re.IGNORECASE,
            ):
                if match.start() >= 0 and match.end() > match.start():
                    start = folded_starts[match.start()]
                    end = folded_ends[match.end() - 1]

                    if start >= cursor:
                        candidates.append((start, end))
                        break

        selected = None

        for start, end in sorted(candidates):
            skipped = sentence[cursor:start]

            if any(not ch.isspace() and ch != "_" for ch in skipped):
                continue

            selected = (start, end)
            break

        if selected is None:
            raise NERPipelineError(
                f"Khong the can chinh token {segment!r} "
                f"tai vi tri {cursor} trong sentence: {sentence!r}"
            )

        start, end = selected
        tokens.append((segment, start, end))
        cursor = end

    tail = sentence[cursor:]

    if any(not ch.isspace() and ch != "_" for ch in tail):
        raise NERPipelineError(
            f"Bo tach tu bo sot phan cuoi sentence: {tail!r}"
        )

    if not tokens and sentence.strip():
        raise NERPipelineError(
            "Bo tach tu khong tao token cho sentence."
        )

    return tokens

def _split_tokens_at_entity_boundaries(
    sentence: str,
    tokens: list[tuple[str, int, int]],
    mentions: list[Mention],
    *,
    row_number: int,
) -> list[tuple[str, int, int]]:
    boundaries = {
        boundary
        for mention in mentions
        for boundary in (mention.start, mention.end)
    }
    adjusted: list[tuple[str, int, int]] = []
    for token, start, end in tokens:
        internal_boundaries = {
            boundary for boundary in boundaries if start < boundary < end
        }
        if not internal_boundaries:
            adjusted.append((token, start, end))
            continue

        syllables = [
            (match.group(), start + match.start(), start + match.end())
            for match in re.finditer(r"[^_\s]+", sentence[start:end])
        ]
        valid_boundaries = {
            boundary
            for _, _, syllable_end in syllables[:-1]
            for boundary in (
                syllable_end,
                syllable_end + 1
                if syllable_end < end
                and sentence[syllable_end].isspace()
                else syllable_end,
            )
        }
        
def _split_tokens_at_entity_boundaries(
    sentence: str,
    tokens: list[tuple[str, int, int]],
    mentions: list[Mention],
    *,
    row_number: int,
) -> list[tuple[str, int, int]]:
    boundaries = {
        boundary
        for mention in mentions
        for boundary in (mention.start, mention.end)
    }

    adjusted: list[tuple[str, int, int]] = []

    for token, start, end in tokens:
        internal_boundaries = {
            boundary
            for boundary in boundaries
            if start < boundary < end
        }

        if not internal_boundaries:
            adjusted.append((token, start, end))
            continue

        syllables = [
            (match.group(), start + match.start(), start + match.end())
            for match in re.finditer(r"[^_\s]+", sentence[start:end])
        ]

        valid_boundaries = set()

        for _, _, syllable_end in syllables[:-1]:
            valid_boundaries.add(syllable_end)

            if (
                syllable_end < end
                and sentence[syllable_end].isspace()
            ):
                valid_boundaries.add(syllable_end + 1)

        # Allow an entity to end before the period in an abbreviation,
        # e.g. token "M." when the annotated entity is "M".
        for boundary in internal_boundaries:
            relative = boundary - start

            if (
                0 < relative < len(token)
                and token[relative] == "."
                and sentence[boundary] == "."
            ):
                valid_boundaries.add(boundary)

        if not internal_boundaries.issubset(valid_boundaries):
            raise NERPipelineError(
                f"Dòng {row_number}: entity cắt giữa một token "
                f"không thể tách an toàn theo ranh giới âm tiết. "
                f"Token={token!r}, span=({start}, {end}), "
                f"Token text={sentence[start:end]!r}, "
                f"Internal boundaries={sorted(internal_boundaries)}, "
                f"Valid boundaries={sorted(valid_boundaries)}, "
                f"Mentions={[(m.text, m.label, m.start, m.end) for m in mentions]}"
            )

        adjusted.extend(syllables)

    return adjusted


def _resolve_overlapping_mentions(
    mentions: list[Mention],
    *,
    row_number: int,
    sentence: str,
) -> tuple[list[Mention], int]:
    candidates = sorted(
        mentions,
        key=lambda item: (
            -(item.end - item.start),
            item.start,
        ),
    )

    selected: list[Mention] = []
    removed = 0

    for mention in candidates:
        overlaps = [
            current
            for current in selected
            if mention.start < current.end
            and mention.end > current.start
        ]

        if not overlaps:
            selected.append(mention)
            continue

        # Keep only one copy when spans and labels are identical.
        if all(
            current.start == mention.start
            and current.end == mention.end
            and current.label == mention.label
            for current in overlaps
        ):
            removed += 1
            continue

        # Sort candidates from longest to shortest.
        # Prefer longer spans to avoid overlapping nested entities.
        current_longer = all(
            (current.end - current.start)
            > (mention.end - mention.start)
            for current in overlaps
        )

        if current_longer:
            removed += 1
            continue

        details = [
            {
                "text": sentence[current.start:current.end],
                "label": current.label,
                "span": (current.start, current.end),
            }
            for current in overlaps
        ]

        raise NERPipelineError(
            f"Dòng {row_number}: entity chồng lấn không thể "
            f"tự động giải quyết. "
            f"Entity hiện tại: "
            f"{sentence[mention.start:mention.end]!r} "
            f"[{mention.label}] "
            f"span=({mention.start}, {mention.end}); "
            f"Entity chồng lấn: {details}"
        )

    return sorted(selected, key=lambda item: item.start), removed


def align_example(
    example: AnnotatedExample,
    *,
    row_number: int,
    segmenter: Callable[[str], list[str]] | None = None,
) -> dict[str, object]:
    # Avoid NFC normalization if it would shift original offsets.
    # Ideally, normalize the data to NFC before annotation.
    sentence = unicodedata.normalize("NFC", example.sentence)
    
    # Use annotator-provided offsets directly instead of searching again by text.
    mentions = []

    for m in example.mentions:
        normalized_mention_text = unicodedata.normalize(
            "NFC", m.text
        )
        label = normalize_entity_label(m.label)

        # Negative offsets mean the data did not provide entity positions.
        if m.start < 0 or m.end < 0:
            # Match whole words and prefer exact case.
            # Case-insensitive matching without word boundaries previously labeled every
            # "t" in a sentence as PERSON when the annotated abbreviation was "T.".
            pattern = (
                r"(?<!\w)"
                + r"\s+".join(
                    re.escape(part)
                    for part in normalized_mention_text.split()
                )
                + r"(?!\w)"
            )

            matches = list(re.finditer(pattern, sentence))
            if not matches:
                matches = list(
                    re.finditer(pattern, sentence, flags=re.IGNORECASE)
                )

            if not matches:
                raise NERPipelineError(
                    f"Dòng {row_number}: Không tìm thấy entity "
                    f"{m.text!r} trong câu."
                )

            for match in matches:
                start, end = match.span()
                mentions.append(
                    Mention(sentence[start:end], label, start, end)
                )

            continue

        start, end = m.start, m.end

        if start < 0 or end > len(sentence) or start >= end:
            raise NERPipelineError(
                f"Dòng {row_number}: Offset không hợp lệ "
                f"({start}:{end})."
            )

        span_text = sentence[start:end]

        if span_text.casefold() != normalized_mention_text.casefold():
            raise NERPipelineError(
                f"Dòng {row_number}: Offset không khớp. "
                f"Text annotator: {m.text!r}, "
                f"Text tại offset ({start}:{end}): {span_text!r}"
            )

        mentions.append(
            Mention(span_text, label, start, end)
        )
    # Handle overlapping entities.
    mentions, overlap_count = _resolve_overlapping_mentions(
        mentions,
        row_number=row_number,
        sentence=sentence,
    )

    # Segment the sentence and initialize BIO labels.
    segments = (segmenter or _underthesea_segments)(sentence)
    tokens = _segment_offsets(sentence, segments)
     # Split tokens when an entity boundary falls inside a token.
    boundaries = {
        position
        for mention in mentions
        for position in (mention.start, mention.end)
    }

    split_tokens = []

    for token, start, end in tokens:
        cuts = sorted(
            position
            for position in boundaries
            if start < position < end
        )

        positions = [start] + cuts + [end]

        for left, right in zip(positions, positions[1:]):
            while left < right and sentence[left].isspace():
                left += 1
            while right > left and sentence[right - 1].isspace():
                right -= 1

            if left < right:
                piece = sentence[left:right].replace(" ", "_")
                split_tokens.append((piece, left, right))

    tokens = split_tokens
    labels = ["O"] * len(tokens)

    # Assign BIO labels to each entity.
    occupied: list[tuple[int, int, str]] = []

    for mention in mentions:
        covered = [
            index
            for index, (_, start, end) in enumerate(tokens)
            if start < mention.end and end > mention.start
        ]

        if not covered:
            raise NERPipelineError(
                f"Dòng {row_number}: entity {mention.text!r} "
                "không khớp token."
            )

        first_start = tokens[covered[0]][1]
        last_end = tokens[covered[-1]][2]

        start_matches = first_start == mention.start
        end_matches = last_end == mention.end

        # Allow an entity to end before the period in "M.".
        if not end_matches and last_end == mention.end + 1:
            end_matches = (
                sentence[mention.end:last_end] == "."
                and mention.text == sentence[mention.start:mention.end]
            )

        if not start_matches or not end_matches:
            raise NERPipelineError(
                f"Dòng {row_number}: entity {mention.text!r} "
                "cắt giữa token đã word-segment."
            )

        for index in covered:
            for old_start, old_end, old_label in occupied:
                if (
                    old_start <= index <= old_end
                    and old_label != mention.label
                ):
                    raise NERPipelineError(
                        f"Dòng {row_number}: các entity chồng lấn "
                        "có nhãn mâu thuẫn."
                    )

            if labels[index] != "O":
                raise NERPipelineError(
                    f"Dòng {row_number}: annotation chứa "
                    "các entity chồng lấn."
                )

            labels[index] = (
                f"B-{mention.label}"
                if index == covered[0]
                else f"I-{mention.label}"
            )

        occupied.append(
            (covered[0], covered[-1], mention.label)
        )


    if any(label not in LABELS for label in labels):
        raise NERPipelineError(f"Dòng {row_number}: BIO label ngoài tập cho phép.")
    aligned_mentions = [
        {
            "text": mention.text,
            "label": mention.label,
            "start": mention.start,
            "end": mention.end,
        }
        for mention in mentions
    ]
    return {
        "sentence": sentence,
        "tokens": [token for token, _, _ in tokens],
        "token_offsets": [[start, end] for _, start, end in tokens],
        "labels": labels,
        "entities": aligned_mentions,
        "overlapping_entities_removed": overlap_count,
    }
