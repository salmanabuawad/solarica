"""Electrical-device endpoints for the security phase.

The `/electrical-devices` endpoint extracts DCCB (DC Combiner Box) and
inverter positions from the project's uploaded construction PDF.  DCCB
positions come straight from text labels like `DCCB_1.1.1`, and
inverter positions are inferred as the centroid of each DCCB group
sharing the same leading INV index (see `electrical_parser`).

If the project has no construction PDF (or the file is missing on disk)
we return empty lists rather than 500-ing — the map layers simply stay
empty and the user sees no markers.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services import db_store
from .electrical_parser import extract_dccb, infer_inverters_from_dccb

router = APIRouter()


def _text_words_from_pdf(pdf_path: str) -> list[dict]:
    """Flatten every PDF page's *word-level* text hits to the
    {text, x, y} shape the electrical parser expects.  `x`, `y` are the
    top-left corner of the word in PDF points (the same coordinate
    space the tracker/pier parser uses, so DCCB and inverter markers
    line up with the existing map overlay without any extra transform).

    We use `get_text("words")` rather than `"blocks"` because the
    construction-set PDFs we've seen emit DCCB labels as isolated words,
    not as paragraph blocks — block extraction came back empty for
    Ashalim despite 283 `DCCB_*` labels being present.
    """
    try:
        import fitz  # PyMuPDF
    except Exception:
        return []
    out: list[dict] = []
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                # `words` returns (x0, y0, x1, y1, text, block_no, line_no, word_no)
                for w in page.get_text("words") or []:
                    if len(w) < 5:
                        continue
                    text = (w[4] or "").strip()
                    if not text:
                        continue
                    out.append({"text": text, "x": float(w[0]), "y": float(w[1])})
    except Exception:
        return []
    return out


@router.get("/projects/{project_id}/electrical-devices")
def get_electrical_devices(project_id: str) -> dict:
    uuid = db_store.get_project_uuid(project_id)
    if not uuid:
        raise HTTPException(status_code=404, detail="Project not found")

    # DCCB labels may live in the construction PDF OR the ramming PDF
    # depending on how the project was drawn.  Ashalim has them in the
    # ramming PDF; another site might put them in the electrical layer
    # of the construction PDF.  Scan every uploaded PDF for this project
    # and union the hits.
    files = db_store.list_project_files(uuid)
    pdf_paths = [
        f["storage_path"]
        for f in files
        if f.get("storage_path", "").lower().endswith(".pdf")
    ]
    if not pdf_paths:
        return {"dccb": [], "inverters": []}

    text_blocks: list[dict] = []
    for p in pdf_paths:
        text_blocks.extend(_text_words_from_pdf(p))
    try:
        dccb = extract_dccb(text_blocks)
        inverters = infer_inverters_from_dccb(dccb)
    except Exception as e:
        # Never 500 for a malformed label — return what we have so the
        # UI can at least show the good ones.  Log to stderr so the
        # operator can trace the bad row during dev.
        import sys
        print(f"[electrical_parser] failed: {e!r}", file=sys.stderr)
        dccb, inverters = [], []
    return {"dccb": dccb, "inverters": inverters}
