from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def placeholder():
    return {"module": "auth", "status": "todo"}
