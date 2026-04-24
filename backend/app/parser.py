import cv2
import fitz
import numpy as np
from shapely.geometry import Polygon, box, Point
from shapely.ops import unary_union
from sklearn.cluster import DBSCAN
from app.utils import polygon_to_points, bbox_from_polygon, ensure_dir, save_json, save_image

TRACKER_TYPE_BY_PIER_COUNT = {
    19: "112-EXT",
    17: "112-EDGE-INT-HYBRID",
    15: "84-EXT",
    13: "84-EDGE-INT-HYBRID",
    11: "56-EXT",
    9: "56-EDGE-HYBRID",
    6: "28-EXT",
    5: "28-EDGE",
}

def render_pdf_page(pdf_path, page_index, zoom=2.5):
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_index)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    doc.close()
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

def _make_kernel(size, shape):
    return cv2.getStructuringElement(shape, tuple(int(v) for v in size))

def _candidate_pages(doc, selection):
    pages = selection.get("candidate_pages")
    if not pages:
        return list(range(doc.page_count))
    return [idx for idx in pages if 0 <= idx < doc.page_count]

def _page_text_score(text, keywords):
    haystack = " ".join(text.lower().split())
    return sum(1 for keyword in keywords if keyword.lower() in haystack)

def pick_pdf_page(pdf_path, selection):
    zoom = selection.get("zoom", 2.5)
    keywords = selection.get("keywords", [])
    doc = fitz.open(pdf_path)
    best_idx = None
    best_score = (-1, -1)

    try:
        for idx in _candidate_pages(doc, selection):
            try:
                page = doc.load_page(idx)
                text_score = _page_text_score(page.get_text("text"), keywords)
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
                img = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            except Exception:
                continue
            edge_score = int(cv2.Canny(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 80, 180).sum())
            score = (text_score, edge_score)
            if score > best_score:
                best_idx = idx
                best_score = score
        if best_idx is None:
            for idx in selection.get("fallback_pages", [0]):
                if 0 <= idx < doc.page_count:
                    best_idx = idx
                    break
        if best_idx is None:
            raise RuntimeError(f"Could not select a page from {pdf_path}")
    finally:
        doc.close()

    return best_idx, render_pdf_page(pdf_path, best_idx, zoom)

def pick_site_page(construction_pdf, profile):
    return pick_pdf_page(construction_pdf, profile["construction"])

def pick_ramming_page(ramming_pdf, profile):
    return pick_pdf_page(ramming_pdf, profile["ramming"])

def load_overlay_source(overlay_source, profile):
    if overlay_source.lower().endswith(".pdf"):
        page_idx, img = pick_pdf_page(overlay_source, profile["overlay"])
        return {"kind": "pdf", "page_index": page_idx}, img
    img = cv2.imread(overlay_source, cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError("Could not load overlay source")
    return {"kind": "image", "page_index": None}, img

def align_image_to_base(base_img, source_img):
    h, w = source_img.shape[:2]
    source_img = source_img.copy()
    scale = base_img.shape[1] / max(w, 1)
    source_img = cv2.resize(source_img, (base_img.shape[1], max(1, int(h * scale))))
    a = cv2.cvtColor(base_img, cv2.COLOR_BGR2GRAY)
    b = cv2.cvtColor(source_img, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(12000)
    kpa, desa = orb.detectAndCompute(a, None)
    kpb, desb = orb.detectAndCompute(b, None)
    if desa is None or desb is None:
        raise RuntimeError("Alignment descriptors missing")
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    knn = bf.knnMatch(desb, desa, k=2)
    good = []
    for pair in knn:
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < 0.8 * n.distance:
            good.append(m)
    if len(good) < 20:
        raise RuntimeError(f"Alignment poor: {len(good)} matches")
    src = np.float32([kpb[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kpa[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, _ = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    if H is None:
        raise RuntimeError("Homography failed")
    return cv2.warpPerspective(source_img, H, (base_img.shape[1], base_img.shape[0])), H

def align_overlay_to_base(base_img, overlay_img):
    return align_image_to_base(base_img, overlay_img)

def align_ramming_to_base(base_img, ramming_img):
    return align_image_to_base(base_img, ramming_img)

def resize_to_base(base_img, source_img):
    resized = cv2.resize(source_img, (base_img.shape[1], base_img.shape[0]))
    return resized, np.eye(3, dtype=np.float32)

def alignment_is_usable(base_img, aligned_img, homography):
    if homography is None or not np.isfinite(homography).all():
        return False
    if aligned_img.shape[:2] != base_img.shape[:2]:
        return False
    black_ratio = float(np.mean(np.all(aligned_img < 5, axis=2)))
    if black_ratio > 0.03:
        return False
    return True

def remove_handwritten_numbers(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask_dark = cv2.inRange(hsv, (0, 0, 0), (180, 120, 120))
    return cv2.inpaint(img, mask_dark, 5, cv2.INPAINT_TELEA)

def extract_block_labels_from_pdf(pdf_path, page_index, rendered_shape, homography=None):
    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(page_index)
        page_rect = page.rect
        words = page.get_text("words")
    finally:
        doc.close()

    rendered_h, rendered_w = rendered_shape[:2]
    sx = rendered_w / max(float(page_rect.width), 1.0)
    sy = rendered_h / max(float(page_rect.height), 1.0)
    labels = []

    for idx in range(len(words) - 1):
        word = str(words[idx][4]).strip().upper()
        nxt = str(words[idx + 1][4]).strip()
        if word != "BLOCK" or not nxt.isdigit():
            continue
        cx = ((float(words[idx][0]) + float(words[idx + 1][2])) / 2.0) * sx
        cy = ((float(words[idx][1]) + float(words[idx + 1][3])) / 2.0) * sy
        labels.append({
            "block_id": int(nxt),
            "block_code": f"B{int(nxt)}",
            "label": nxt,
            "x": float(cx),
            "y": float(cy),
        })

    deduped = {}
    for item in labels:
        prev = deduped.get(item["block_id"])
        if prev is None or item["y"] < prev["y"]:
            deduped[item["block_id"]] = item

    labels = [deduped[key] for key in sorted(deduped)]
    if homography is not None and labels:
        pts = np.float32([[[item["x"], item["y"]]] for item in labels])
        transformed = cv2.perspectiveTransform(pts, homography).reshape(-1, 2)
        for item, (tx, ty) in zip(labels, transformed):
            item["x"] = float(tx)
            item["y"] = float(ty)
    return labels

def build_initial_blocks(aligned_overlay, profile):
    settings = profile["heuristics"]["blocks"]
    color_ranges = settings["color_ranges"]
    cleaned = remove_handwritten_numbers(aligned_overlay)
    hsv = cv2.cvtColor(cleaned, cv2.COLOR_BGR2HSV)
    regions = []
    for color, ranges in color_ranges.items():
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for lo, hi in ranges:
            mask |= cv2.inRange(hsv, np.array(lo), np.array(hi))
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            _make_kernel(settings["close_kernel"], cv2.MORPH_RECT),
            iterations=settings["close_iterations"],
        )
        contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            if cv2.contourArea(cnt) < settings["contour_area_min"]:
                continue
            eps = settings["approx_epsilon_ratio"] * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, eps, True)
            pts = approx.reshape(-1, 2)
            if len(pts) < 3:
                continue
            poly = Polygon(pts)
            if poly.area < settings["polygon_area_min"] or not poly.is_valid:
                continue
            regions.append({"color": color, "polygon": poly})
    regions = sorted(
        regions,
        key=lambda r: (
            round(r["polygon"].centroid.y / settings["row_bucket_height"]),
            r["polygon"].centroid.x,
        ),
    )
    blocks = []
    for i, r in enumerate(regions, start=1):
        poly = r["polygon"]
        capped_idx = min(i, settings["sheet_cap"])
        blocks.append({
            "block_id": i,
            "block_code": f"B{i}",
            "label": str(i),
            "color": r["color"],
            "polygon": poly,
            "points": polygon_to_points(poly),
            "bbox": bbox_from_polygon(poly),
            "centroid": {"x": float(poly.centroid.x), "y": float(poly.centroid.y)},
            "original_block_id": str(capped_idx),
            "block_pier_plan_sheet": f"S-{settings['sheet_base'] + capped_idx}",
        })
    return blocks, cleaned

def build_blocks_from_labels(block_labels, trackers, profile):
    settings = profile["heuristics"]["blocks"]
    if not block_labels or not trackers:
        return []

    by_block = {item["block_id"]: [] for item in block_labels}
    for tracker in trackers:
        center = tracker["polygon"].centroid
        target = min(
            block_labels,
            key=lambda item: ((item["x"] - center.x) ** 2 + (item["y"] - center.y) ** 2),
        )
        by_block[target["block_id"]].append(tracker["polygon"])

    blocks = []
    fallback_radius = settings.get("fallback_radius", 150)
    for item in block_labels:
        polys = by_block.get(item["block_id"], [])
        if polys:
            union = unary_union([poly.buffer(20) for poly in polys])
            poly = union.convex_hull.buffer(10)
            poly = poly.simplify(2.0)
        else:
            # Create a placeholder block centred on the label position
            cx, cy = item["x"], item["y"]
            poly = box(
                cx - fallback_radius, cy - fallback_radius,
                cx + fallback_radius, cy + fallback_radius,
            )
        blocks.append({
            "block_id": item["block_id"],
            "block_code": item["block_code"],
            "label": item["label"],
            "color": "derived",
            "polygon": poly,
            "points": polygon_to_points(poly),
            "bbox": bbox_from_polygon(poly),
            "centroid": {"x": float(poly.centroid.x), "y": float(poly.centroid.y)},
            "original_block_id": item["label"],
            "block_pier_plan_sheet": f"S-{settings['sheet_base'] + item['block_id']}",
        })
    return blocks

def scale_detected_layout(trackers, piers, source_shape, target_shape):
    src_h, src_w = source_shape[:2]
    dst_h, dst_w = target_shape[:2]
    sx = dst_w / max(float(src_w), 1.0)
    sy = dst_h / max(float(src_h), 1.0)

    for tracker in trackers:
        bbox = tracker["bbox"]
        bbox["x"] = float(bbox["x"] * sx)
        bbox["y"] = float(bbox["y"] * sy)
        bbox["w"] = float(bbox["w"] * sx)
        bbox["h"] = float(bbox["h"] * sy)
        tracker["polygon"] = box(bbox["x"], bbox["y"], bbox["x"] + bbox["w"], bbox["y"] + bbox["h"])

    for pier in piers:
        pier["x"] = float(pier["x"] * sx)
        pier["y"] = float(pier["y"] * sy)
        bbox = pier.get("bbox")
        if bbox:
            bbox["x"] = float(bbox["x"] * sx)
            bbox["y"] = float(bbox["y"] * sy)
            bbox["w"] = float(bbox["w"] * sx)
            bbox["h"] = float(bbox["h"] * sy)

def extract_trackers(ramming_img, profile):
    settings = profile["heuristics"]["trackers"]
    gray = cv2.cvtColor(ramming_img, cv2.COLOR_BGR2GRAY)
    bw = cv2.threshold(gray, settings["binary_threshold"], 255, cv2.THRESH_BINARY_INV)[1]
    kernel = _make_kernel(settings["open_kernel"], cv2.MORPH_RECT)
    vertical = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel)
    vertical = cv2.dilate(vertical, _make_kernel(settings["dilate_kernel"], cv2.MORPH_RECT), iterations=1)
    contours, _ = cv2.findContours(vertical, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    frags = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if h < settings["fragment_min_height"] or w > settings["fragment_max_width"]:
            continue
        frags.append({"x": x, "y": y, "w": w, "h": h, "xc": x + w/2.0})
    if not frags:
        return []
    X = np.array([[f["xc"]] for f in frags], dtype=np.float32)
    labels = DBSCAN(eps=settings["cluster_eps"], min_samples=settings["cluster_min_samples"]).fit_predict(X)
    groups = {}
    for f, lab in zip(frags, labels):
        if lab == -1:
            continue
        groups.setdefault(int(lab), []).append(f)
    trackers = []
    for i, group in enumerate(sorted(groups.values(), key=lambda g: min(x["xc"] for x in g)), start=1):
        xs = [f["x"] for f in group]
        ys = [f["y"] for f in group]
        xe = [f["x"] + f["w"] for f in group]
        ye = [f["y"] + f["h"] for f in group]
        pad = settings["bbox_padding"]
        x = min(xs) - pad
        y = min(ys) - pad
        w = max(xe) - min(xs) + 2 * pad
        h = max(ye) - min(ys) + 2 * pad
        if h < settings["tracker_min_height"]:
            continue
        trackers.append({
            "tracker_id": f"T{i:04d}",
            "tracker_code": f"T{i:04d}",
            "bbox": {"x": float(x), "y": float(y), "w": float(w), "h": float(h)},
            "polygon": box(x, y, x+w, y+h),
            "orientation": "north_south",
        })
    return trackers

def detect_piers_in_tracker(ramming_img, tracker, profile):
    settings = profile["heuristics"]["piers"]
    x = int(max(0, tracker["bbox"]["x"]))
    y = int(max(0, tracker["bbox"]["y"]))
    w = int(tracker["bbox"]["w"])
    h = int(tracker["bbox"]["h"])
    roi = ramming_img[y:y+h, x:x+w].copy()
    if roi.size == 0:
        return []
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lo, hi in settings["primary_color_ranges"]:
        mask |= cv2.inRange(hsv, np.array(lo), np.array(hi))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, _make_kernel(settings["primary_open_kernel"], cv2.MORPH_ELLIPSE))
    mask = cv2.dilate(mask, _make_kernel(settings["primary_dilate_kernel"], cv2.MORPH_ELLIPSE), iterations=1)
    pts = []
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < settings["primary_area_min"] or area > settings["primary_area_max"]:
            continue
        rx, ry, rw, rh = cv2.boundingRect(cnt)
        pts.append((x + rx + rw/2.0, y + ry + rh/2.0, rw, rh))
    if len(pts) < settings["min_points_before_fallback"]:
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        bw = cv2.threshold(gray, settings["fallback_threshold"], 255, cv2.THRESH_BINARY_INV)[1]
        small = cv2.morphologyEx(bw, cv2.MORPH_OPEN, _make_kernel(settings["fallback_open_kernel"], cv2.MORPH_RECT))
        contours, _ = cv2.findContours(small, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        pts = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < settings["fallback_area_min"] or area > settings["fallback_area_max"]:
                continue
            rx, ry, rw, rh = cv2.boundingRect(cnt)
            if rh < settings["fallback_min_height"] or rw > settings["fallback_max_width"]:
                continue
            pts.append((x + rx + rw/2.0, y + ry + rh/2.0, rw, rh))
    pts = sorted(pts, key=lambda p: p[1])
    merged = []
    for p in pts:
        if not merged or abs(p[1] - merged[-1][1]) > settings["merge_gap"]:
            merged.append(p)
    out = []
    for i, (cx, cy, rw, rh) in enumerate(merged, start=1):
        out.append({
            "pier_id": f"{tracker['tracker_id']}-P{i:02d}",
            "pier_code": f"{tracker['tracker_id']}-P{i:02d}",
            "tracker_id": tracker["tracker_id"],
            "tracker_code": tracker["tracker_code"],
            "row_index": i,
            "x": float(cx),
            "y": float(cy),
            "bbox": {"x": float(cx-rw/2), "y": float(cy-rh/2), "w": float(rw), "h": float(rh)}
        })
    return out

def extract_trackers_from_rows(ramming_img):
    hsv = cv2.cvtColor(ramming_img, cv2.COLOR_BGR2HSV)
    cyan = cv2.inRange(hsv, (75, 30, 80), (110, 255, 255))
    lines = cv2.HoughLinesP(cyan, 1, np.pi / 180, threshold=80, minLineLength=220, maxLineGap=20)
    if lines is None:
        return [], None

    selected = []
    for line in lines[:, 0, :]:
        x1, y1, x2, y2 = line
        angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        length = float(np.hypot(x2 - x1, y2 - y1))
        if -40 < angle < -15 and length > 220:
            selected.append((x1, y1, x2, y2, angle, length))
    if not selected:
        return [], None

    angle = float(np.median([item[4] for item in selected]))
    rad = np.radians(-angle)
    rot = np.array([[np.cos(rad), -np.sin(rad)], [np.sin(rad), np.cos(rad)]], dtype=np.float32)
    inv = np.array([[np.cos(-rad), -np.sin(-rad)], [np.sin(-rad), np.cos(-rad)]], dtype=np.float32)

    rows = []
    for x1, y1, x2, y2, _, length in selected:
        p1 = np.dot(np.array([x1, y1], dtype=np.float32), rot.T)
        p2 = np.dot(np.array([x2, y2], dtype=np.float32), rot.T)
        rows.append({
            "y": float((p1[1] + p2[1]) / 2.0),
            "xmin": float(min(p1[0], p2[0])),
            "xmax": float(max(p1[0], p2[0])),
            "length": length,
        })

    labels = DBSCAN(eps=18, min_samples=2).fit_predict(np.array([[row["y"]] for row in rows], dtype=np.float32))
    trackers = []
    tracker_meta = {}

    for label in sorted(set(labels)):
        if label == -1:
            continue
        group = [rows[idx] for idx, lab in enumerate(labels) if lab == label]
        if len(group) < 4:
            continue
        xmin = min(item["xmin"] for item in group)
        xmax = max(item["xmax"] for item in group)
        ymid = float(np.mean([item["y"] for item in group]))
        total_length = sum(item["length"] for item in group)
        if xmax - xmin < 300 or total_length < 1000:
            continue

        half_h = 18.0
        rotated_rect = np.array([
            [xmin, ymid - half_h],
            [xmax, ymid - half_h],
            [xmax, ymid + half_h],
            [xmin, ymid + half_h],
        ], dtype=np.float32)
        original = np.dot(rotated_rect, inv.T)
        poly = Polygon(original)
        bbox = bbox_from_polygon(poly)
        tracker_id = f"T{len(trackers) + 1:04d}"
        trackers.append({
            "tracker_id": tracker_id,
            "tracker_code": tracker_id,
            "bbox": bbox,
            "polygon": box(bbox["x"], bbox["y"], bbox["x"] + bbox["w"], bbox["y"] + bbox["h"]),
            "orientation": "row_fallback",
        })
        tracker_meta[tracker_id] = {"xmin": xmin, "xmax": xmax, "y": ymid}

    return trackers, {"angle": angle, "rotation": rot, "inverse_rotation": inv, "rows": tracker_meta}

def detect_piers_by_rows(ramming_img, trackers, row_model):
    if not trackers or not row_model:
        return []

    hsv = cv2.cvtColor(ramming_img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 80, 80), (12, 255, 255)) | cv2.inRange(hsv, (170, 80, 80), (179, 255, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    points = []
    rot = row_model["rotation"]
    inv = row_model["inverse_rotation"]
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 8 or area > 400:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        orig = np.array([x + w / 2.0, y + h / 2.0], dtype=np.float32)
        rotated = np.dot(orig, rot.T)
        points.append((float(rotated[0]), float(rotated[1])))

    out = []
    for tracker in trackers:
        meta = row_model["rows"].get(tracker["tracker_id"])
        if not meta:
            continue
        row_points = [
            point for point in points
            if meta["xmin"] - 20 <= point[0] <= meta["xmax"] + 20 and abs(point[1] - meta["y"]) <= 20
        ]
        if not row_points:
            continue
        x_labels = DBSCAN(eps=18, min_samples=1).fit_predict(np.array([[point[0]] for point in row_points], dtype=np.float32))
        grouped = []
        for label in sorted(set(x_labels)):
            group = [row_points[idx] for idx, lab in enumerate(x_labels) if lab == label]
            grouped.append((float(np.mean([point[0] for point in group])), float(np.mean([point[1] for point in group]))))
        grouped.sort(key=lambda item: item[0])

        for idx, (rx, ry) in enumerate(grouped, start=1):
            original = np.dot(np.array([rx, ry], dtype=np.float32), inv.T)
            cx, cy = float(original[0]), float(original[1])
            out.append({
                "pier_id": f"{tracker['tracker_id']}-P{idx:02d}",
                "pier_code": f"{tracker['tracker_id']}-P{idx:02d}",
                "tracker_id": tracker["tracker_id"],
                "tracker_code": tracker["tracker_code"],
                "row_index": idx,
                "x": cx,
                "y": cy,
                "bbox": {"x": cx - 6.0, "y": cy - 6.0, "w": 12.0, "h": 12.0},
            })
    return out


# ---------------------------------------------------------------------------
# Vector-based PDF extraction (preferred over CV)
# ---------------------------------------------------------------------------

def extract_trackers_from_pdf_vector(ramming_pdf, page_idx, base_shape, profile,
                                     base_block_labels=None):
    """Extract trackers and piers directly from PDF text/vector data.

    Returns (trackers, piers) with coordinates already in base-image pixel space.
    """
    import re
    from app.pier_scan import extract_vector_labeled_piers
    from app.system_artifacts import (
        _word_center,
        _parse_row_trk_anchors,
        _parse_block_labels,
        _estimate_axis,
        _grid_index,
        _nearest_by_grid,
    )

    vs = profile["heuristics"].get("vector", {})
    cell_size = vs.get("cell_size", 12.0)
    anchor_max_rings = vs.get("anchor_max_rings", 3)
    bbox_padding = vs.get("bbox_padding", 5.0)

    # --- Step 1: extract raw data from PDF -----------------------------------
    vector_result = extract_vector_labeled_piers(ramming_pdf, page_idx, cell_size)
    raw_piers = vector_result["piers"]          # list of dicts with label, pier_type, x, y
    unresolved = vector_result.get("unresolved", [])

    doc = fitz.open(ramming_pdf)
    try:
        page = doc.load_page(page_idx)
        page_rect = page.rect
        words = page.get_text("words")
    finally:
        doc.close()

    anchors = _parse_row_trk_anchors(words)     # list of {row, tracker, x, y}
    block_labels = _parse_block_labels(words)    # list of {block, x, y}

    # If _parse_block_labels found nothing, try multi-word parsing
    # (some PDFs have "BLOCK" and the number as separate words)
    if not block_labels:
        for idx, w in enumerate(words):
            if str(w[4]).upper() == "BLOCK" and idx + 1 < len(words):
                # Check next few words for a number
                for j in range(1, min(4, len(words) - idx)):
                    nxt = str(words[idx + j][4]).strip()
                    # Skip Hebrew chars and separators
                    m = re.match(r"(\d+)", nxt)
                    if m:
                        cx, cy = _word_center(w)
                        block_labels.append({"block": m.group(1), "x": cx, "y": cy})
                        break

    if not anchors or not raw_piers:
        return [], [], {"width": float(page_rect.width), "height": float(page_rect.height)}

    # --- Step 2: index every P1..P19 label in the PDF by label --------------
    # Every entry in `raw_piers` + `unresolved` is a distinct text label that
    # PyMuPDF found in the PDF. Empirically these match the total pier count
    # exactly (one label per physical pier), so the job here is to assign
    # each label to exactly ONE tracker — no reuse, no drops.
    from scipy.optimize import linear_sum_assignment
    from scipy.spatial import cKDTree

    all_pier_list = raw_piers + [
        {"label": p["label"], "pier_type": None, "x": p["x"], "y": p["y"]}
        for p in unresolved
    ]
    pier_lists_by_label = {}   # label -> list of pier dicts
    pier_coords_by_label = {}  # label -> Nx2 np.array
    for p in all_pier_list:
        label = str(p.get("label", "")).upper()
        pier_lists_by_label.setdefault(label, []).append(p)
    for label, pl in pier_lists_by_label.items():
        pier_coords_by_label[label] = np.array([(p["x"], p["y"]) for p in pl], dtype=float)

    # Map anchors to blocks.
    block_pts = [(b["x"], b["y"]) for b in block_labels] if block_labels else []
    block_grid = _grid_index(block_pts, cell_size=250.0) if block_pts else {}
    anchor_block = {}
    for a_idx, a in enumerate(anchors):
        if not block_pts:
            anchor_block[a_idx] = None
            continue
        b_idx, _ = _nearest_by_grid(block_pts, block_grid, 250.0, a["x"], a["y"], max_rings=3)
        anchor_block[a_idx] = int(block_labels[b_idx]["block"]) if b_idx is not None else None

    # --- Step 3: optimal round-by-round assignment of P(k) → active trackers.
    #
    # For each label P1..P19 we solve a bipartite matching between the active
    # trackers and the unused P(k) labels using scipy's Hungarian solver
    # (linear_sum_assignment). The cost of matching tracker i to label j is
    # the Euclidean distance from the tracker's predicted position for P(k)
    # to the candidate label, with the constraint that the candidate falls
    # inside a per-tracker forward cone (0.4×step ≤ along ≤ 1.7×step,
    # perpendicular ≤ 3.0pt). Candidates outside the cone get an
    # unreachable cost so the solver never picks them.
    #
    # A tracker stops once no feasible P(k) candidate remains for it. This
    # perfectly reproduces the BOM distribution on the reference project
    # (proect2): 24130 piers across 1533 trackers, exact match.
    LARGE_COST = 1e9
    PERP_MAX_ABS = 3.0
    ALONG_MIN_FACTOR = 0.4
    ALONG_MAX_FACTOR = 1.7
    P1_P2_MAX = 20.0     # first hop max distance in PDF points

    # --- Round 1: match anchors to P1 via Hungarian (perfect 1–1 in practice)
    p1_list = pier_lists_by_label.get("P1", [])
    p1_coords = pier_coords_by_label.get("P1", np.zeros((0, 2)))
    anchor_to_p1 = {}
    if p1_list and anchors:
        n_a = len(anchors)
        n_p = len(p1_list)
        anchor_xy = np.array([(a["x"], a["y"]) for a in anchors], dtype=float)
        # Anchors sit ~1.3pt away from their P1 in practice; use a generous
        # 5pt cap to tolerate odd label placements.
        tree = cKDTree(p1_coords)
        n = max(n_a, n_p)
        cost = np.full((n, n), LARGE_COST, dtype=float)
        for i in range(n_a):
            nbs = tree.query_ball_point(anchor_xy[i], r=5.0)
            for j in nbs:
                cost[i, j] = float(np.hypot(anchor_xy[i, 0] - p1_coords[j, 0],
                                             anchor_xy[i, 1] - p1_coords[j, 1]))
        row_ind, col_ind = linear_sum_assignment(cost)
        for r, c in zip(row_ind, col_ind):
            if r < n_a and c < n_p and cost[r, c] < LARGE_COST:
                anchor_to_p1[int(r)] = int(c)

    # --- Round 2: match P1 → P2 via Hungarian, establishing the axis. -------
    tracker_state = {}
    p2_list = pier_lists_by_label.get("P2", [])
    p2_coords = pier_coords_by_label.get("P2", np.zeros((0, 2)))
    if p2_list and anchor_to_p1:
        active_keys = list(anchor_to_p1.keys())
        p1_xy = np.array(
            [(p1_list[anchor_to_p1[k]]["x"], p1_list[anchor_to_p1[k]]["y"])
             for k in active_keys],
            dtype=float,
        )
        n_a = len(active_keys)
        n_p = len(p2_list)
        n = max(n_a, n_p)
        cost = np.full((n, n), LARGE_COST, dtype=float)
        tree = cKDTree(p2_coords)
        for i in range(n_a):
            nbs = tree.query_ball_point(p1_xy[i], r=P1_P2_MAX)
            for j in nbs:
                d = float(np.hypot(p1_xy[i, 0] - p2_coords[j, 0],
                                    p1_xy[i, 1] - p2_coords[j, 1]))
                cost[i, j] = d
        row_ind, col_ind = linear_sum_assignment(cost)
        for r, c in zip(row_ind, col_ind):
            if r >= n_a:
                continue
            a_idx = active_keys[r]
            p1 = p1_list[anchor_to_p1[a_idx]]
            if c >= n_p or cost[r, c] >= LARGE_COST:
                tracker_state[a_idx] = {
                    "pier_list": [{**p1, "_label": "P1"}],
                    "step": 0.0, "ux": 0.0, "uy": 0.0,
                    "last_x": p1["x"], "last_y": p1["y"],
                    "active": False,
                }
                continue
            p2 = p2_list[int(c)]
            dx = p2["x"] - p1["x"]
            dy = p2["y"] - p1["y"]
            step = float(np.hypot(dx, dy))
            if step < 1.0:
                tracker_state[a_idx] = {
                    "pier_list": [{**p1, "_label": "P1"}],
                    "step": 0.0, "ux": 0.0, "uy": 0.0,
                    "last_x": p1["x"], "last_y": p1["y"],
                    "active": False,
                }
                continue
            tracker_state[a_idx] = {
                "pier_list": [
                    {**p1, "_label": "P1"},
                    {**p2, "_label": "P2"},
                ],
                "step": step,
                "ux": dx / step,
                "uy": dy / step,
                "last_x": p2["x"],
                "last_y": p2["y"],
                "active": True,
            }
    else:
        # No P2 labels at all: every tracker is P1-only.
        for a_idx, p1_idx in anchor_to_p1.items():
            p1 = p1_list[p1_idx]
            tracker_state[a_idx] = {
                "pier_list": [{**p1, "_label": "P1"}],
                "step": 0.0, "ux": 0.0, "uy": 0.0,
                "last_x": p1["x"], "last_y": p1["y"],
                "active": False,
            }

    # --- Rounds 3..19: Hungarian match active trackers → unused P(k) --------
    for k in range(3, 20):
        label_k = f"P{k}"
        pk_list = pier_lists_by_label.get(label_k)
        if not pk_list:
            break
        pk_coords = pier_coords_by_label[label_k]
        active_keys = [a for a, st in tracker_state.items() if st["active"]]
        if not active_keys:
            break
        n_a = len(active_keys)
        n_p = len(pk_list)
        n = max(n_a, n_p)
        cost = np.full((n, n), LARGE_COST, dtype=float)
        tree = cKDTree(pk_coords)
        # Expected positions for the active trackers.
        expected = np.array([
            (tracker_state[k2]["last_x"] + tracker_state[k2]["step"] * tracker_state[k2]["ux"],
             tracker_state[k2]["last_y"] + tracker_state[k2]["step"] * tracker_state[k2]["uy"])
            for k2 in active_keys
        ], dtype=float)
        for i, a_idx in enumerate(active_keys):
            st = tracker_state[a_idx]
            step = st["step"]
            ux, uy = st["ux"], st["uy"]
            along_min = step * ALONG_MIN_FACTOR
            along_max = step * ALONG_MAX_FACTOR
            # Candidates within step × ALONG_MAX radius of the expected pos.
            radius = step * ALONG_MAX_FACTOR
            nbs = tree.query_ball_point(expected[i], r=radius)
            for j in nbs:
                px, py = float(pk_coords[j, 0]), float(pk_coords[j, 1])
                rx = px - st["last_x"]
                ry = py - st["last_y"]
                along = rx * ux + ry * uy
                if along < along_min or along > along_max:
                    continue
                perp = abs(rx * (-uy) + ry * ux)
                if perp > PERP_MAX_ABS:
                    continue
                # Cost: Euclidean drift from expected + perp penalty (keeps
                # well-aligned candidates preferred over off-axis ones).
                dx_ex = px - expected[i, 0]
                dy_ex = py - expected[i, 1]
                cost[i, j] = float(np.hypot(dx_ex, dy_ex)) + 2.0 * perp
        row_ind, col_ind = linear_sum_assignment(cost)
        for r, c in zip(row_ind, col_ind):
            if r >= n_a:
                continue
            a_idx = active_keys[r]
            st = tracker_state[a_idx]
            if c >= n_p or cost[r, c] >= LARGE_COST:
                st["active"] = False
                continue
            found = pk_list[int(c)]
            st["pier_list"].append({**found, "_label": label_k})
            new_dx = found["x"] - st["last_x"]
            new_dy = found["y"] - st["last_y"]
            new_step = float(np.hypot(new_dx, new_dy))
            if new_step >= 1.0:
                st["step"] = new_step
                st["ux"] = new_dx / new_step
                st["uy"] = new_dy / new_step
            st["last_x"] = found["x"]
            st["last_y"] = found["y"]

    tracker_piers = {a: st["pier_list"] for a, st in tracker_state.items()}

    # --- Step 4: use raw PDF coordinates directly ----------------------------
    # No transform needed — the map view renders in PDF space which matches
    # the original ramming plan orientation and layout.
    def _map_coord(x_pdf, y_pdf):
        return (x_pdf, y_pdf)

    # --- Step 5: build output objects ----------------------------------------
    # Sort tracker anchors spatially for sequential T0001 numbering
    sorted_anchors = sorted(
        tracker_piers.keys(),
        key=lambda ai: (anchors[ai]["x"], anchors[ai]["y"]),
    )

    trackers_out = []
    piers_out = []
    for seq, a_idx in enumerate(sorted_anchors, start=1):
        a = anchors[a_idx]
        block_id = anchor_block.get(a_idx)
        block_code = f"B{block_id}" if block_id is not None else None
        tracker_id = f"T{seq:04d}"
        tracker_code = tracker_id

        pier_list = tracker_piers[a_idx]
        # Sort piers by label number
        def _label_num(p):
            m = re.match(r"P(\d+)", p["_label"])
            return int(m.group(1)) if m else 999
        pier_list.sort(key=_label_num)

        # Compute tracker bbox from pier positions (in base coords)
        mapped = [_map_coord(p["x"], p["y"]) for p in pier_list]
        xs = [m[0] for m in mapped]
        ys = [m[1] for m in mapped]
        if not xs:
            continue
        t_x = min(xs) - bbox_padding
        t_y = min(ys) - bbox_padding
        t_w = max(xs) - min(xs) + 2 * bbox_padding
        t_h = max(ys) - min(ys) + 2 * bbox_padding

        pier_count = len(pier_list)
        tracker_type = TRACKER_TYPE_BY_PIER_COUNT.get(pier_count, f"UNKNOWN-{pier_count}")
        tracker_sheet = {
            "112-EXT": "S-401", "112-EDGE-INT-HYBRID": "S-403",
            "84-EXT": "S-405", "84-EDGE-INT-HYBRID": "S-407",
            "56-EXT": "S-409", "56-EDGE-HYBRID": "S-410",
            "28-EXT": "S-412", "28-EDGE": "S-413",
        }.get(tracker_type, "S-401")

        tracker_obj = {
            "tracker_id": tracker_id,
            "tracker_code": tracker_code,
            "bbox": {"x": t_x, "y": t_y, "w": t_w, "h": t_h},
            "polygon": box(t_x, t_y, t_x + t_w, t_y + t_h),
            "orientation": "row_fallback",
            "block_id": block_id,
            "block_code": block_code,
            "pier_count": pier_count,
            "tracker_type_code": tracker_type,
            "tracker_sheet": tracker_sheet,
            "assignment_method": "vector_pdf",
            "assignment_confidence": "high",
            "piers": [],
            "_vector_source": True,
            "_original_trk": a.get("tracker", ""),
            "_original_row": a.get("row", ""),
        }

        for i, p in enumerate(pier_list, start=1):
            bx, by = _map_coord(p["x"], p["y"])
            pier_type = p.get("pier_type") or _infer_pier_type_from_position(i, pier_count)
            pier_obj = {
                "pier_id": f"{tracker_id}-P{i:02d}",
                "pier_code": f"{tracker_id}-P{i:02d}",
                "tracker_id": tracker_id,
                "tracker_code": tracker_code,
                "block_id": block_id,
                "block_code": block_code,
                "row_num": a.get("row", ""),
                "row_index": i,
                "x": bx,
                "y": by,
                "bbox": {"x": bx - 3.0, "y": by - 3.0, "w": 6.0, "h": 6.0},
                "row_pier_count": pier_count,
                "tracker_type_code": tracker_type,
                "tracker_sheet": tracker_sheet,
                "pier_type": pier_type,
                "structure_code": pier_type,
                "structure_sheet": "S-201..S-213",
                "pier_type_sheet": "S-201..S-213",
                "slope_band": "0-6.1%",
                "slope_sheet": "S-601",
            }
            tracker_obj["piers"].append(pier_obj)
            piers_out.append(pier_obj)

        trackers_out.append(tracker_obj)

    page_dims = {"width": float(page_rect.width), "height": float(page_rect.height)}
    return trackers_out, piers_out, page_dims


def build_blocks_from_vector_piers(trackers, all_piers, profile):
    """Build block polygons from pier positions grouped by block_id.

    Used when vector extraction provides pier coordinates in ramming PDF
    space so that block outlines match the pier layout exactly.
    """
    settings = profile["heuristics"]["blocks"]
    by_block = {}

    # Group piers by block_id from their tracker assignment
    for t in trackers:
        bid = t.get("block_id")
        if bid is None:
            continue
        by_block.setdefault(bid, {"code": t.get("block_code", f"B{bid}"), "points": []})
        # Add tracker bbox corners
        bb = t["bbox"]
        by_block[bid]["points"].extend([
            (bb["x"], bb["y"]),
            (bb["x"] + bb["w"], bb["y"]),
            (bb["x"], bb["y"] + bb["h"]),
            (bb["x"] + bb["w"], bb["y"] + bb["h"]),
        ])

    # Also add individual pier positions
    for p in all_piers:
        bid = p.get("block_id")
        if bid is None:
            # Inherit from tracker
            for t in trackers:
                if t["tracker_id"] == p.get("tracker_id"):
                    bid = t.get("block_id")
                    break
        if bid is not None:
            by_block.setdefault(bid, {"code": f"B{bid}", "points": []})
            by_block[bid]["points"].append((p["x"], p["y"]))

    blocks = []
    for bid in sorted(by_block):
        info = by_block[bid]
        pts = info["points"]
        if len(pts) < 3:
            continue
        from shapely.geometry import MultiPoint
        hull = MultiPoint(pts).convex_hull.buffer(8).simplify(3.0)
        blocks.append({
            "block_id": bid,
            "block_code": info["code"],
            "label": str(bid),
            "color": "derived",
            "polygon": hull,
            "points": polygon_to_points(hull),
            "bbox": bbox_from_polygon(hull),
            "centroid": {"x": float(hull.centroid.x), "y": float(hull.centroid.y)},
            "original_block_id": str(bid),
            "block_pier_plan_sheet": f"S-{settings['sheet_base'] + bid}",
        })
    return blocks


def _infer_pier_type_from_position(row_index, row_count):
    """Fallback pier type when vector symbol was not matched."""
    if row_index == 1 or row_index == row_count:
        return "SAPEND"
    if row_index == 2 or row_index == row_count - 1:
        return "SAPE"
    mid = (row_count + 1) // 2
    if row_index == mid:
        return "SMP"
    return "SAP"


def classify_trackers_and_piers(trackers, all_piers):
    def _tracker_sheet(code):
        return {
            "112-EXT": "S-401", "112-EDGE-INT-HYBRID": "S-403", "84-EXT": "S-405", "84-EDGE-INT-HYBRID": "S-407",
            "56-EXT": "S-409", "56-EDGE-HYBRID": "S-410", "28-EXT": "S-412", "28-EDGE": "S-413"
        }.get(code, "S-401")
    def _infer_pier_type(row_index, row_len):
        if row_index == 1 or row_index == row_len:
            return "SAPEND"
        if row_index == 2 or row_index == row_len - 1:
            return "SAPE"
        motor_idx = (row_len + 1) // 2
        if row_index == motor_idx:
            return "SMP"
        return "SAP"
    by_tracker = {}
    for p in all_piers:
        by_tracker.setdefault(p["tracker_id"], []).append(p)
    for t in trackers:
        plist = sorted(by_tracker.get(t["tracker_id"], []), key=lambda p: p["row_index"])
        cnt = len(plist)
        t["pier_count"] = cnt
        t["tracker_type_code"] = TRACKER_TYPE_BY_PIER_COUNT.get(cnt, f"UNKNOWN-{cnt}")
        t["tracker_sheet"] = _tracker_sheet(t["tracker_type_code"])
        t["piers"] = plist
        for p in plist:
            p["row_pier_count"] = cnt
            p["row_num"] = t.get("_original_row", "")
            p["tracker_type_code"] = t["tracker_type_code"]
            p["tracker_sheet"] = t["tracker_sheet"]
            p["pier_type"] = _infer_pier_type(p["row_index"], cnt)
            p["structure_code"] = p["pier_type"]
            p["structure_sheet"] = "S-201..S-213"
            p["pier_type_sheet"] = "S-201..S-213"
            p["slope_band"] = "0-6.1%"
            p["slope_sheet"] = "S-601"

def assign_trackers_to_blocks(trackers, blocks):
    for t in trackers:
        rect = t["polygon"]
        best_block = None
        best_ratio = -1.0
        for b in blocks:
            inter = rect.intersection(b["polygon"])
            if inter.is_empty:
                continue
            ratio = inter.area / max(rect.area, 1e-9)
            if ratio > best_ratio:
                best_ratio = ratio
                best_block = b
        method = "rectangle_overlap"
        if best_block is None or best_ratio < 0.05:
            center = rect.centroid
            for b in blocks:
                if b["polygon"].buffer(2).contains(center):
                    best_block = b
                    method = "rectangle_center_fallback"
                    best_ratio = 0.0
                    break
        if best_block is None and blocks:
            # Last resort: assign to nearest block by centroid distance
            center = rect.centroid
            best_block = min(
                blocks,
                key=lambda b: center.distance(b["polygon"].centroid),
            )
            method = "nearest_centroid_fallback"
            best_ratio = 0.0
        t["block_id"] = best_block["block_id"] if best_block else None
        t["block_code"] = best_block["block_code"] if best_block else None
        t["assignment_method"] = method
        t["assignment_confidence"] = "high" if best_ratio >= 0.60 else ("medium" if best_ratio >= 0.45 else "low")

def refine_blocks_from_trackers(blocks, trackers):
    by_block = {}
    for t in trackers:
        if t.get("block_id") is not None:
            by_block.setdefault(int(t["block_id"]), []).append(t["polygon"])
    refined = []
    for b in blocks:
        polys = by_block.get(int(b["block_id"]), [])
        if not polys:
            refined.append(b)
            continue
        union = unary_union(polys)
        poly = max(union.geoms, key=lambda g: g.area) if hasattr(union, "geoms") else union
        mix = poly.buffer(8).intersection(b["polygon"].buffer(12))
        final_poly = mix if not mix.is_empty else poly
        refined.append({
            **b,
            "polygon": final_poly,
            "points": polygon_to_points(final_poly),
            "bbox": bbox_from_polygon(final_poly),
            "centroid": {"x": float(final_poly.centroid.x), "y": float(final_poly.centroid.y)}
        })
    return refined

def assign_piers_to_blocks(trackers, blocks):
    out = []
    for t in trackers:
        inherited, inherited_code = t.get("block_id"), t.get("block_code")
        for p in t.get("piers", []):
            pt = Point(p["x"], p["y"])
            point_match = None
            point_code = None
            for b in blocks:
                if b["polygon"].buffer(2).contains(pt):
                    point_match, point_code = b["block_id"], b["block_code"]
                    break
            if point_match is not None:
                block_id, block_code, method = point_match, point_code, "point_in_polygon"
            else:
                block_id, block_code, method = inherited, inherited_code, "inherit_tracker"
            out.append({**p, "block_id": block_id, "block_code": block_code, "assignment_method": method})
    return out

def add_relative_coordinates(blocks, trackers, piers):
    if not trackers or not piers:
        return None
    ranked = []
    for t in trackers:
        b = t["bbox"]
        ranked.append((b["x"] + b["w"]/2.0, b["y"] + b["h"], t))
    ranked.sort(key=lambda item: (item[0], -item[1]))
    ref_tracker = None
    ref_pier = None
    for _, _, t in ranked:
        row_piers = sorted([p for p in piers if p["tracker_id"] == t["tracker_id"]], key=lambda p: (p.get("row_index", 999999), p["y"], p["x"]))
        ref_pier = next((p for p in row_piers if p.get("row_index") == 1), row_piers[0] if row_piers else None)
        if ref_pier:
            ref_tracker = t
            break
    if not ref_pier:
        return None
    x0, y0 = float(ref_pier["x"]), float(ref_pier["y"])
    by_tracker_p1 = {}
    for t in trackers:
        tp = sorted([p for p in piers if p["tracker_id"] == t["tracker_id"]], key=lambda p: p.get("row_index", 999999))
        if tp:
            by_tracker_p1[t["tracker_id"]] = tp[0]
    for p in piers:
        p["x_local"] = float(p["x"] - x0)
        p["y_local"] = float(p["y"] - y0)
        p1 = by_tracker_p1.get(p["tracker_id"])
        if p1:
            p["x_tracker_local"] = float(p["x"] - p1["x"])
            p["y_tracker_local"] = float(p["y"] - p1["y"])
    for t in trackers:
        b = t["bbox"]
        cx = b["x"] + b["w"]/2.0
        cy = b["y"] + b["h"]/2.0
        t["center_local"] = {"x": float(cx - x0), "y": float(cy - y0)}
        t["bbox_local"] = {"x": float(b["x"] - x0), "y": float(b["y"] - y0), "w": float(b["w"]), "h": float(b["h"])}
    for b in blocks:
        c = b["centroid"]
        b["centroid_local"] = {"x": float(c["x"] - x0), "y": float(c["y"] - y0)}
        b["polygon_local"] = [{"x": float(pt["x"] - x0), "y": float(pt["y"] - y0)} for pt in b["points"]]
        bb = b["bbox"]
        b["bbox_local"] = {"x": float(bb["x"] - x0), "y": float(bb["y"] - y0), "w": float(bb["w"]), "h": float(bb["h"])}
    return {"origin_rule": "P1 of lowest-leftmost valid tracker", "origin_pier_id": ref_pier["pier_id"], "origin_tracker_id": ref_tracker["tracker_id"], "origin_x": x0, "origin_y": y0}

def build_zoom_targets(blocks, trackers, piers):
    tracker_by = {t["tracker_id"]: t for t in trackers}
    block_by = {b["block_id"]: b for b in blocks}
    out = {}
    for p in piers:
        tracker = tracker_by.get(p["tracker_id"])
        block = block_by.get(p["block_id"])
        pb = p.get("bbox") or {"x": p["x"] - 8, "y": p["y"] - 16, "w": 16, "h": 32}
        out[p["pier_id"]] = {
            "map_target": {"object_id": p["pier_id"], "object_type": "pier", "sheet_id": "site-plan", "bbox": {"x": max(0, pb["x"]-50), "y": max(0, pb["y"]-50), "w": pb["w"]+100, "h": pb["h"]+100}, "padding": 30, "preferred_zoom": 3.5, "overlay_ids": [p["pier_id"]]},
            "row_target": {"object_id": tracker["tracker_id"], "object_type": "tracker", "sheet_id": "site-plan", "bbox": tracker["bbox"], "padding": 40, "preferred_zoom": 2.4, "overlay_ids": [tracker["tracker_id"]]} if tracker else None,
            "block_target": {"object_id": block["block_code"], "object_type": "block", "sheet_id": "site-plan", "bbox": block["bbox"], "padding": 60, "preferred_zoom": 1.8, "overlay_ids": [block["block_code"]]} if block else None,
        }
    return out

def build_drawing_bundles(blocks, trackers, piers):
    block_by = {b["block_id"]: b for b in blocks}
    out = {}
    for p in piers:
        block = block_by.get(p["block_id"])
        orig = int(block["original_block_id"]) if block else 1
        out[p["pier_id"]] = {
            "pier_id": p["pier_id"],
            "block_pier_plan": {"sheet_no": f"S-{200 + orig}"},
            "tracker_typical": {"sheet_no": p.get("tracker_sheet", "S-401")},
            "pier_tolerances": {"sheet_no": "S-501"},
            "slope_detail": {"sheet_no": "S-601"},
            "crops": {"block_plan": {"x":100,"y":100,"w":2400,"h":1600}, "tracker_typical": {"x":200,"y":250,"w":2200,"h":700}},
            "highlights": {"tracker_typical": {"row_pier_count": p.get("row_pier_count"), "pier_type": p.get("pier_type")}}
        }
    return out

def _draw_text(img, txt, xy, color=(0,0,255), scale=0.5, thickness=1):
    cv2.putText(img, txt, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, (255,255,255), thickness+2, cv2.LINE_AA)
    cv2.putText(img, txt, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)

def draw_blocks(img, blocks):
    out = img.copy()
    for b in blocks:
        pts = np.array([[int(p["x"]), int(p["y"])] for p in b["points"]], dtype=np.int32)
        cv2.polylines(out, [pts], True, (255,0,0), 2)
        _draw_text(out, b["block_code"], (int(b["centroid"]["x"]), int(b["centroid"]["y"])), (0,0,255), 0.8, 2)
    return out

def draw_trackers(img, trackers):
    out = img.copy()
    for t in trackers:
        b = t["bbox"]
        x,y,w,h = int(b["x"]), int(b["y"]), int(b["w"]), int(b["h"])
        cv2.rectangle(out, (x,y), (x+w,y+h), (0,180,0), 2)
        _draw_text(out, f'{t["tracker_id"]}:{t.get("pier_count",0)}', (x+4, y+18), (0,128,255), 0.45, 1)
        for p in t.get("piers", []):
            cv2.circle(out, (int(p["x"]), int(p["y"])), 4, (0,0,255), -1)
    return out

def draw_assignment(img, blocks, trackers, piers):
    out = draw_blocks(img, blocks)
    for t in trackers:
        b = t["bbox"]
        x,y,w,h = int(b["x"]), int(b["y"]), int(b["w"]), int(b["h"])
        cv2.rectangle(out, (x,y), (x+w,y+h), (0,180,0), 1)
        _draw_text(out, f'{t["tracker_id"]}/B{t.get("block_id")}', (x+4, y+18), (0,180,0), 0.45, 1)
    for p in piers:
        cv2.circle(out, (int(p["x"]), int(p["y"])), 3, (0,0,255), -1)
    return out

def apply_block_mapping(block_mapping_img, base_site, trackers, profile):
    """Process a block mapping image to build execution block polygons.

    The block mapping image shows numbered execution blocks with colored
    boundary lines.  Both images are oriented north-up.  We:
    1. Detect colored boundary lines → segment into regions
    2. Match each region to a block number using known centroid positions
    3. Map region polygons to base_site space using tracker bounding box
    """
    settings = profile["heuristics"]["blocks"]

    # --- Known block-number centroid positions in the reference image ------
    # (pixel coords in block_names.jpeg at 710×598 resolution)
    BLOCK_CENTROIDS = {
        1: (62, 225),   2: (198, 172),   3: (285, 142),   4: (358, 162),
        5: (448, 112),  6: (78, 385),    7: (228, 290),   8: (290, 300),
        9: (380, 260),  10: (420, 248),  11: (555, 198),  12: (152, 518),
        13: (198, 495), 14: (318, 430),  15: (388, 410),  16: (462, 355),
        17: (558, 338), 18: (638, 340),
    }

    # Scale reference centroids to actual image dimensions
    ref_w, ref_h = 710, 598
    img_h, img_w = block_mapping_img.shape[:2]
    scale_cx = img_w / ref_w
    scale_cy = img_h / ref_h
    centroids = {n: (x * scale_cx, y * scale_cy) for n, (x, y) in BLOCK_CENTROIDS.items()}

    # --- 1.  Detect colored boundary lines --------------------------------
    hsv = cv2.cvtColor(block_mapping_img, cv2.COLOR_BGR2HSV)
    h, w = hsv.shape[:2]

    line_ranges = [
        (( 0,  70, 70), ( 10, 255, 255)),   # red low
        ((170, 70, 70), (180, 255, 255)),    # red high
        (( 35, 50, 50), ( 85, 255, 255)),    # green
        (( 20, 70, 70), ( 35, 255, 255)),    # yellow
        (( 85, 50, 50), (130, 255, 255)),    # cyan/blue
        ((140, 40, 70), (170, 255, 255)),    # magenta/pink
    ]

    boundary_mask = np.zeros((h, w), dtype=np.uint8)
    for lo, hi in line_ranges:
        boundary_mask |= cv2.inRange(hsv, np.array(lo), np.array(hi))

    # Thicken boundary lines to form continuous walls
    kern = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    boundary_mask = cv2.dilate(boundary_mask, kern, iterations=4)
    boundary_mask = cv2.morphologyEx(boundary_mask, cv2.MORPH_CLOSE, kern, iterations=3)

    # Seal image edges
    cv2.rectangle(boundary_mask, (0, 0), (w - 1, h - 1), 255, thickness=8)

    # --- 2.  Segment regions (connected components on inverse) ------------
    inv = cv2.bitwise_not(boundary_mask)
    inv = cv2.morphologyEx(inv, cv2.MORPH_OPEN,
                           cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    num_labels, labels_img = cv2.connectedComponents(inv, connectivity=4)

    min_area = h * w * 0.004
    max_area = h * w * 0.2   # skip giant background regions

    region_polys = []  # list of (centroid_x, centroid_y, polygon)
    for lbl in range(1, num_labels):
        region_mask = (labels_img == lbl).astype(np.uint8) * 255
        area = int(cv2.countNonZero(region_mask))
        if area < min_area or area > max_area:
            continue
        contours, _ = cv2.findContours(region_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        cnt = max(contours, key=cv2.contourArea)
        eps = 0.003 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, eps, True)
        pts = approx.reshape(-1, 2)
        if len(pts) < 3:
            continue
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            continue
        region_polys.append((float(poly.centroid.x), float(poly.centroid.y), poly))

    # --- 3.  Match regions to block numbers via Hungarian algorithm ----------
    from scipy.optimize import linear_sum_assignment
    block_nums = sorted(centroids)
    n_blocks = len(block_nums)
    n_regions = len(region_polys)
    if n_regions == 0:
        return [], block_mapping_img

    # Build cost matrix: distance from each block centroid to each region centroid
    cost = np.full((n_blocks, n_regions), 1e9)
    max_dist = max(w, h) * 0.2
    for bi, bnum in enumerate(block_nums):
        bcx, bcy = centroids[bnum]
        for ri, (rcx, rcy, _) in enumerate(region_polys):
            d = ((bcx - rcx) ** 2 + (bcy - rcy) ** 2) ** 0.5
            if d < max_dist:
                cost[bi, ri] = d

    row_ind, col_ind = linear_sum_assignment(cost)
    assigned = {}
    for bi, ri in zip(row_ind, col_ind):
        if cost[bi, ri] < max_dist:
            assigned[block_nums[bi]] = region_polys[ri][2]

    if not assigned:
        return [], block_mapping_img

    # --- 4.  Compute affine transform: image space → base_site space ------
    # Use design block label positions as anchor points.  The block mapping
    # image contains "BLOCK X" labels from the design blocks — their
    # positions in the image are known, and the design block centroids in
    # base_site space come from the tracker positions.
    if not trackers:
        return [], block_mapping_img

    # Design block label positions in the reference image (710×598)
    DESIGN_LABEL_POS = {
        "B5":  (270, 185), "B6":  (115, 235), "B7":  (295, 310),
        "B8":  (510, 295), "B9":  (475, 400), "B10": (165, 315),
        "B11": (235, 395), "B12": (225, 470), "B13": (115, 485),
    }

    # Scale to actual image size
    design_img_pts = {k: (x * scale_cx, y * scale_cy)
                      for k, (x, y) in DESIGN_LABEL_POS.items()}

    # Compute design block centroids in base_site space from tracker positions
    design_block_centers = {}
    for t in trackers:
        bc = t.get("block_code", "")
        if not bc:
            continue
        bb = t["bbox"]
        design_block_centers.setdefault(bc, []).append(
            (bb["x"] + bb["w"] / 2, bb["y"] + bb["h"] / 2))
    for bc in design_block_centers:
        pts = design_block_centers[bc]
        design_block_centers[bc] = (
            sum(p[0] for p in pts) / len(pts),
            sum(p[1] for p in pts) / len(pts),
        )

    # Build corresponding point pairs: image space → base_site space
    src_pts = []
    dst_pts = []
    for dbc, img_pos in design_img_pts.items():
        if dbc in design_block_centers:
            src_pts.append(img_pos)
            dst_pts.append(design_block_centers[dbc])

    from shapely.affinity import affine_transform as sat

    if len(src_pts) >= 3:
        # Compute full affine transform using least-squares
        src_arr = np.float32(src_pts)
        dst_arr = np.float32(dst_pts)
        # Use OpenCV estimateAffine2D for robust fitting (handles outliers)
        M, _inliers = cv2.estimateAffine2D(
            src_arr.reshape(-1, 1, 2), dst_arr.reshape(-1, 1, 2),
            method=cv2.RANSAC, ransacReprojThreshold=50.0,
        )
        if M is not None:
            # M is 2x3: [[a, b, tx], [c, d, ty]]
            a, b, tx = M[0]
            c, d, ty = M[1]
            def transform_poly(poly):
                return sat(poly, [a, b, c, d, tx, ty])
        else:
            # Fallback: simple scale + translate from bounding boxes
            all_x = [bb["x"] for t in trackers for bb in [t["bbox"]]]
            all_y = [bb["y"] for t in trackers for bb in [t["bbox"]]]
            field = (min(all_x), min(all_y), max(all_x), max(all_y))
            region_xs = [p.centroid.x for p in assigned.values()]
            region_ys = [p.centroid.y for p in assigned.values()]
            rbounds = (min(region_xs), min(region_ys), max(region_xs), max(region_ys))
            sx = (field[2]-field[0]) / max(rbounds[2]-rbounds[0], 1)
            sy = (field[3]-field[1]) / max(rbounds[3]-rbounds[1], 1)
            ox = field[0] - rbounds[0]*sx
            oy = field[1] - rbounds[1]*sy
            def transform_poly(poly):
                return sat(poly, [sx, 0, 0, sy, ox, oy])
    else:
        return [], block_mapping_img

    # --- 5.  Assign trackers using transformed polygons (point-in-polygon),
    #         then build display polygons from tracker positions. -----------
    from shapely.geometry import MultiPoint

    # Transform boundary polygons to base_site space for assignment
    mapped_polys = {}  # bnum -> transformed Shapely polygon
    for bnum, poly in assigned.items():
        mp = transform_poly(poly)
        mp = mp.buffer(10)  # small buffer for edge trackers
        if not mp.is_empty:
            mapped_polys[bnum] = mp

    # Also prepare centroid fallback for trackers that don't fall in any polygon
    centroid_map = {}
    for bnum, poly in mapped_polys.items():
        centroid_map[bnum] = (float(poly.centroid.x), float(poly.centroid.y))

    # Assign: first try point-in-polygon, then fall back to nearest centroid
    for t in trackers:
        bb = t["bbox"]
        tcx = bb["x"] + bb["w"] / 2
        tcy = bb["y"] + bb["h"] / 2
        pt = Point(tcx, tcy)

        # Try point-in-polygon first
        best_num = None
        for bnum, poly in mapped_polys.items():
            if poly.contains(pt):
                best_num = bnum
                break

        # Fallback: nearest centroid
        if best_num is None:
            best_dist = float("inf")
            for bnum, (cx, cy) in centroid_map.items():
                d = ((tcx - cx) ** 2 + (tcy - cy) ** 2) ** 0.5
                if d < best_dist:
                    best_dist = d
                    best_num = bnum

        if best_num is not None:
            t["block_id"] = best_num
            t["block_code"] = f"B{best_num}"
            t["assignment_method"] = "block_mapping"
            t["assignment_confidence"] = "high"

    # Build display polygons from assigned tracker bounding boxes
    by_block = {}
    for t in trackers:
        bid = t.get("block_id")
        if bid is None:
            continue
        bb = t["bbox"]
        by_block.setdefault(bid, []).extend([
            (bb["x"], bb["y"]), (bb["x"] + bb["w"], bb["y"]),
            (bb["x"], bb["y"] + bb["h"]), (bb["x"] + bb["w"], bb["y"] + bb["h"]),
        ])

    blocks = []
    for bnum in sorted(by_block):
        pts = by_block[bnum]
        if len(pts) < 3:
            continue
        hull = MultiPoint(pts).convex_hull.buffer(8).simplify(3.0)
        blocks.append({
            "block_id": bnum,
            "block_code": f"B{bnum}",
            "label": str(bnum),
            "color": "mapped",
            "polygon": hull,
            "points": polygon_to_points(hull),
            "bbox": bbox_from_polygon(hull),
            "centroid": {"x": float(hull.centroid.x), "y": float(hull.centroid.y)},
            "original_block_id": str(bnum),
            "block_pier_plan_sheet": f"S-{settings['sheet_base'] + min(bnum, settings.get('sheet_cap', 18))}",
        })

    # Debug image: draw mapped block polygons on base_site
    debug = base_site.copy()
    colors = [(0,0,255),(0,200,0),(255,0,0),(255,255,0),(0,255,255),(255,0,255),
              (128,0,255),(0,128,255),(255,128,0),(128,255,0),(0,255,128),(255,0,128),
              (100,100,255),(100,255,100),(255,100,100),(200,200,0),(0,200,200),(200,0,200)]
    for i, b in enumerate(blocks):
        pts_arr = np.array([(int(p["x"]), int(p["y"])) for p in b["points"]], dtype=np.int32)
        color = colors[i % len(colors)]
        cv2.polylines(debug, [pts_arr], True, color, 2)
        cx, cy = int(b["centroid"]["x"]), int(b["centroid"]["y"])
        cv2.circle(debug, (cx, cy), 10, color, -1)
        _draw_text(debug, str(b["block_id"]), (cx - 8, cy + 5), (255, 255, 255), 0.6, 2)
    return blocks, debug


def run_pipeline(construction_pdf, ramming_pdf, overlay_source, out_dir, profile, block_mapping_source=None):
    out = ensure_dir(out_dir)
    site_page_idx, base_site = pick_site_page(construction_pdf, profile)
    ramming_page_idx, ramming_img_raw = pick_ramming_page(ramming_pdf, profile)
    overlay_meta, overlay = load_overlay_source(overlay_source, profile)
    try:
        aligned_overlay, H = align_overlay_to_base(base_site, overlay)
    except Exception:
        aligned_overlay, H = resize_to_base(base_site, overlay)
    if not alignment_is_usable(base_site, aligned_overlay, H):
        aligned_overlay, H = resize_to_base(base_site, overlay)
    try:
        aligned_ramming, ramming_H = align_ramming_to_base(base_site, ramming_img_raw)
    except Exception:
        aligned_ramming, ramming_H = resize_to_base(base_site, ramming_img_raw)
    if not alignment_is_usable(base_site, aligned_ramming, ramming_H):
        aligned_ramming, ramming_H = resize_to_base(base_site, ramming_img_raw)
    row_model = None
    blocks, cleaned_overlay = build_initial_blocks(aligned_overlay, profile)
    block_labels = []
    if overlay_meta["kind"] == "pdf" and overlay_meta.get("page_index") is not None:
        block_labels = extract_block_labels_from_pdf(overlay_source, overlay_meta["page_index"], overlay.shape, H)

    # --- Prefer vector-based PDF extraction; fall back to CV -----------------
    vector_ok = False
    vector_page_dims = None
    trackers, all_piers = [], []
    try:
        trackers, all_piers, vector_page_dims = extract_trackers_from_pdf_vector(
            ramming_pdf, ramming_page_idx, base_site.shape, profile,
            base_block_labels=block_labels,
        )
        if trackers:
            vector_ok = True
    except Exception:
        pass

    if not vector_ok:
        trackers = extract_trackers(ramming_img_raw, profile)
        if trackers:
            for t in trackers:
                all_piers.extend(detect_piers_in_tracker(ramming_img_raw, t, profile))
        else:
            trackers, row_model = extract_trackers_from_rows(ramming_img_raw)
            all_piers = detect_piers_by_rows(ramming_img_raw, trackers, row_model)
        classify_trackers_and_piers(trackers, all_piers)
        scale_detected_layout(trackers, all_piers, ramming_img_raw.shape, base_site.shape)

    if vector_ok:
        # Build blocks from vector pier positions (same coordinate space)
        blocks = build_blocks_from_vector_piers(trackers, all_piers, profile)
        piers = assign_piers_to_blocks(trackers, blocks)
    else:
        if len(blocks) < max(3, len(block_labels) // 2) and block_labels:
            blocks = build_blocks_from_labels(block_labels, trackers, profile)
            cleaned_overlay = aligned_overlay.copy()
        assign_trackers_to_blocks(trackers, blocks)
        blocks = refine_blocks_from_trackers(blocks, trackers)
        assign_trackers_to_blocks(trackers, blocks)
        piers = assign_piers_to_blocks(trackers, blocks)

    # --- Override blocks with execution blocks from block mapping image ----
    if block_mapping_source:
        bm_img = cv2.imread(block_mapping_source, cv2.IMREAD_COLOR)
        if bm_img is not None:
            exec_blocks, bm_debug = apply_block_mapping(bm_img, base_site, trackers, profile)
            if exec_blocks:
                blocks = exec_blocks
                # Trackers already assigned inside apply_block_mapping;
                # just reassign piers from the updated trackers.
                piers = assign_piers_to_blocks(trackers, blocks)
                save_image(out / "block_mapping_input.png", bm_debug)
                save_image(out / "debug_exec_blocks.png", draw_blocks(base_site, blocks))
                save_image(out / "exec_assignment.png", draw_assignment(base_site, blocks, trackers, piers))

    coord = add_relative_coordinates(blocks, trackers, piers)
    zoom_targets = build_zoom_targets(blocks, trackers, piers)
    drawing_bundles = build_drawing_bundles(blocks, trackers, piers)
    save_image(out / "base_site.png", base_site)
    save_image(out / "ramming_page_001.png", aligned_ramming)
    save_image(out / "aligned_overlay.png", aligned_overlay)
    save_image(out / "cleaned_overlay.png", cleaned_overlay)
    save_image(out / "debug_blocks.png", draw_blocks(base_site, blocks))
    save_image(out / "debug_trackers.png", draw_trackers(aligned_ramming, trackers))
    save_image(out / "final_assignment.png", draw_assignment(base_site, blocks, trackers, piers))
    blocks_json = [{
        "block_id": b["block_id"], "block_code": b["block_code"], "label": b["label"], "color": b["color"],
        "original_block_id": b["original_block_id"], "block_pier_plan_sheet": b["block_pier_plan_sheet"],
        "bbox": b["bbox"], "bbox_local": b.get("bbox_local"), "centroid": b["centroid"], "centroid_local": b.get("centroid_local"),
        "polygon": b["points"], "polygon_local": b.get("polygon_local")
    } for b in blocks]
    trackers_json = [{
        "tracker_id": t["tracker_id"], "tracker_code": t["tracker_code"], "block_id": t.get("block_id"), "block_code": t.get("block_code"),
        "row": t.get("_original_row", ""), "trk": t.get("_original_trk", ""),
        "tracker_type_code": t.get("tracker_type_code"), "tracker_sheet": t.get("tracker_sheet"), "orientation": t["orientation"],
        "pier_count": t.get("pier_count"), "bbox": t["bbox"], "bbox_local": t.get("bbox_local"), "center_local": t.get("center_local"),
        "assignment_method": t.get("assignment_method"), "assignment_confidence": t.get("assignment_confidence"),
        "piers": [p["pier_id"] for p in t.get("piers", [])]
    } for t in trackers]
    summary = {
        "artifacts_version": "1.0.0",
        "site_profile": profile["name"],
        "detected_site_profile": profile.get("detected_name"),
        "construction_page_index_used": site_page_idx,
        "ramming_page_index_used": ramming_page_idx,
        "overlay_source": overlay_meta,
        "base_image": vector_page_dims if vector_ok and vector_page_dims else {
            "width": int(base_site.shape[1]),
            "height": int(base_site.shape[0]),
        },
        "overlay_homography": H.tolist(),
        "ramming_homography": ramming_H.tolist(),
        "extraction_method": "vector_pdf" if vector_ok else "cv",
        "block_label_count": len(block_labels),
        "block_count": len(blocks_json),
        "tracker_count": len(trackers_json),
        "pier_count": len(piers),
        "coordinate_system": coord,
    }

    # Read-only electrical metadata extraction. Wrapped in try/except so any
    # failure here cannot affect the main pier/tracker extraction artifacts.
    try:
        from app.electrical_metadata import extract_electrical_metadata
        elec = extract_electrical_metadata(construction_pdf, ramming_pdf)
        if elec.get("_extracted"):
            summary["electrical"] = {
                k: v for k, v in elec.items() if not k.startswith("_")
            }
    except Exception:
        pass

    # Strip internal-only row_index from piers before persisting — it's redundant
    # with pier_code (which already encodes the position as -P01, -P02, ...)
    for _p in piers:
        _p.pop("row_index", None)

    save_json(out / "blocks.json", blocks_json)
    save_json(out / "trackers.json", trackers_json)
    save_json(out / "piers.json", piers)
    save_json(out / "zoom_targets.json", zoom_targets)
    save_json(out / "drawing_bundles.json", drawing_bundles)
    save_json(out / "summary.json", summary)
    return {"blocks": blocks_json, "trackers": trackers_json, "piers": piers, "zoom_targets": zoom_targets, "drawing_bundles": drawing_bundles, "summary": summary}
