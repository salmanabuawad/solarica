from pydantic import BaseModel

class MobileHomeResponse(BaseModel):
    role: str
    cards: list[str]
