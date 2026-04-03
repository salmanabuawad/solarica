from fastapi import Request

def get_language(request: Request) -> str:
    lang = request.headers.get("Accept-Language", "en")
    return lang.split(",")[0][:2]
