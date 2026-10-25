from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

from .ner_pipeline.errors import NERPipelineError
from .ner_pipeline.event_module import detect_triggers
from .ner_pipeline.phobert import predict_sentence

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProcessRequest(BaseModel):
    text: Optional[str] = ""

@app.get("/")
def read_root():
    return {"message": "Hello, this is my first API!"}

@app.post("/api/process")
def process_post(req: ProcessRequest):
    text = req.text or ""
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text must not be empty.")

    try:
        entities = predict_sentence(text)
    except NERPipelineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "message": "Text processed successfully.",
        "input_text": text,
        "status": "success",
        "entities": entities,
    }


@app.post("/api/process/event-trigger")
def detect_event_triggers(req: ProcessRequest):
    text = req.text or ""
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text must not be empty.")

    return {
        "input_text": text,
        "triggers": detect_triggers(text),
    }


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="127.0.0.1", port=3001, reload=True)
