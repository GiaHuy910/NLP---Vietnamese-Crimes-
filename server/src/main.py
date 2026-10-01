from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Xin chào, đây là API đầu tiên của tôi!"}

@app.get("/api/process")
def process():
    return {"message": "API thu nhat nhan input"}

@app.get("/api/process-file")
def process():
    return {"message":"API thu hai nhan File"}
