import random
import unicodedata
from pathlib import Path
from typing import Any

from .errors import NERPipelineError
from .metrics import Span, spans_from_bio
from .paths import MODEL_DIR
from .schema import LABELS


LABEL_TO_ID = {label: index for index, label in enumerate(LABELS)}
ID_TO_LABEL = {index: label for label, index in LABEL_TO_ID.items()}


class _EncodedWords(dict[str, Any]):
    def __init__(self, values: dict[str, Any], word_ids: list[int | None]):
        super().__init__(values)
        self._word_ids = word_ids

    def word_ids(self) -> list[int | None]:
        return self._word_ids


def _dependencies() -> tuple[Any, Any, Any, Any]:
    try:
        import torch
        from torch.utils.data import DataLoader
        from transformers import AutoModelForTokenClassification, AutoTokenizer
    except ImportError as exc:
        raise NERPipelineError(
            "Thiếu dependency cho PhoBERT. Cài bằng "
            "`pip install -r requirements-ner.txt` trong thư mục server."
        ) from exc
    return torch, DataLoader, AutoModelForTokenClassification, AutoTokenizer


def _require_model(model_dir: Path) -> None:
    if not (model_dir / "config.json").is_file():
        raise NERPipelineError(
            f"PhoBERT NER chưa được train hoặc không tồn tại tại {model_dir}. "
            "Chạy lệnh train trước khi predict/evaluate."
        )


def _tokenize_words(tokenizer: Any, tokens: list[str], max_length: int) -> Any:
    if tokenizer.is_fast:
        encoded = tokenizer(
            tokens,
            is_split_into_words=True,
            truncation=False,
            add_special_tokens=True,
        )
        word_ids = encoded.word_ids()
    else:
        token_ids: list[int] = []
        raw_word_ids: list[int] = []
        for word_index, word in enumerate(tokens):
            pieces = tokenizer.tokenize(word)
            if not pieces:
                pieces = [tokenizer.unk_token]
            piece_ids = tokenizer.convert_tokens_to_ids(pieces)
            token_ids.extend(piece_ids)
            raw_word_ids.extend([word_index] * len(piece_ids))
        special_mask = tokenizer.get_special_tokens_mask(
            token_ids, already_has_special_tokens=False
        )
        input_ids = tokenizer.build_inputs_with_special_tokens(token_ids)
        word_ids = []
        source_index = 0
        for is_special in special_mask:
            if is_special:
                word_ids.append(None)
            else:
                word_ids.append(raw_word_ids[source_index])
                source_index += 1
        if len(word_ids) != len(input_ids):
            raise NERPipelineError(
                "Không thể căn chỉnh token PhoBERT với các từ tiếng Việt."
            )
        if len(input_ids) > max_length:
            raise NERPipelineError(
                f"Câu có {len(input_ids)} subword nhưng max_length={max_length}; "
                "tăng --max-length hoặc xử lý câu dài trước khi train."
            )
        encoded = _EncodedWords(
            {
                "input_ids": input_ids,
                "attention_mask": [1] * len(input_ids),
            },
            word_ids,
        )
    if len(encoded["input_ids"]) > max_length:
        raise NERPipelineError(
            f"Câu cần {len(encoded['input_ids'])} subword nhưng max_length="
            f"{max_length}; tăng --max-length hoặc xử lý câu dài trước khi train."
        )
    represented = {word_id for word_id in word_ids if word_id is not None}
    if represented != set(range(len(tokens))):
        raise NERPipelineError(
            f"Câu có {len(tokens)} token tiếng Việt nhưng bị cắt bởi max_length="
            f"{max_length}; tăng --max-length hoặc xử lý câu dài trước khi train."
        )
    return encoded


def _encode_record(tokenizer: Any, record: dict[str, Any], max_length: int) -> dict[str, Any]:
    encoded = _tokenize_words(tokenizer, record["tokens"], max_length)
    word_ids = encoded.word_ids()
    labels = record["labels"]
    aligned: list[int] = []
    previous_word_id: int | None = None
    for word_id in word_ids:
        if word_id is None:
            aligned.append(-100)
        elif word_id != previous_word_id:
            aligned.append(LABEL_TO_ID[labels[word_id]])
        else:
            aligned.append(-100)
        previous_word_id = word_id
    return {**encoded, "labels": aligned}


def _batch(dataset: list[dict[str, Any]], tokenizer: Any, torch: Any) -> dict[str, Any]:
    features = [
        {
            key: value
            for key, value in item.items()
            if key in tokenizer.model_input_names
        }
        for item in dataset
    ]
    label_rows = [item["labels"] for item in dataset]
    padded = tokenizer.pad(features, padding=True, return_tensors="pt")
    width = padded["input_ids"].shape[1]
    padded["labels"] = torch.tensor(
        [row + [-100] * (width - len(row)) for row in label_rows], dtype=torch.long
    )
    return padded


def _class_weights(
    records: list[dict[str, Any]], *, power: float = 0.5
) -> list[float]:
    counts = {label: 0 for label in LABELS}
    for record in records:
        for label in record["labels"]:
            counts[label] += 1
    total = sum(counts.values())
    present = [label for label in LABELS if counts[label]]
    if not present:
        raise NERPipelineError("Training split không có BIO labels để train.")
    weights = {
        label: (total / counts[label]) ** power if counts[label] else 0.0
        for label in LABELS
    }
    mean = sum(weights[label] for label in present) / len(present)
    return [weights[label] / mean for label in LABELS]


def _prediction_for_record(
    record: dict[str, Any], tokenizer: Any, model: Any, torch: Any, max_length: int
) -> list[Span]:
    encoded = _tokenize_words(tokenizer, record["tokens"], max_length)
    word_ids = encoded.word_ids()
    inputs = {
        name: torch.tensor([encoded[name]], dtype=torch.long, device=model.device)
        for name in tokenizer.model_input_names
        if name in encoded
    }
    model.eval()
    with torch.no_grad():
        logits = model(**inputs).logits[0]
    word_labels: list[str | None] = [None] * len(record["tokens"])
    for token_index, word_id in enumerate(word_ids):
        if word_id is not None and word_labels[word_id] is None:
            word_labels[word_id] = ID_TO_LABEL[int(logits[token_index].argmax().item())]
    labels = [label or "O" for label in word_labels]
    return spans_from_bio(record["token_offsets"], labels)


def predict_records(
    records: list[dict[str, Any]], model_dir: Path = MODEL_DIR, max_length: int = 256
) -> list[list[Span]]:
    _require_model(model_dir)
    torch, _, AutoModelForTokenClassification, AutoTokenizer = _dependencies()
    tokenizer = AutoTokenizer.from_pretrained(model_dir, use_fast=True)
    model = AutoModelForTokenClassification.from_pretrained(model_dir)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    return [
        _prediction_for_record(record, tokenizer, model, torch, max_length)
        for record in records
    ]


def predict_sentence(
    sentence: str, model_dir: Path = MODEL_DIR, max_length: int = 256
) -> list[dict[str, str]]:
    from .alignment import _underthesea_segments, _segment_offsets

    _require_model(model_dir)
    sentence = unicodedata.normalize("NFC", sentence)
    segments = _underthesea_segments(sentence)
    tokens_with_offsets = _segment_offsets(sentence, segments)
    record = {
        "sentence": sentence,
        "tokens": [token for token, _, _ in tokens_with_offsets],
        "token_offsets": [[start, end] for _, start, end in tokens_with_offsets],
    }
    spans = predict_records([record], model_dir=model_dir, max_length=max_length)[0]
    return [
        {"text": sentence[start:end], "label": label}
        for start, end, label in spans
    ]


def _validation_f1(
    records: list[dict[str, Any]],
    tokenizer: Any,
    model: Any,
    torch: Any,
    max_length: int,
) -> float:
    gold: list[list[Span]] = []
    predicted: list[list[Span]] = []
    for record in records:
        gold.append(
            [
                (int(item["start"]), int(item["end"]), str(item["label"]))
                for item in record["entities"]
            ]
        )
        predicted.append(
            _prediction_for_record(record, tokenizer, model, torch, max_length)
        )
    from .metrics import score_spans

    return float(score_spans(gold, predicted)["overall"]["f1"])


def train(
    train_records: list[dict[str, Any]],
    validation_records: list[dict[str, Any]],
    *,
    model_dir: Path = MODEL_DIR,
    model_name: str = "vinai/phobert-base-v2",
    epochs: int = 3,
    batch_size: int = 8,
    learning_rate: float = 2e-5,
    max_length: int = 256,
    seed: int = 42,
    class_weight_power: float = 0.5,
) -> Path:
    if not train_records or not validation_records:
        raise NERPipelineError("Train và validation phải có ít nhất một câu.")
    if epochs < 1 or batch_size < 1 or learning_rate <= 0 or max_length < 2:
        raise NERPipelineError(
            "epochs, batch-size và learning-rate phải dương; max-length phải >= 2."
        )
    if class_weight_power < 0:
        raise NERPipelineError("class-weight-power không được âm.")
    torch, DataLoader, AutoModelForTokenClassification, AutoTokenizer = _dependencies()
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    tokenizer = AutoTokenizer.from_pretrained(
        model_name, use_fast=True, add_prefix_space=True
    )
    model = AutoModelForTokenClassification.from_pretrained(
        model_name,
        num_labels=len(LABELS),
        id2label=ID_TO_LABEL,
        label2id=LABEL_TO_ID,
    )
    encoded_train = [
        _encode_record(tokenizer, record, max_length) for record in train_records
    ]
    for record in validation_records:
        _encode_record(tokenizer, record, max_length)
    generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(
        encoded_train,
        batch_size=batch_size,
        shuffle=True,
        generator=generator,
        collate_fn=lambda items: _batch(items, tokenizer, torch),
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    class_weights = torch.tensor(
        _class_weights(train_records, power=class_weight_power),
        dtype=torch.float32,
        device=device,
    )

    best_f1 = -1.0
    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        for batch in loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            optimizer.zero_grad()
            labels = batch.pop("labels")
            logits = model(**batch).logits
            loss = torch.nn.functional.cross_entropy(
                logits.reshape(-1, len(LABELS)),
                labels.reshape(-1),
                weight=class_weights,
                ignore_index=-100,
            )
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item())
        validation_f1 = _validation_f1(
            validation_records, tokenizer, model, torch, max_length
        )
        print(
            f"Epoch {epoch + 1}/{epochs}: "
            f"train_loss={total_loss / max(len(loader), 1):.6f}, "
            f"validation_f1={validation_f1:.6f}"
        )
        if validation_f1 > best_f1:
            best_f1 = validation_f1
            model_dir.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(model_dir)
            tokenizer.save_pretrained(model_dir)

    return model_dir
