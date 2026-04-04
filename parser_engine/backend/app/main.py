from fastapi import FastAPI, UploadFile

from app.parsers.design.final_engine import run

app = FastAPI()


@app.post("/scan")
async def scan(file: UploadFile):
    content = await file.read()
    text = content.decode(errors="ignore")
    return run(text)
