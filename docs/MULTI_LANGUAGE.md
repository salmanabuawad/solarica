# Multi-Language (i18n) Support

## Goals
- Full UI translation (React)
- API responses localized (optional)
- Store content per language where needed
- RTL support (Hebrew/Arabic)

## Frontend (React)
Use i18next.

Structure:
frontend/src/i18n/
  en.json
  he.json
  ar.json

Example:
{
  "app.title": "Solarica",
  "tagline": "From Design to Operation",
  "menu.tasks": "Tasks"
}

Setup:
- detect language from browser or user profile
- allow manual switch
- persist selection

## Backend (FastAPI)
- Read `Accept-Language` header
- Provide helper to choose language
- Optional: translate system messages

## DB Strategy
- Static labels → frontend JSON
- Dynamic content:
  - either store default language
  - or use translation table:
    translations(entity, field, lang, value)

## RTL Support
- auto switch dir="rtl" for he/ar
- CSS support required

## Modules
Each module can include:
- frontend/i18n/en.json
- frontend/i18n/he.json

Loaded dynamically by module loader.

## Recommendation
Start with:
- English + Hebrew
Then extend to Arabic.