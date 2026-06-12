from pathlib import Path
import json
import cv2

def ensure_dir(path):
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

def save_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def save_image(path, img):
    # cv2's default PNG compression is level 1 (fast but ~2x larger on disk).
    # These are all debug/intermediate renders, so use level 9 — still lossless,
    # roughly half the bytes. JPEG would be worse here (line-art/text overlays).
    path = str(path)
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    if ext == "png":
        cv2.imwrite(path, img, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    elif ext in ("jpg", "jpeg"):
        cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    else:
        cv2.imwrite(path, img)

def polygon_to_points(poly):
    return [{"x": float(x), "y": float(y)} for x, y in list(poly.exterior.coords)]

def bbox_from_polygon(poly):
    minx, miny, maxx, maxy = poly.bounds
    return {"x": float(minx), "y": float(miny), "w": float(maxx-minx), "h": float(maxy-miny)}
