from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def placeholder():
    return {"module": "progress", "status": "todo"}
