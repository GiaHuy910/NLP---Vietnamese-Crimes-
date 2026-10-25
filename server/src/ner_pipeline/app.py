from fastapi import FastAPI, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from typing import Optional

# Import the pipeline orchestrator.
from server.src.ner_pipeline.pipeline import LegalExtractionPipeline

app = FastAPI(
    title="API Trích xuất Thực thể & Sự kiện Pháp luật",
    description="Backend xử lý NLP cho bài toán vi phạm pháp luật tiếng Việt"
)

# Initialize the pipeline once at module load so the model is loaded only once.
nlp_pipeline = LegalExtractionPipeline()


# 1. Define the request body for text input.
class TextProcessRequest(BaseModel):
    input: str

    class Config:
        json_schema_extra = {
            "example": {
                "input": "Ngày 15/8, Công an quận Đống Đa đã khởi tố và bắt tạm giam Nguyễn Văn A vì tội lừa đảo chiếm đoạt tài sản."
            }
        }


# =====================================================================
# ENDPOINT 1: /api/process (Process submitted text)
# =====================================================================
@app.post("/api/process", summary="Xử lý chuỗi văn bản nhập từ Client")
@app.get("/api/process", summary="Xử lý chuỗi văn bản (Hỗ trợ fallback GET)")
def process_text_endpoint(payload: TextProcessRequest):
    text = payload.input
    
    if not text or not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Trường 'input' không được để trống."
        )
    
    # Run NER and event extraction.
    result = nlp_pipeline.process(text)
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=result["error"]
        )
        
    return result


# =====================================================================
# ENDPOINT 2: /api/process-file (Process an uploaded file buffer)
# =====================================================================
@app.post("/api/process-file", summary="Xử lý file văn bản nạp từ Client")
@app.get("/api/process-file", summary="Xử lý file văn bản (Hỗ trợ fallback GET)")
async def process_file_endpoint(file: UploadFile = File(...)):
    try:
        # Read the raw buffer uploaded by the client.
        file_bytes = await file.read()
        
        # Decode the buffer as UTF-8 text.
        text = file_bytes.decode("utf-8")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không thể đọc buffer hoặc định dạng file không hỗ trợ UTF-8: {str(e)}"
        )

    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Nội dung file rỗng."
        )

    # Run the processing pipeline.
    result = nlp_pipeline.process(text)
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=result["error"]
        )

    return result