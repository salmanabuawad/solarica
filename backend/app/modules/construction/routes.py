"""Placeholder — see the module __init__ docstring for scope."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
def module_status() -> dict:
    return {"module": "construction", "phase": 3, "stage": "not_implemented"}
