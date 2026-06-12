"""Downscale stored string photos so they stay small for offline field use.

Field crews upload phone photos (often several MB) over slow links, and the
whole project bundle is cached in IndexedDB on every device. A single helper,
``shrink_image_to_max``, caps each stored image at ~100 KB. It is used both by
the live upload endpoint and by the one-shot batch that recompresses images
captured before this was added.
"""
from __future__ import annotations

import io

from PIL import Image, ImageOps

DEFAULT_MAX_BYTES = 100_000  # bytes — "max 100k" under any reading (< 100 KiB too)
MAX_DIMENSION = 1600  # px, cap on the longest side
# Quality ladder: try high quality first, step down only as needed.
_QUALITY_STEPS = (85, 75, 65, 55, 45, 38, 30)


def _flatten_to_rgb(img: "Image.Image") -> "Image.Image":
    """Return an RGB image, compositing any alpha onto white (JPEG has no alpha)."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def shrink_image_to_max(content: bytes, max_bytes: int = DEFAULT_MAX_BYTES) -> tuple[bytes, bool]:
    """Return ``(bytes, changed)``.

    Images already at or under ``max_bytes`` are returned untouched. Larger ones
    are re-encoded as JPEG: the longest side is capped at ``MAX_DIMENSION`` and
    quality is stepped down until the result fits, with progressive dimension
    shrinking as a last resort. Undecodable input is returned unchanged.
    """
    if len(content) <= max_bytes:
        return content, False
    try:
        img = Image.open(io.BytesIO(content))
        img = ImageOps.exif_transpose(img)  # honor camera rotation before dropping EXIF
    except Exception:
        return content, False  # not a decodable image — leave it alone

    img = _flatten_to_rgb(img)
    if max(img.size) > MAX_DIMENSION:
        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)

    def encode(im: "Image.Image", quality: int) -> bytes:
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
        return buf.getvalue()

    best = None
    for quality in _QUALITY_STEPS:
        best = encode(img, quality)
        if len(best) <= max_bytes:
            return best, True

    # Still too big at lowest quality: keep shrinking dimensions.
    im = img
    while max(im.size) > 320 and len(best) > max_bytes:
        im = im.resize(
            (max(1, int(im.size[0] * 0.8)), max(1, int(im.size[1] * 0.8))),
            Image.Resampling.LANCZOS,
        )
        best = encode(im, 32)
    return best, True
