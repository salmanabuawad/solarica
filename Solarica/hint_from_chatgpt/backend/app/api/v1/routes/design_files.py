from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def placeholder():
    return {"module": "design_files", "status": "todo"}
