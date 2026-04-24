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
    cv2.imwrite(str(path), img)

def polygon_to_points(poly):
    return [{"x": float(x), "y": float(y)} for x, y in list(poly.exterior.coords)]

def bbox_from_polygon(poly):
    minx, miny, maxx, maxy = poly.bounds
    return {"x": float(minx), "y": float(miny), "w": float(maxx-minx), "h": float(maxy-miny)}
