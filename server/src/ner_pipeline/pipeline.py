import json
from pathlib import Path
import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer, AutoConfig

from .errors import NERPipelineError
from .paths import MODEL_DIR
from .schema import LABELS
from .event_module import extract_events
from .phobert import _tokenize_words, ID_TO_LABEL, spans_from_bio
from .alignment import _underthesea_segments, _segment_offsets

class LegalExtractionPipeline:
    def __init__(self, model_dir: Path = MODEL_DIR):
        print("Đang khởi tạo Legal Extraction Pipeline và nạp PhoBERT vào RAM...")
        if not (model_dir / "config.json").is_file():
            raise NERPipelineError(f"Không tìm thấy model tại {model_dir}")
            
        config = AutoConfig.from_pretrained(model_dir)
        if config.num_labels != len(LABELS):
             raise NERPipelineError("Cấu hình nhãn của Checkpoint không khớp với Schema hiện tại.")

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir, use_fast=True)
        self.model = AutoModelForTokenClassification.from_pretrained(model_dir).to(self.device)
        self.model.eval()
        self.max_length = 256
        print(f"Khởi tạo thành công trên thiết bị: {self.device}")

    def _predict_ner_internal(self, text: str) -> list[dict]:
        import unicodedata
        sentence = unicodedata.normalize("NFC", text)
        segments = _underthesea_segments(sentence)
        tokens_with_offsets = _segment_offsets(sentence, segments)
        
        tokens = [token for token, _, _ in tokens_with_offsets]
        token_offsets = [[start, end] for _, start, end in tokens_with_offsets]
        
        encoded = _tokenize_words(self.tokenizer, tokens, self.max_length)
        word_ids = encoded.word_ids()
        
        inputs = {
            name: torch.tensor([encoded[name]], dtype=torch.long, device=self.device)
            for name in self.tokenizer.model_input_names if name in encoded
        }
        
        with torch.no_grad():
            logits = self.model(**inputs).logits[0]
            
        word_labels = [None] * len(tokens)
        for token_index, word_id in enumerate(word_ids):
            if word_id is not None and word_labels[word_id] is None:
                word_labels[word_id] = ID_TO_LABEL[int(logits[token_index].argmax().item())]
                
        labels = [label or "O" for label in word_labels]
        spans = spans_from_bio(token_offsets, labels)
        
        return [
            {"text": sentence[start:end], "label": label, "start": start, "end": end}
            for start, end, label in spans
        ]

    def process(self, text: str) -> dict:
        if not text.strip():
            return {"error": "Văn bản đầu vào trống"}

        try:
            ner_results = self._predict_ner_internal(text)
            events = extract_events(text, ner_results)

            return {
                "text": text,
                "entities": ner_results,
                "events": events
            }
        except Exception as e:
            return {"error": f"Lỗi trong quá trình xử lý: {str(e)}"}