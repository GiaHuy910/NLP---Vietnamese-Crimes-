import re
import unicodedata
from typing import Callable

from .errors import NERPipelineError
from .schema import AnnotatedExample, LABELS, Mention


_SURFACE_TOKEN = re.compile(r"[^\W_]+|[^\w\s]", flags=re.UNICODE)
_SEGMENT_TOKEN = re.compile(r"[^\W_]+(?:_[^\W_]+)*|[^\w\s]", flags=re.UNICODE)


def surface_tokens(text: str) -> list[tuple[str, int, int]]:
    """Tokenize orthographic words and punctuation while retaining source offsets."""
    return [
        (match.group(), match.start(), match.end())
        for match in _SURFACE_TOKEN.finditer(text)
    ]


def _normalized_token(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("_", " ")).casefold()



def _fold_with_offsets(value: str) -> tuple[str, list[int], list[int]]:
    folded: list[str] = []
    starts: list[int] = []
    ends: list[int] = []

    for index, character in enumerate(value):
        normalized = unicodedata.normalize("NFD", character.casefold())

        for result in normalized:
            if unicodedata.category(result) == "Mn":
                continue

            folded.append(result)
            starts.append(index)
            ends.append(index + 1)

    return "".join(folded), starts, ends


def _fold_with_offsets_normalized(value: str):
    folded = []
    starts = []
    ends = []

    for index, character in enumerate(value):
        # NFC first makes Vietnamese combining-mark order consistent.
        normalized = unicodedata.normalize("NFC", character).casefold()
        normalized = unicodedata.normalize("NFD", normalized)

        for result in normalized:
            if unicodedata.category(result) == "Mn":
                continue
            folded.append(result)
            starts.append(index)
            ends.append(index + 1)

    return "".join(folded), starts, ends



def _find_mentions(
    sentence: str, mention_texts: tuple[tuple[str, str], ...], *, row_number: int
) -> list[Mention]:
    sentence_tokens = surface_tokens(sentence)
    normalized_sentence = [_normalized_token(token) for token, _, _ in sentence_tokens]
    found: list[Mention] = []

    for text, label in mention_texts:
        entity_tokens = surface_tokens(text)
        needle = [_normalized_token(token) for token, _, _ in entity_tokens]
        if not needle:
            raise NERPipelineError(f"Dòng {row_number}: entity không có token hợp lệ.")

        matches = 0
        for index in range(len(normalized_sentence) - len(needle) + 1):
            if normalized_sentence[index : index + len(needle)] != needle:
                continue
            start = sentence_tokens[index][1]
            end = sentence_tokens[index + len(needle) - 1][2]
            found.append(Mention(sentence[start:end], label, start, end))
            matches += 1
        if not matches:
            raise NERPipelineError(
                f"Dòng {row_number}: không tìm thấy entity {text!r} trong sentence."
            )
    return found


def _underthesea_segments(sentence: str) -> list[str]:
    try:
        from underthesea import word_tokenize
    except ImportError as exc:
        raise NERPipelineError(
            "Thiếu underthesea. Cài dependency bằng "
            "`pip install -r requirements-ner.txt` trong thư mục server."
        ) from exc

    segmented = word_tokenize(sentence, format="text")
    return [match.group() for match in _SEGMENT_TOKEN.finditer(segmented)]





def _segment_offsets(
    sentence: str,
    segments: list[str],
) -> list[tuple[str, int, int]]:
    tokens: list[tuple[str, int, int]] = []
    cursor = 0

    folded_sentence, folded_starts, folded_ends = _fold_with_offsets(sentence)

    for segment in segments:
        folded_segment, _, _ = _fold_with_offsets(segment)

        # Tokenizer có thể gộp từ bằng dấu "_".
        flexible = re.escape(segment).replace("_", r"[\s_]+")
        folded_pattern = re.escape(folded_segment).replace("_", r"[\s_]+")

        candidates: list[tuple[int, int]] = []

        # 1. Tìm khớp trực tiếp trong phần câu chưa xử lý.
        for match in re.finditer(
            flexible, sentence[cursor:], flags=re.IGNORECASE
        ):
            candidates.append(
                (cursor + match.start(), cursor + match.end())
            )
            break

        # 2. Tìm khớp sau khi bỏ dấu và chuẩn hóa chữ hoa/thường.
        for match in re.finditer(
            folded_pattern, folded_sentence, flags=re.IGNORECASE
        ):
            if match.start() >= len(folded_starts):
                continue
            if match.end() == 0 or match.end() > len(folded_ends):
                continue

            start = folded_starts[match.start()]
            end = folded_ends[match.end() - 1]

            if start >= cursor:
                candidates.append((start, end))
                break

        # 3. Nếu không có khớp nào, xử lý trường hợp "40_g" và "40g".
        if not candidates:
            compact_segment = segment.replace("_", "")
            compact_match = (
                re.match(
                    re.escape(compact_segment),
                    sentence[cursor:],
                    flags=re.IGNORECASE,
                )
                if compact_segment
                else None
            )

            if compact_match is not None:
                candidates.append(
                    (cursor, cursor + compact_match.end())
                )

        # Chọn vị trí hợp lệ sớm nhất; không nhảy qua chữ trong câu.
        selected = None

        for start, end in sorted(candidates):
            skipped = sentence[cursor:start]

            if any(not ch.isspace() and ch != "_" for ch in skipped):
                continue

            selected = (start, end)
            break

        if selected is None:
            raise NERPipelineError(
                f"Không thể căn chỉnh token {segment!r} "
                f"tại vị trí {cursor} trong sentence: {sentence!r}"
            )

        start, end = selected
        tokens.append((segment, start, end))
        cursor = end

    tail = sentence[cursor:]

    if any(not ch.isspace() and ch != "_" for ch in tail):
        raise NERPipelineError(
            f"Bộ tách từ bỏ sót phần cuối sentence: {tail!r}"
        )

    if not tokens and sentence.strip():
        raise NERPipelineError(
            "Bộ tách từ không tạo token cho sentence."
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
        if not internal_boundaries.issubset(valid_boundaries):
            raise NERPipelineError(
                f"Dòng {row_number}: entity cắt giữa một token không thể tách "
                "an toàn theo ranh giới âm tiết."
            )
        adjusted.extend(syllables)
    return adjusted


def _resolve_overlapping_mentions(
    mentions: list[Mention], *, row_number: int
) -> tuple[list[Mention], int]:
    candidates = sorted(mentions, key=lambda item: (-(item.end - item.start), item.start))
    selected: list[Mention] = []
    removed = 0
    for mention in candidates:
        overlaps = [
            current
            for current in selected
            if mention.start < current.end and mention.end > current.start
        ]
        if not overlaps:
            selected.append(mention)
            continue
        if any(current.label != mention.label for current in overlaps):
            raise NERPipelineError(
                f"Dòng {row_number}: entity chồng lấn có nhãn khác nhau; "
                "hãy rà soát annotation."
            )
        removed += 1
    return sorted(selected, key=lambda item: item.start), removed


def align_example(
    example: AnnotatedExample,
    *,
    row_number: int,
    segmenter: Callable[[str], list[str]] | None = None,
) -> dict[str, object]:
    sentence = unicodedata.normalize("NFC", example.sentence)
    raw_mentions = tuple(
        (unicodedata.normalize("NFC", mention.text), mention.label)
        for mention in example.mentions
    )
    mentions = _find_mentions(sentence, raw_mentions, row_number=row_number)
    mentions, overlap_count = _resolve_overlapping_mentions(
        mentions, row_number=row_number
    )
    segments = (segmenter or _underthesea_segments)(sentence)
    tokens = _segment_offsets(sentence, segments)
    tokens = _split_tokens_at_entity_boundaries(
        sentence, tokens, mentions, row_number=row_number
    )
    labels = ["O"] * len(tokens)

    occupied: list[tuple[int, int, str]] = []
    for mention in mentions:
        covered = [
            index
            for index, (_, start, end) in enumerate(tokens)
            if start < mention.end and end > mention.start
        ]
        if not covered:
            raise NERPipelineError(
                f"Dòng {row_number}: entity {mention.text!r} không khớp token."
            )
        first_start = tokens[covered[0]][1]
        last_end = tokens[covered[-1]][2]
        if first_start != mention.start or last_end != mention.end:
            raise NERPipelineError(
                f"Dòng {row_number}: entity {mention.text!r} cắt giữa token đã "
                "word-segment. Hãy sửa span annotation hoặc cách viết entity."
            )
        for index in covered:
            for old_start, old_end, old_label in occupied:
                if index >= old_start and index <= old_end and old_label != mention.label:
                    raise NERPipelineError(
                        f"Dòng {row_number}: các entity chồng lấn có nhãn mâu thuẫn."
                    )
            if labels[index] != "O":
                raise NERPipelineError(
                    f"Dòng {row_number}: annotation chứa các entity chồng lấn."
                )
            labels[index] = (
                f"B-{mention.label}" if index == covered[0] else f"I-{mention.label}"
            )
        occupied.append((covered[0], covered[-1], mention.label))

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
