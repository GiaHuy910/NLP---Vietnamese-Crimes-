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


def _fold_with_offsets_normalized(value: str):
    folded = []
    starts = []
    ends = []

    for index, character in enumerate(value):
        # NFC first makes Vietnamese combining-mark order consistent.
        character = character.replace("Ð", "Đ").replace("ð", "đ")
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

        matches: list[tuple[int, int, bool]] = []

        for index in range(len(normalized_sentence) - len(needle) + 1):
            if normalized_sentence[index:index + len(needle)] != needle:
                continue

            start = sentence_tokens[index][1]
            end = sentence_tokens[index + len(needle) - 1][2]

            # Ưu tiên cách viết hoa/thường khớp chính xác.
            exact_case = sentence[start:end] == text
            matches.append((start, end, exact_case))

        if not matches:
            raise NERPipelineError(
                f"Dòng {row_number}: không tìm thấy entity "
                f"{text!r} trong sentence."
            )

        chosen = matches

        for start, end, _ in chosen:
            raw_candidates.append(
                Mention(sentence[start:end], label, start, end)
            )

    # Loại các span trùng hoàn toàn cùng nhãn.
    # Không tự động xóa span lồng nhau khác nhãn ở đây.
    seen: set[tuple[int, int, str]] = set()

    for mention in raw_candidates:
        key = (mention.start, mention.end, mention.label)
        if key in seen:
            continue

        seen.add(key)
        found.append(mention)

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

        # Cho phép khớp token có dấu "_" với cụm chữ-số
        # hoặc khoảng trắng trong câu gốc.
        parts = segment.split("_")
        flexible = r"[\s_]*".join(
            re.escape(part) for part in parts
        )

        folded_parts = folded_segment.split("_")
        folded_pattern = r"[\s_]*".join(
            re.escape(part) for part in folded_parts
        )

        candidates: list[tuple[int, int]] = []

        # 1. Tim khop truc tiep trong cau goc.
        for match in re.finditer(
            flexible, sentence[cursor:], flags=re.IGNORECASE
        ):
            candidates.append(
                (cursor + match.start(), cursor + match.end())
            )
            break

        # 2. Tim khop sau khi chuan hoa Unicode va bo dau.
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
        if not internal_boundaries.issubset(valid_boundaries):
            raise NERPipelineError(
                f"Dòng {row_number}: entity cắt giữa một token không thể tách "
                "an toàn theo ranh giới âm tiết."
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

        # Nếu cùng span và cùng nhãn thì chỉ giữ một bản.
        if all(
            current.start == mention.start
            and current.end == mention.end
            and current.label == mention.label
            for current in overlaps
        ):
            removed += 1
            continue

        # Candidates được sắp xếp từ span dài đến span ngắn.
        # Ưu tiên span dài hơn để tránh entity con chồng lấn.
        current_longer = all(
            (current.end - current.start)
            >= (mention.end - mention.start)
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
    sentence = unicodedata.normalize("NFC", example.sentence)
    raw_mentions = tuple(
        (unicodedata.normalize("NFC", mention.text), mention.label)
        for mention in example.mentions
    )
    mentions = _find_mentions(sentence, raw_mentions, row_number=row_number)
    mentions, overlap_count = _resolve_overlapping_mentions(
      mentions, row_number=row_number, sentence=sentence
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
