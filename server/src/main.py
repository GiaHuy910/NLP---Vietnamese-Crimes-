from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

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

@app.get("/api/process")
def process_get():
    return {"message": "First API receiving input (GET)"}

@app.post("/api/process")
def process_post(req: ProcessRequest):
    return {
        "message": "Text received successfully!",
        "input_text": req.text,
        "status": "success",
        "analysis": f"Text contains {len(req.text or '')} characters."
    }

@app.get("/api/process-file")
@app.post("/api/process-file")
def process_file():
    return {"message": "Second API receiving File"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=3001, reload=True)

