"""User preferences endpoints (language, etc.)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth_deps import get_current_user
from database import get_db_connection

router = APIRouter()


class PreferencesResponse(BaseModel):
    language: str


class PreferencesPatch(BaseModel):
    language: str


@router.get("", response_model=PreferencesResponse)
def get_preferences(
    user: dict = Depends(get_current_user),
    conn=Depends(get_db_connection),
):
    """Return the current user's preferences."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT language FROM user_preferences WHERE user_id = %s",
            (user["id"],),
        )
        row = cur.fetchone()
    return PreferencesResponse(language=row[0] if row else "en")


@router.patch("", response_model=PreferencesResponse)
def update_preferences(
    body: PreferencesPatch,
    user: dict = Depends(get_current_user),
    conn=Depends(get_db_connection),
):
    """Upsert the current user's preferences."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_preferences (user_id, language, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE
                SET language = EXCLUDED.language,
                    updated_at = NOW()
            """,
            (user["id"], body.language),
        )
    conn.commit()
    return PreferencesResponse(language=body.language)
