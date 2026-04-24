"""Placeholder EPL router.

The real EPL behaviour still lives in `backend/app/main.py`; this module
is a target home for that code once the module migration lands.
Subscribers can already register here since the event bus is live.
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
def epl_status() -> dict:
    return {"module": "epl", "phase": 2, "stage": "shipped_in_main"}
