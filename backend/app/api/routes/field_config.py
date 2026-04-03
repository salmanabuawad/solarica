from __future__ import annotations
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories import field_config_repo

router = APIRouter()


class FieldConfigItem(BaseModel):
    grid_name:    str
    field_name:   str
    visible:      bool = True
    width:        Optional[int] = None
    column_order: Optional[int] = None


class FieldConfigOut(FieldConfigItem):
    id: int

    class Config:
        from_attributes = True


@router.get("", response_model=List[FieldConfigOut])
def get_field_configs(
    grid_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    if grid_name:
        rows = field_config_repo.get_all(db, grid_name)
    else:
        rows = field_config_repo.get_all_grids(db)
    return [r.to_dict() for r in rows]


@router.put("", response_model=dict)
def save_field_configs(
    items: List[FieldConfigItem],
    db: Session = Depends(get_db),
):
    count = field_config_repo.bulk_upsert(db, [i.dict() for i in items])
    return {"saved": count}
