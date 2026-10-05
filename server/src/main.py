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
    return {"message": "Xin chào, đây là API đầu tiên của tôi!"}

@app.get("/api/process")
def process_get():
    return {"message": "API thu nhat nhan input (GET)"}

@app.post("/api/process")
def process_post(req: ProcessRequest):
    return {
        "message": "Đã nhận văn bản thành công!",
        "input_text": req.text,
        "status": "success",
        "analysis": f"Văn bản có {len(req.text or '')} ký tự."
    }

@app.get("/api/process-file")
@app.post("/api/process-file")
def process_file():
    return {"message": "API thu hai nhan File"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=3001, reload=True)

