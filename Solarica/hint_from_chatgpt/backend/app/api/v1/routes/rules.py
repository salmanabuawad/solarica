from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def placeholder():
    return {"module": "rules", "status": "todo"}
