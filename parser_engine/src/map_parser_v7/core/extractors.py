from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from pypdf import PdfReader


def extract_pdf_text(files: list[str]) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    combined_texts: list[str] = []
    for file_path in files:
        path = Path(file_path)
        reader = PdfReader(str(path))
        for page_no, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append({"file": str(path), "page_number": page_no, "text": text, "words": []})
            combined_texts.append(text)

    return {"kind": "pdf", "pages": pages, "text": "\n".join(combined_texts)}


def extract_dxf_text(files: list[str]) -> dict[str, Any]:
    try:
        import ezdxf  # type: ignore
    except Exception as exc:
        raise RuntimeError("DXF support requires ezdxf. Install with: pip install -e .[dxf]") from exc

    pages: list[dict[str, Any]] = []
    texts: list[str] = []
    for file_path in files:
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()
        words = []
        for entity in msp:
            if entity.dxftype() in {"TEXT", "MTEXT"}:
                txt = entity.dxf.text if hasattr(entity.dxf, "text") else getattr(entity, "text", "")
                txt = str(txt)
                if txt:
                    texts.append(txt)
                    ins = getattr(entity.dxf, "insert", None)
                    x = float(ins.x) if ins else 0.0
                    y = float(ins.y) if ins else 0.0
                    words.append({"text": txt, "x0": x, "top": y, "x1": x + 1.0, "bottom": y + 1.0, "page_width": 1.0, "page_height": 1.0})
        pages.append({"file": file_path, "page_number": 1, "text": "\n".join(texts), "words": words})
    return {"kind": "dxf", "pages": pages, "text": "\n".join(texts)}


def optional_ocr_pdf(files: list[str]) -> dict[str, Any]:
    try:
        from pdf2image import convert_from_path  # type: ignore
        import pytesseract  # type: ignore
    except Exception as exc:
        raise RuntimeError("OCR support requires pdf2image + pytesseract. Install with: pip install -e .[ocr]") from exc

    pages: list[dict[str, Any]] = []
    texts: list[str] = []
    for file_path in files:
        images = convert_from_path(file_path)
        for i, img in enumerate(images, start=1):
            text = pytesseract.image_to_string(img)
            texts.append(text)
            pages.append({"file": file_path, "page_number": i, "text": text, "words": []})
    return {"kind": "pdf_ocr", "pages": pages, "text": "\n".join(texts)}
