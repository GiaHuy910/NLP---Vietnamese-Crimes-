from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import json
import uvicorn

from .ner_pipeline.errors import NERPipelineError
from .ner_pipeline.paths import MODEL_DIR, DATASET_DIR
from .ner_pipeline.baseline import RuleBasedNER
from .ner_pipeline.event_module import extract_events
from .ner_pipeline.phobert import predict_sentence

app = FastAPI(title="Vietnamese Crimes NLP Analysis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProcessRequest(BaseModel):
    text: Optional[str] = ""

class FeedbackRequest(BaseModel):
    text: Optional[str] = ""
    rating: str  # "positive" | "negative"
    category: Optional[str] = "general"
    comment: Optional[str] = ""
    timestamp: Optional[str] = None


def extract_entities_robust(text: str):
    """
    Trích xuất thực thể NER:
    Ưu tiên PhoBERT nếu có checkpoint tải sẵn, nếu không sẽ tự động fallback
    sang RuleBasedNER để hệ thống luôn phản hồi ổn định và chính xác.
    """
    phobert_ready = (MODEL_DIR / "config.json").is_file()
    if phobert_ready:
        try:
            return predict_sentence(text), "PhoBERT"
        except Exception:
            pass

    baseline = RuleBasedNER()
    return baseline.predict(text), "Rule-based Baseline"


@app.get("/")
def read_root():
    return {"message": "Vietnamese Crimes NLP Analysis API is running!"}


@app.post("/api/process")
def process_post(req: ProcessRequest):
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Văn bản không được để trống.")

    try:
        entities, model_used = extract_entities_robust(text)
        events = extract_events(text, entities)
        triggers = [ev["trigger"] for ev in events if "trigger" in ev]

        return {
            "message": "Phân tích văn bản thành công.",
            "input_text": text,
            "status": "success",
            "model_used": model_used,
            "entities": entities,
            "triggers": triggers,
            "events": events,
            "char_count": len(text),
            "word_count": len(text.split()),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích: {exc}") from exc


@app.post("/api/process/event-trigger")
def detect_event_triggers(req: ProcessRequest):
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Văn bản không được để trống.")

    try:
        entities, _ = extract_entities_robust(text)
        events = extract_events(text, entities)
        triggers = [ev["trigger"] for ev in events if "trigger" in ev]

        return {
            "input_text": text,
            "triggers": triggers,
            "events": events,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi nhận diện trigger: {exc}") from exc


@app.post("/api/process-file")
async def process_file(file: UploadFile = File(...)):
    try:
        content = await file.read()
        text = content.decode("utf-8", errors="replace").strip()
        if not text:
            raise HTTPException(status_code=400, detail="File tải lên không có nội dung văn bản.")

        entities, model_used = extract_entities_robust(text)
        events = extract_events(text, entities)
        triggers = [ev["trigger"] for ev in events if "trigger" in ev]

        return {
            "message": "Phân tích file thành công.",
            "filename": file.filename,
            "input_text": text,
            "status": "success",
            "model_used": model_used,
            "entities": entities,
            "triggers": triggers,
            "events": events,
            "char_count": len(text),
            "word_count": len(text.split()),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Không thể xử lý file: {exc}") from exc


@app.post("/api/feedback")
def submit_feedback(req: FeedbackRequest):
    feedback_file = DATASET_DIR / "user_feedback.jsonl"
    record = {
        "text": req.text,
        "rating": req.rating,
        "category": req.category,
        "comment": req.comment,
        "timestamp": req.timestamp or datetime.now().isoformat(),
    }
    try:
        feedback_file.parent.mkdir(parents=True, exist_ok=True)
        with open(feedback_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return {"status": "success", "message": "Cảm ơn bạn đã gửi phản hồi!"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Không thể lưu phản hồi: {exc}") from exc


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="127.0.0.1", port=3001, reload=True)
    uvicorn.run("src.main:app", host="127.0.0.1", port=3001, reload=True)
