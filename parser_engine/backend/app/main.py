from fastapi import FastAPI, UploadFile

from app.parsers.design.unified_scan_adapter import plain_text_stub_scan

app = FastAPI()


@app.post("/scan")
async def scan(file: UploadFile):
    content = await file.read()
    text = content.decode(errors="ignore")
    return plain_text_stub_scan(text)
