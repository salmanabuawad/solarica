from fastapi import APIRouter

router = APIRouter()

@router.get("")
def get_branding():
    return {
        "name": "Solarica",
        "tagline": "From Design to Operation",
        "positioning": "The Solar Operating System"
    }
