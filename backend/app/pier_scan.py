from __future__ import annotations

import csv
import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

import cv2
import fitz
import numpy as np
from sklearn.cluster import DBSCAN


RED_RANGES = [((0, 80, 80), (12, 255, 255)), ((170, 80, 80), (179, 255, 255))]
SITE_RANGES = [
    ((70, 20, 80), (115, 255, 255)),
    ((35, 20, 60), (95, 255, 255)),
    ((115, 20, 60), (170, 255, 255)),
    ((15, 40, 80), (40, 255, 255)),
]
ALLOWED_SET_SIZES = (19, 17, 15, 13, 11, 9, 6, 5)


def render_pdf_tiles(pdf_path, page_index=0, zoom=2.8, tile_width=900, tile_height=900, overlap=120):
    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(page_index)
        rect = page.rect
        step_x = max(tile_width - overlap, 1)
        step_y = max(tile_height - overlap, 1)
        y = 0
        while y < rect.height:
            x = 0
            while x < rect.width:
                clip = fitz.Rect(x, y, min(rect.width, x + tile_width), min(rect.height, y + tile_height))
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False, clip=clip)
                arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
                offset = (int(round(clip.x0 * zoom)), int(round(clip.y0 * zoom)))
                yield cv2.cvtColor(arr, cv2.COLOR_RGB2BGR), offset
                x += step_x
            y += step_y
    finally:
        doc.close()


def get_page_pixel_size(pdf_path, page_index=0, zoom=2.8):
    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(page_index)
        rect = page.rect
        return int(round(rect.width * zoom)), int(round(rect.height * zoom))
    finally:
        doc.close()


def extract_site_mask(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lo, hi in SITE_RANGES:
        mask |= cv2.inRange(hsv, np.array(lo), np.array(hi))
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (61, 61)),
        iterations=2,
    )
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return mask
    out = np.zeros(mask.shape, dtype=np.uint8)
    cv2.drawContours(out, [max(contours, key=cv2.contourArea)], -1, 255, thickness=-1)
    return out


def _classify_red_symbol(contour):
    area = cv2.contourArea(contour)
    if area < 6 or area > 250:
        return None
    x, y, w, h = cv2.boundingRect(contour)
    if w > 30 or h > 30:
        return None
    peri = cv2.arcLength(contour, True)
    circularity = (4 * np.pi * area / (peri * peri)) if peri else 0.0
    rect_ratio = area / max(float(w * h), 1.0)
    if circularity > 0.84 and rect_ratio > 0.62:
        shape = "circle"
    elif rect_ratio < 0.60 or circularity < 0.80:
        shape = "diamond"
    else:
        shape = "other"
    return {
        "x": float(x + w / 2.0),
        "y": float(y + h / 2.0),
        "w": int(w),
        "h": int(h),
        "area": float(area),
        "shape": shape,
    }


def detect_red_symbols(img, site_mask, offset=(0, 0)):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    red = np.zeros(site_mask.shape, dtype=np.uint8)
    for lo, hi in RED_RANGES:
        red |= cv2.inRange(hsv, np.array(lo), np.array(hi))
    red &= site_mask
    red = cv2.morphologyEx(
        red,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    )
    contours, _ = cv2.findContours(red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    symbols = []
    ox, oy = offset
    for contour in contours:
        item = _classify_red_symbol(contour)
        if not item:
            continue
        item["x"] += ox
        item["y"] += oy
        symbols.append(item)
    return symbols


def dedupe_symbols(symbols, eps=8):
    if not symbols:
        return []
    pts = np.array([[item["x"], item["y"]] for item in symbols], dtype=np.float32)
    labels = DBSCAN(eps=eps, min_samples=1).fit_predict(pts)
    deduped = []
    for label in sorted(set(labels)):
        group = [symbols[idx] for idx, lab in enumerate(labels) if lab == label]
        shapes = Counter(item["shape"] for item in group)
        deduped.append({
            "x": float(np.mean([item["x"] for item in group])),
            "y": float(np.mean([item["y"] for item in group])),
            "shape": shapes.most_common(1)[0][0],
            "hits": len(group),
        })
    return deduped


def group_ns_sets(symbols, x_eps=12, y_gap=50):
    if not symbols:
        return []
    pts = np.array([[item["x"], item["y"]] for item in symbols], dtype=np.float32)
    x_labels = DBSCAN(eps=x_eps, min_samples=1).fit_predict(pts[:, 0:1])
    sizes = []
    for label in sorted(set(x_labels)):
        group = pts[x_labels == label]
        ys = np.sort(group[:, 1])
        start = 0
        for idx in range(1, len(ys)):
            if ys[idx] - ys[idx - 1] > y_gap:
                sizes.append(int(idx - start))
                start = idx
        sizes.append(int(len(ys) - start))
    return sizes


def split_ns_symbol_sets(symbols, x_eps=12, y_gap=50):
    if not symbols:
        return [], []
    ordered = sorted(symbols, key=lambda item: (item["x"], item["y"]))
    pts = np.array([[item["x"], item["y"]] for item in ordered], dtype=np.float32)
    x_labels = DBSCAN(eps=x_eps, min_samples=1).fit_predict(pts[:, 0:1])
    complete_sets = []
    leftovers = []

    for label in sorted(set(x_labels), key=lambda lab: float(np.mean(pts[x_labels == lab, 0]))):
        group = [ordered[idx] for idx, lab in enumerate(x_labels) if lab == label]
        group.sort(key=lambda item: item["y"])

        segments = []
        start = 0
        for idx in range(1, len(group)):
            if group[idx]["y"] - group[idx - 1]["y"] > y_gap:
                segments.append(group[start:idx])
                start = idx
        segments.append(group[start:])

        for segment in segments:
            _, parts = _best_set_decomposition(len(segment))
            if not parts:
                leftovers.append(segment)
                continue

            cursor = 0
            for size in parts:
                subset = segment[cursor:cursor + size]
                if len(subset) != size:
                    leftovers.append(subset)
                else:
                    complete_sets.append(subset)
                cursor += size
            if cursor < len(segment):
                leftovers.append(segment[cursor:])

    return complete_sets, leftovers


@lru_cache(None)
def _best_set_decomposition(count):
    if count == 0:
        return 0, ()
    best_score = count * 100
    best_parts = ()
    for size in ALLOWED_SET_SIZES:
        if size > count:
            continue
        score, parts = _best_set_decomposition(count - size)
        candidate_score = score + 1
        candidate_parts = parts + (size,)
        if candidate_score < best_score:
            best_score = candidate_score
            best_parts = candidate_parts
    return best_score, best_parts


def decompose_set_sizes(group_sizes):
    parts = []
    leftovers = []
    for count in group_sizes:
        _, group_parts = _best_set_decomposition(int(count))
        if group_parts:
            parts.extend(group_parts)
            leftover = int(count) - sum(group_parts)
            if leftover:
                leftovers.append(leftover)
        else:
            leftovers.append(int(count))
    return parts, leftovers


def estimate_pier_type_counts(symbols, set_sizes):
    shapes = Counter(item["shape"] for item in symbols)
    sapend = 2 * len(set_sizes)
    sape = 2 * len(set_sizes)
    smp = len(set_sizes)
    sap = sum(max(size - 5, 0) for size in set_sizes)
    return {
        "SAP": sap,
        "SAPE": sape,
        "SAPEND": sapend,
        "SMP": smp,
        "red_circle_symbols": shapes["circle"],
        "red_diamond_symbols": shapes["diamond"],
    }


def estimate_set_type_counts(set_size):
    return {
        "SAP": max(int(set_size) - 5, 0),
        "SAPE": 2,
        "SAPEND": 2,
        "SMP": 1,
    }


def scan_pier_symbols(pdf_path, page_index=0, zoom=2.8):
    raw_symbols = []
    for tile, offset in render_pdf_tiles(pdf_path, page_index=page_index, zoom=zoom):
        site_mask = extract_site_mask(tile)
        raw_symbols.extend(detect_red_symbols(tile, site_mask, offset=offset))
    symbols = dedupe_symbols(raw_symbols)
    page_width, page_height = get_page_pixel_size(pdf_path, page_index=page_index, zoom=zoom)
    return {
        "page_width": page_width,
        "page_height": page_height,
        "symbols": symbols,
    }


def deep_scan_pier_types(pdf_path, page_index=0, zoom=2.8):
    scan = scan_pier_symbols(pdf_path, page_index=page_index, zoom=zoom)
    symbols = scan["symbols"]
    complete_sets, leftover_groups = split_ns_symbol_sets(symbols)
    set_sizes = [len(group) for group in complete_sets]
    leftovers = [len(group) for group in leftover_groups]
    return {
        "page_width": scan["page_width"],
        "page_height": scan["page_height"],
        "total_symbols": len(symbols),
        "shape_counts": dict(Counter(item["shape"] for item in symbols)),
        "raw_group_sizes": dict(sorted(Counter(group_ns_sets(symbols)).items())),
        "set_sizes": dict(sorted(Counter(set_sizes).items())),
        "leftovers": dict(sorted(Counter(leftovers).items())),
        "resolved_symbol_count": int(sum(set_sizes)),
        "unresolved_symbol_count": int(sum(leftovers)),
        "complete_set_count": len(set_sizes),
        "pier_type_counts": estimate_pier_type_counts(symbols, set_sizes),
    }


def build_ns_set_rows(symbols):
    complete_sets, leftover_groups = split_ns_symbol_sets(symbols)
    rows = []
    for idx, group in enumerate(sorted(complete_sets, key=lambda items: (min(item["x"] for item in items), min(item["y"] for item in items))), start=1):
        xs = [item["x"] for item in group]
        ys = [item["y"] for item in group]
        counts = estimate_set_type_counts(len(group))
        rows.append({
            "set_id": f"S{idx:03d}",
            "set_size": len(group),
            "symbol_count": len(group),
            "x_center": float(np.mean(xs)),
            "y_center": float(np.mean(ys)),
            "x_min": float(min(xs)),
            "x_max": float(max(xs)),
            "y_min": float(min(ys)),
            "y_max": float(max(ys)),
            "width": float(max(xs) - min(xs)),
            "height": float(max(ys) - min(ys)),
            "estimated_type_counts": counts,
        })
    return rows, leftover_groups


def export_pier_symbol_csv(out_path, page_width, page_height, symbols):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["symbol_id", "shape", "x", "y", "x_rel", "y_rel", "hits"])
        for idx, item in enumerate(sorted(symbols, key=lambda row: (row["y"], row["x"])), start=1):
            writer.writerow([
                f"P{idx:04d}",
                item["shape"],
                round(item["x"], 3),
                round(item["y"], 3),
                round(item["x"] / max(page_width, 1), 6),
                round(item["y"] / max(page_height, 1), 6),
                item.get("hits", 1),
            ])
    return out_path


def export_pier_symbol_svg(out_path, page_width, page_height, symbols, title="Pier Relative Map"):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    canvas_width = 1400
    canvas_height = 900
    margin = 40
    scale = min(
        (canvas_width - 2 * margin) / max(page_width, 1),
        (canvas_height - 2 * margin) / max(page_height, 1),
    )
    plot_width = page_width * scale
    plot_height = page_height * scale
    offset_x = (canvas_width - plot_width) / 2.0
    offset_y = (canvas_height - plot_height) / 2.0

    lines = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{canvas_width}' height='{canvas_height}' viewBox='0 0 {canvas_width} {canvas_height}'>",
        "  <rect width='100%' height='100%' fill='#f8f3e9' />",
        f"  <text x='{margin}' y='28' font-family='Segoe UI, Arial, sans-serif' font-size='20' fill='#1d2a33'>{title}</text>",
        f"  <text x='{margin}' y='50' font-family='Segoe UI, Arial, sans-serif' font-size='12' fill='#4a5a68'>Relative positions only. Red circles and blue diamonds are deep-scan symbol detections.</text>",
        f"  <rect x='{offset_x:.2f}' y='{offset_y:.2f}' width='{plot_width:.2f}' height='{plot_height:.2f}' fill='#fffdf8' stroke='#c8bba8' stroke-width='1.5' />",
    ]

    for item in symbols:
        px = offset_x + item["x"] * scale
        py = offset_y + item["y"] * scale
        if item["shape"] == "diamond":
            size = 3.4
            points = [
                f"{px:.2f},{py - size:.2f}",
                f"{px + size:.2f},{py:.2f}",
                f"{px:.2f},{py + size:.2f}",
                f"{px - size:.2f},{py:.2f}",
            ]
            lines.append(
                f"  <polygon points='{' '.join(points)}' fill='#1f6fb2' fill-opacity='0.82' stroke='#0b3d62' stroke-width='0.35' />"
            )
        else:
            radius = 2.6 if item["shape"] == "circle" else 2.2
            fill = "#cf2e2e" if item["shape"] == "circle" else "#7c6f64"
            lines.append(
                f"  <circle cx='{px:.2f}' cy='{py:.2f}' r='{radius}' fill='{fill}' fill-opacity='0.78' stroke='none' />"
            )

    legend_x = canvas_width - 255
    legend_y = 34
    lines.extend([
        f"  <rect x='{legend_x}' y='{legend_y}' width='205' height='76' rx='8' fill='#fffdf8' stroke='#c8bba8' stroke-width='1' />",
        f"  <circle cx='{legend_x + 18}' cy='{legend_y + 24}' r='4' fill='#cf2e2e' />",
        f"  <text x='{legend_x + 32}' y='{legend_y + 28}' font-family='Segoe UI, Arial, sans-serif' font-size='12' fill='#1d2a33'>Circle symbol</text>",
        f"  <polygon points='{legend_x + 18},{legend_y + 45} {legend_x + 22},{legend_y + 49} {legend_x + 18},{legend_y + 53} {legend_x + 14},{legend_y + 49}' fill='#1f6fb2' />",
        f"  <text x='{legend_x + 32}' y='{legend_y + 53}' font-family='Segoe UI, Arial, sans-serif' font-size='12' fill='#1d2a33'>Diamond symbol</text>",
        f"  <text x='{legend_x + 14}' y='{legend_y + 70}' font-family='Segoe UI, Arial, sans-serif' font-size='11' fill='#4a5a68'>{len(symbols)} total detected symbols</text>",
        "</svg>",
    ])

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def export_pier_group_csv(out_path, page_width, page_height, groups):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "set_id",
            "set_size",
            "x_center",
            "y_center",
            "x_rel",
            "y_rel",
            "x_min",
            "x_max",
            "y_min",
            "y_max",
            "sap",
            "sape",
            "sapend",
            "smp",
        ])
        for row in groups:
            counts = row["estimated_type_counts"]
            writer.writerow([
                row["set_id"],
                row["set_size"],
                round(row["x_center"], 3),
                round(row["y_center"], 3),
                round(row["x_center"] / max(page_width, 1), 6),
                round(row["y_center"] / max(page_height, 1), 6),
                round(row["x_min"], 3),
                round(row["x_max"], 3),
                round(row["y_min"], 3),
                round(row["y_max"], 3),
                counts["SAP"],
                counts["SAPE"],
                counts["SAPEND"],
                counts["SMP"],
            ])
    return out_path


def export_pier_group_svg(out_path, page_width, page_height, groups, leftover_groups=None, title="Pier Type Group Map"):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    leftover_groups = leftover_groups or []

    canvas_width = 1600
    canvas_height = 1000
    margin = 44
    scale = min(
        (canvas_width - 2 * margin) / max(page_width, 1),
        (canvas_height - 2 * margin) / max(page_height, 1),
    )
    plot_width = page_width * scale
    plot_height = page_height * scale
    offset_x = (canvas_width - plot_width) / 2.0
    offset_y = (canvas_height - plot_height) / 2.0

    def sx(value):
        return offset_x + value * scale

    def sy(value):
        return offset_y + value * scale

    lines = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{canvas_width}' height='{canvas_height}' viewBox='0 0 {canvas_width} {canvas_height}'>",
        "  <rect width='100%' height='100%' fill='#f7f1e3' />",
        f"  <text x='{margin}' y='30' font-family='Segoe UI, Arial, sans-serif' font-size='22' fill='#1d2a33'>{title}</text>",
        f"  <text x='{margin}' y='52' font-family='Segoe UI, Arial, sans-serif' font-size='12' fill='#4a5a68'>North-south grouped sets with estimated pier-type mix per set.</text>",
        f"  <rect x='{offset_x:.2f}' y='{offset_y:.2f}' width='{plot_width:.2f}' height='{plot_height:.2f}' fill='#fffdf8' stroke='#c8bba8' stroke-width='1.5' />",
    ]

    label_rows = []
    for row in groups:
        x0 = sx(row["x_min"] - 14)
        x1 = sx(row["x_max"] + 14)
        y0 = sy(row["y_min"] - 18)
        y1 = sy(row["y_max"] + 18)
        width = max(x1 - x0, 10)
        height = max(y1 - y0, 16)
        size = row["set_size"]
        opacity = "0.26" if size >= 15 else "0.22"
        stroke = "#9a6b2f" if size >= 15 else "#4e7a5d"
        fill = "#f3c677" if size >= 15 else "#9fd3b0"
        lines.append(
            f"  <rect x='{x0:.2f}' y='{y0:.2f}' width='{width:.2f}' height='{height:.2f}' rx='5' fill='{fill}' fill-opacity='{opacity}' stroke='{stroke}' stroke-width='1.1' />"
        )

        cx = sx(row["x_center"])
        top_label_y = max(y0 - 6, 74)
        label_rows.append((top_label_y, cx, row))

    for leftover in leftover_groups:
        xs = [item["x"] for item in leftover]
        ys = [item["y"] for item in leftover]
        x0 = sx(min(xs) - 10)
        x1 = sx(max(xs) + 10)
        y0 = sy(min(ys) - 10)
        y1 = sy(max(ys) + 10)
        lines.append(
            f"  <rect x='{x0:.2f}' y='{y0:.2f}' width='{max(x1 - x0, 8):.2f}' height='{max(y1 - y0, 8):.2f}' rx='4' fill='#d7d3cf' fill-opacity='0.15' stroke='#877f76' stroke-dasharray='4 3' stroke-width='0.9' />"
        )

    label_rows.sort(key=lambda item: (item[0], item[1]))
    placed = []
    for proposed_y, cx, row in label_rows:
        label_y = proposed_y
        for prev_y, prev_x in placed:
            if abs(label_y - prev_y) < 16 and abs(cx - prev_x) < 92:
                label_y = prev_y + 16
        placed.append((label_y, cx))
        counts = row["estimated_type_counts"]
        text = f"{row['set_id']}  {row['set_size']}p  SAP {counts['SAP']}  SAPE 2  SAPEND 2  SMP 1"
        lines.append(
            f"  <text x='{cx:.2f}' y='{label_y:.2f}' text-anchor='middle' font-family='Segoe UI, Arial, sans-serif' font-size='10' fill='#1d2a33'>{text}</text>"
        )

    legend_x = canvas_width - 318
    legend_y = 32
    unresolved = sum(len(group) for group in leftover_groups)
    lines.extend([
        f"  <rect x='{legend_x}' y='{legend_y}' width='258' height='100' rx='8' fill='#fffdf8' stroke='#c8bba8' stroke-width='1' />",
        f"  <rect x='{legend_x + 14}' y='{legend_y + 16}' width='20' height='12' rx='3' fill='#f3c677' fill-opacity='0.35' stroke='#9a6b2f' />",
        f"  <text x='{legend_x + 44}' y='{legend_y + 26}' font-family='Segoe UI, Arial, sans-serif' font-size='12' fill='#1d2a33'>Larger north-south set</text>",
        f"  <rect x='{legend_x + 14}' y='{legend_y + 40}' width='20' height='12' rx='3' fill='#9fd3b0' fill-opacity='0.3' stroke='#4e7a5d' />",
        f"  <text x='{legend_x + 44}' y='{legend_y + 50}' font-family='Segoe UI, Arial, sans-serif' font-size='12' fill='#1d2a33'>Smaller north-south set</text>",
        f"  <rect x='{legend_x + 14}' y='{legend_y + 64}' width='20' height='12' rx='3' fill='#d7d3cf' fill-opacity='0.15' stroke='#877f76' stroke-dasharray='4 3' />",
        f"  <text x='{legend_x + 44}' y='{legend_y + 74}' font-family='Segoe UI, Arial, sans-serif' font-size='12' fill='#1d2a33'>Unresolved partial group</text>",
        f"  <text x='{legend_x + 14}' y='{legend_y + 92}' font-family='Segoe UI, Arial, sans-serif' font-size='11' fill='#4a5a68'>{len(groups)} complete sets, {unresolved} unresolved symbols</text>",
        "</svg>",
    ])

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


PIER_LABEL_RE = re.compile(r"^P\d+$", re.IGNORECASE)


def _classify_vector_symbol(drawing):
    rect = fitz.Rect(drawing["rect"])
    width = float(rect.width)
    height = float(rect.height)
    if width < 1.5 or height < 1.5 or width > 12 or height > 12:
        return None

    color = tuple(float(value) for value in (drawing.get("color") or ()))
    if not color:
        return None

    item_types = tuple(item[0] for item in drawing.get("items", []))
    if not item_types:
        return None

    red, green, blue = color
    if all(item == "c" for item in item_types):
        if red > 0.8 and green < 0.2 and blue < 0.2:
            return "HAP"
        if green > 0.8 and blue > 0.8 and red < 0.2:
            return "SAP"

    if all(item == "l" for item in item_types):
        if red > 0.8 and green < 0.2 and blue < 0.2:
            return "HMP"
        if red > 0.75 and 0.25 < green < 0.6 and blue < 0.2:
            return "SAPEND"
        if blue > 0.7 and red < 0.4 and green < 0.2:
            return "SAPE"
        if green > 0.8 and blue > 0.8 and red < 0.2:
            return "SMP"

    return None


def _grid_key(value, cell_size):
    return int(np.floor(float(value) / float(cell_size)))


def _iter_rect_cells(rect, cell_size, padding=0.0):
    x0 = _grid_key(rect.x0 - padding, cell_size)
    x1 = _grid_key(rect.x1 + padding, cell_size)
    y0 = _grid_key(rect.y0 - padding, cell_size)
    y1 = _grid_key(rect.y1 + padding, cell_size)
    for gx in range(x0, x1 + 1):
        for gy in range(y0, y1 + 1):
            yield gx, gy


def extract_vector_labeled_piers(pdf_path, page_index=0, cell_size=12.0):
    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(page_index)
        page_rect = page.rect
        words = page.get_text("words")
        raw_drawings = page.get_drawings()
    finally:
        doc.close()

    labels = [word for word in words if PIER_LABEL_RE.match(str(word[4]).upper())]

    symbol_candidates = []
    symbol_grid = {}
    for drawing in raw_drawings:
        pier_type = _classify_vector_symbol(drawing)
        if not pier_type:
            continue
        rect = fitz.Rect(drawing["rect"])
        center_x = float((rect.x0 + rect.x1) / 2.0)
        center_y = float((rect.y0 + rect.y1) / 2.0)
        item = {
            "pier_type": pier_type,
            "rect": rect,
            "center_x": center_x,
            "center_y": center_y,
        }
        idx = len(symbol_candidates)
        symbol_candidates.append(item)
        for key in _iter_rect_cells(rect, cell_size, padding=2.0):
            symbol_grid.setdefault(key, []).append(idx)

    pier_rows = []
    type_counts = Counter()
    label_counts = Counter()
    unresolved = []

    for word in labels:
        label = str(word[4]).upper()
        label_rect = fitz.Rect(word[0], word[1], word[2], word[3])
        center_x = float((label_rect.x0 + label_rect.x1) / 2.0)
        center_y = float((label_rect.y0 + label_rect.y1) / 2.0)

        nearby_ids = set()
        for key in _iter_rect_cells(label_rect, cell_size, padding=2.0):
            nearby_ids.update(symbol_grid.get(key, []))

        best = None
        best_distance = float("inf")
        for idx in nearby_ids:
            candidate = symbol_candidates[idx]
            rect = candidate["rect"]
            distance = float(np.hypot(candidate["center_x"] - center_x, candidate["center_y"] - center_y))
            if rect.intersects(label_rect + (-2.0, -2.0, 2.0, 2.0)) or distance <= 4.5:
                if distance < best_distance:
                    best_distance = distance
                    best = candidate

        if best is None:
            unresolved.append({
                "label": label,
                "x": center_x,
                "y": center_y,
            })
            continue

        row = {
            "label": label,
            "pier_type": best["pier_type"],
            "x": center_x,
            "y": center_y,
            "x_rel": float(center_x / max(float(page_rect.width), 1.0)),
            "y_rel": float(center_y / max(float(page_rect.height), 1.0)),
            "symbol_x0": float(best["rect"].x0),
            "symbol_y0": float(best["rect"].y0),
            "symbol_x1": float(best["rect"].x1),
            "symbol_y1": float(best["rect"].y1),
        }
        pier_rows.append(row)
        type_counts[row["pier_type"]] += 1
        label_counts[label] += 1

    return {
        "page_width": float(page_rect.width),
        "page_height": float(page_rect.height),
        "label_count": len(labels),
        "resolved_count": len(pier_rows),
        "unresolved_count": len(unresolved),
        "pier_type_counts": dict(type_counts),
        "label_counts": dict(sorted(label_counts.items(), key=lambda item: (int(item[0][1:]), item[0]))),
        "piers": pier_rows,
        "unresolved": unresolved,
    }


def export_labeled_pier_json(out_path, result):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return out_path


def export_labeled_pier_csv(out_path, result):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "pier_id",
            "label",
            "pier_type",
            "x",
            "y",
            "x_rel",
            "y_rel",
            "symbol_x0",
            "symbol_y0",
            "symbol_x1",
            "symbol_y1",
        ])
        for idx, row in enumerate(result["piers"], start=1):
            writer.writerow([
                f"VP{idx:05d}",
                row["label"],
                row["pier_type"],
                round(row["x"], 6),
                round(row["y"], 6),
                round(row["x_rel"], 6),
                round(row["y_rel"], 6),
                round(row["symbol_x0"], 6),
                round(row["symbol_y0"], 6),
                round(row["symbol_x1"], 6),
                round(row["symbol_y1"], 6),
            ])
    return out_path


def export_labeled_pier_type_map_svg(out_path, result, title="Vector Pier Type Map"):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    page_width = float(result["page_width"])
    page_height = float(result["page_height"])
    piers = result["piers"]

    canvas_width = 1600
    canvas_height = 1000
    margin = 44
    scale = min(
        (canvas_width - 2 * margin) / max(page_width, 1.0),
        (canvas_height - 2 * margin) / max(page_height, 1.0),
    )
    plot_width = page_width * scale
    plot_height = page_height * scale
    offset_x = (canvas_width - plot_width) / 2.0
    offset_y = (canvas_height - plot_height) / 2.0

    def sx(value):
        return offset_x + float(value) * scale

    def sy(value):
        return offset_y + float(value) * scale

    style_by_type = {
        "SAP": {"fill": "#3cd6e6", "stroke": "none"},
        "SAPE": {"fill": "#6241ff", "stroke": "none"},
        "SAPEND": {"fill": "#d77a18", "stroke": "none"},
        "SMP": {"fill": "#00b9c7", "stroke": "none"},
        "HAP": {"fill": "#e23a3a", "stroke": "none"},
        "HMP": {"fill": "#c81414", "stroke": "none"},
    }

    lines = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{canvas_width}' height='{canvas_height}' viewBox='0 0 {canvas_width} {canvas_height}'>",
        "  <rect width='100%' height='100%' fill='#f7f2e8' />",
        f"  <text x='{margin}' y='30' font-family='Segoe UI, Arial, sans-serif' font-size='22' fill='#1d2a33'>{title}</text>",
        f"  <text x='{margin}' y='52' font-family='Segoe UI, Arial, sans-serif' font-size='12' fill='#4a5a68'>Vector-text anchored pier symbols classified from the PDF drawing layer.</text>",
        f"  <rect x='{offset_x:.2f}' y='{offset_y:.2f}' width='{plot_width:.2f}' height='{plot_height:.2f}' fill='#fffdf8' stroke='#c8bba8' stroke-width='1.5' />",
    ]

    for row in piers:
        px = sx(row["x"])
        py = sy(row["y"])
        style = style_by_type.get(row["pier_type"], {"fill": "#444444", "stroke": "none"})
        lines.append(
            f"  <circle cx='{px:.2f}' cy='{py:.2f}' r='1.9' fill='{style['fill']}' fill-opacity='0.86' stroke='{style['stroke']}' />"
        )

    legend_x = canvas_width - 290
    legend_y = 28
    legend_rows = [
        ("SAP", "#3cd6e6"),
        ("SAPE", "#6241ff"),
        ("SAPEND", "#d77a18"),
        ("SMP", "#00b9c7"),
        ("HAP", "#e23a3a"),
        ("HMP", "#c81414"),
    ]
    legend_height = 26 + len(legend_rows) * 18 + 20
    lines.append(
        f"  <rect x='{legend_x}' y='{legend_y}' width='230' height='{legend_height}' rx='8' fill='#fffdf8' stroke='#c8bba8' stroke-width='1' />"
    )
    for idx, (label, color) in enumerate(legend_rows):
        y = legend_y + 22 + idx * 18
        count = result["pier_type_counts"].get(label, 0)
        lines.append(f"  <circle cx='{legend_x + 16}' cy='{y}' r='4' fill='{color}' />")
        lines.append(
            f"  <text x='{legend_x + 30}' y='{y + 4}' font-family='Segoe UI, Arial, sans-serif' font-size='12' fill='#1d2a33'>{label}: {count}</text>"
        )
    lines.append(
        f"  <text x='{legend_x + 14}' y='{legend_y + legend_height - 10}' font-family='Segoe UI, Arial, sans-serif' font-size='11' fill='#4a5a68'>Resolved {result['resolved_count']} of {result['label_count']} labels</text>"
    )
    lines.append("</svg>")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
