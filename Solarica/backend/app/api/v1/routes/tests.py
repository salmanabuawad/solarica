from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def placeholder():
    return {"module": "tests", "status": "todo"}
