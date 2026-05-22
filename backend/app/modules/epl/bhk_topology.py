"""BHK electrical topology reconstruction.

Reconstructs the real per-string electrical route from the BHK E20 cable
plan, using the dedicated ``BE-STRINGS`` CAD layer which cleanly isolates
routing from panels/roads/contours.

On that layer each string is drawn as:
  - one green start triangle
  - one red end circle
  - one black routed *ribbon* (a thin stroked outline, ~3pt wide, traced
    out-and-back) whose centerline is the cable route

A near-vertical centerline run that spans a row pitch (~15pt) means the
SAME string continues on an adjacent physical row (a "jump"). Panel pairs
for every event are derived from E41 panel geometry using SOUTH-origin
numbering.

Output per string (spec):
    {"string": "2.2.1.7", "events": [
        {"type": "start",     "row": "ROW_061", "between_panels": [54, 55]},
        {"type": "exit_row",  "row": "ROW_061", "between_panels": [45, 46]},
        {"type": "enter_row", "row": "ROW_062", "between_panels": [45, 46]},
        {"type": "end",       "row": "ROW_062", "between_panels": [20, 21]},
    ]}
"""
from __future__ import annotations

import math
from typing import Any

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

STRINGS_LAYER = "BE-STRINGS"

# Geometry thresholds (PDF points). Calibrated against BHK_E_20: ribbon
# width ~3pt, row pitch ~15pt, panel pitch ~5pt.
MIN_SIG_LEN = 6.0          # ignore ribbon-width artifacts shorter than this
MIN_JUMP_LEN = 8.0         # a row-to-row jump segment is at least this long
VERT_ANGLE_MIN = 60.0      # degrees from horizontal to count as a jump
RUN_ANGLE_TOL = 14.0       # clustering: max angle delta for parallel edges
RUN_PERP_TOL = 5.0         # clustering: max perpendicular gap for ribbon edges
START_MATCH_MAX = 70.0     # green/label-to-route endpoint match radius
PANEL_ROW_MAX = 14.0       # max perpendicular distance to assign a point to a row


def _rgb(color):
    if not color or len(color) < 3:
        return None
    return tuple(float(c) for c in color[:3])


def _color_class(c):
    if c is None:
        return "none"
    r, g, b = c
    if r > 0.85 and g < 0.2 and b < 0.2:
        return "red"
    if g > 0.7 and r < 0.3 and b < 0.3:
        return "green"
    if max(r, g, b) < 0.2:
        return "black"
    return "other"


def _ribbon_vertices(d) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for it in d.get("items") or []:
        if it[0] == "l":
            p0, p1 = it[1], it[2]
            if not pts:
                pts.append((p0.x, p0.y))
            pts.append((p1.x, p1.y))
    return pts


def _centroid(d):
    r = d.get("rect")
    if not r:
        return None
    return ((r.x0 + r.x1) / 2.0, (r.y0 + r.y1) / 2.0)


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _point_line_dist(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    denom = dx * dx + dy * dy
    if denom < 1e-9:
        return _dist(p, a)
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / denom
    qx, qy = a[0] + dx * t, a[1] + dy * t
    return math.hypot(p[0] - qx, p[1] - qy)


def load_be_strings(page) -> dict[str, Any]:
    """Extract starts, ends and routed ribbons from the BE-STRINGS layer."""
    greens: list[tuple[float, float]] = []
    reds: list[tuple[float, float]] = []
    ribbons: list[list[tuple[float, float]]] = []
    for d in page.get_drawings():
        if str(d.get("layer") or "") != STRINGS_LAYER:
            continue
        cls = _color_class(_rgb(d.get("color")))
        if cls == "green":
            ce = _centroid(d)
            if ce:
                greens.append(ce)
        elif cls == "red":
            ce = _centroid(d)
            if ce:
                reds.append(ce)
        elif cls == "black":
            verts = _ribbon_vertices(d)
            if len(verts) >= 2:
                ribbons.append(verts)
    return {"greens": greens, "reds": reds, "ribbons": ribbons}


def ribbon_centerline_runs(ribbon: list[tuple[float, float]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Collapse a ribbon outline into centerline run segments.

    The ribbon is a thin stroked outline: every logical run appears twice
    (the two parallel edges). We keep significant segments, cluster the
    parallel/overlapping ones, and emit one centerline segment per cluster.
    """
    raw: list[tuple[tuple[float, float], tuple[float, float], float]] = []
    for i in range(len(ribbon) - 1):
        a, b = ribbon[i], ribbon[i + 1]
        L = _dist(a, b)
        if L >= MIN_SIG_LEN:
            raw.append((a, b, L))
    used = [False] * len(raw)
    runs: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for i in range(len(raw)):
        if used[i]:
            continue
        a, b, L = raw[i]
        ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180.0
        members = [(a, b)]
        used[i] = True
        for j in range(i + 1, len(raw)):
            if used[j]:
                continue
            a2, b2, _ = raw[j]
            ang2 = math.degrees(math.atan2(b2[1] - a2[1], b2[0] - a2[0])) % 180.0
            da = abs(ang - ang2)
            da = min(da, 180.0 - da)
            if da > RUN_ANGLE_TOL:
                continue
            mid2 = ((a2[0] + b2[0]) / 2.0, (a2[1] + b2[1]) / 2.0)
            if _point_line_dist(mid2, a, b) > RUN_PERP_TOL:
                continue
            members.append((a2, b2))
            used[j] = True
        runs.append(_merge_run(members))
    return runs


def _merge_run(members) -> tuple[tuple[float, float], tuple[float, float]]:
    """Average a cluster of parallel ribbon edges into one centerline run."""
    # Principal direction from the longest member.
    longest = max(members, key=lambda m: _dist(m[0], m[1]))
    ax, ay = longest[0]
    bx, by = longest[1]
    dx, dy = bx - ax, by - ay
    norm = math.hypot(dx, dy) or 1.0
    ux, uy = dx / norm, dy / norm
    pts = [p for m in members for p in m]
    # Project onto direction; perpendicular offset averaged for centerline.
    projs = [((p[0] - ax) * ux + (p[1] - ay) * uy) for p in pts]
    perps = [(-(p[0] - ax) * uy + (p[1] - ay) * ux) for p in pts]
    mean_perp = sum(perps) / len(perps)
    tmin, tmax = min(projs), max(projs)
    def at(t):
        return (ax + ux * t - uy * mean_perp, ay + uy * t + ux * mean_perp)
    return (at(tmin), at(tmax))


def _seg_angle(p, q) -> float:
    ang = abs(math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])))
    return 180 - ang if ang > 90 else ang


def classify_runs(runs):
    """Split centerline runs into horizontal (row traversals) and vertical
    (row-to-row jumps)."""
    horiz = []  # (midpoint, p, q)
    vert = []   # (p, q)
    for p, q in runs:
        ang = _seg_angle(p, q)
        L = _dist(p, q)
        if ang >= VERT_ANGLE_MIN and L >= MIN_JUMP_LEN:
            vert.append((p, q))
        elif ang <= 35.0:
            mid = ((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0)
            horiz.append((mid, p, q))
    return horiz, vert


def _row_axis(row):
    sx, sy = float(row["south_x"]), float(row["south_y"])
    nx, ny = float(row["north_x"]), float(row["north_y"])
    return sx, sy, nx, ny


def assign_row(point, panel_rows) -> int | None:
    """Return the 1-based south-origin panel-row index nearest to point."""
    best = None
    for idx, row in enumerate(panel_rows):
        sx, sy, nx, ny = _row_axis(row)
        dx, dy = nx - sx, ny - sy
        denom = dx * dx + dy * dy or 1.0
        t = ((point[0] - sx) * dx + (point[1] - sy) * dy) / denom
        if t < -0.1 or t > 1.1:
            continue
        qx, qy = sx + dx * t, sy + dy * t
        dist = math.hypot(point[0] - qx, point[1] - qy)
        if best is None or dist < best[0]:
            best = (dist, idx)
    if best and best[0] <= PANEL_ROW_MAX:
        return best[1] + 1
    return None


def panel_pair_at(point, panel_rows, row_idx: int | None = None) -> dict[str, Any]:
    """Bracketing south-origin panel pair for an event point."""
    if row_idx is None:
        row_idx = assign_row(point, panel_rows)
    if not row_idx:
        return {"row_index": None, "between_panels": None}
    row = panel_rows[row_idx - 1]
    sx, sy, nx, ny = _row_axis(row)
    dx, dy = nx - sx, ny - sy
    denom = dx * dx + dy * dy or 1.0
    t_pt = ((point[0] - sx) * dx + (point[1] - sy) * dy) / denom
    panels = sorted(row.get("panels") or [], key=lambda p: float(p.get("t", 0)))
    if not panels:
        return {"row_index": row_idx, "between_panels": None}
    # Find the two panels bracketing t_pt (south side first).
    south = None
    north = None
    for p in panels:
        if float(p["t"]) <= t_pt:
            south = p
        else:
            north = p
            break
    if south is None:
        north = panels[0]
        return {"row_index": row_idx, "between_panels": [max(1, int(north["panel"]) - 1), int(north["panel"])]}
    if north is None:
        south = panels[-1]
        return {"row_index": row_idx, "between_panels": [int(south["panel"]), int(south["panel"]) + 1]}
    return {"row_index": row_idx, "between_panels": [int(south["panel"]), int(north["panel"])]}


def _row_id(row_idx: int | None) -> str | None:
    if not row_idx:
        return None
    return f"ROW_{row_idx:03d}"


def _south_row(internal_idx: int | None, n_rows: int) -> int | None:
    """Convert internal row index (ascending PDF-Y, 1=top/north) to the
    site's south-origin physical-row number (ROW_001 = bottom = south)."""
    if not internal_idx:
        return None
    return n_rows - internal_idx + 1


def route_events(runs, start_pt, end_pt, panel_rows, n_rows: int | None = None) -> list[dict[str, Any]]:
    """Derive ordered start/exit_row/enter_row/end events from centerline runs.

    Strategy (order-robust): classify runs into horizontal traversals and
    vertical jumps. The set of occupied rows is ordered from the start row
    toward the end row; each consecutive row transition is matched to the
    vertical jump run that bridges those two rows, giving the exit/enter
    panel pairs. Emitted row numbers are south-origin (ROW_001 = bottom).
    """
    if n_rows is None:
        n_rows = len(panel_rows)
    horiz, vert = classify_runs(runs)
    start_row = assign_row(start_pt, panel_rows)
    end_row = assign_row(end_pt, panel_rows)

    occupied = set()
    for mid, _p, _q in horiz:
        r = assign_row(mid, panel_rows)
        if r:
            occupied.add(r)
    if start_row:
        occupied.add(start_row)
    if end_row:
        occupied.add(end_row)

    events: list[dict[str, Any]] = []
    if not start_row:
        return events

    # Order rows along the direction of travel (start -> end).
    if end_row and end_row != start_row:
        step = 1 if end_row > start_row else -1
        ordered_rows = list(range(start_row, end_row + step, step))
        # Keep only rows actually occupied (plus the endpoints).
        ordered_rows = [r for r in ordered_rows if r in occupied or r in (start_row, end_row)]
    else:
        ordered_rows = [start_row]

    # Pre-index vertical jumps by the (row_a, row_b) pair they connect.
    jump_index: dict[tuple[int, int], tuple] = {}
    for p, q in vert:
        ra = assign_row(p, panel_rows)
        rb = assign_row(q, panel_rows)
        if ra and rb and ra != rb:
            jump_index[(min(ra, rb), max(ra, rb))] = (p, q, ra, rb)

    pp_start = panel_pair_at(start_pt, panel_rows, start_row)
    sr = _south_row(start_row, n_rows)
    events.append({"type": "start", "row": _row_id(sr), "physical_row": sr, "between_panels": pp_start["between_panels"]})

    for i in range(len(ordered_rows) - 1):
        r_a, r_b = ordered_rows[i], ordered_rows[i + 1]
        jump = jump_index.get((min(r_a, r_b), max(r_a, r_b)))
        if jump:
            p, q, ra, rb = jump
            exit_pt = p if ra == r_a else q
            enter_pt = q if ra == r_a else p
        else:
            # No explicit vertical run found; approximate the crossing x as
            # the mean of the two rows' horizontal-run midpoints.
            exit_pt = enter_pt = _row_crossing_guess(r_a, r_b, horiz, panel_rows)
        ex = panel_pair_at(exit_pt, panel_rows, r_a)
        en = panel_pair_at(enter_pt, panel_rows, r_b)
        sa, sb = _south_row(r_a, n_rows), _south_row(r_b, n_rows)
        events.append({"type": "exit_row", "row": _row_id(sa), "physical_row": sa, "between_panels": ex["between_panels"]})
        events.append({"type": "enter_row", "row": _row_id(sb), "physical_row": sb, "between_panels": en["between_panels"]})

    pp_end = panel_pair_at(end_pt, panel_rows, end_row)
    er = _south_row(end_row, n_rows)
    events.append({"type": "end", "row": _row_id(er), "physical_row": er, "between_panels": pp_end["between_panels"]})
    return events


def row_coverage(runs, start_pt, end_pt, panel_rows, n_rows: int | None = None) -> dict[str, Any]:
    """Per-row panel coverage, counting each row's panels ONCE.

    A string runs out along a row and back to the start before jumping, so
    the drawing shows the same panels twice. We take the min..max panel the
    horizontal runs reach on each row (the physical extent) — independent of
    how many times the cable retraces it — and report it once. Summing the
    per-row spans yields the string's total panels, which should equal
    ~44 (22 series optimizers x 2 panels each).
    """
    if n_rows is None:
        n_rows = len(panel_rows)
    horiz, _vert = classify_runs(runs)
    by_row: dict[int, list[int]] = {}
    for _mid, p, q in horiz:
        for pt in (p, q):
            idx = assign_row(pt, panel_rows)
            if not idx:
                continue
            pp = panel_pair_at(pt, panel_rows, idx)
            if pp["between_panels"]:
                by_row.setdefault(idx, []).extend(pp["between_panels"])
    # Make sure the start/end anchors are included.
    for pt in (start_pt, end_pt):
        idx = assign_row(pt, panel_rows)
        if idx:
            pp = panel_pair_at(pt, panel_rows, idx)
            if pp["between_panels"]:
                by_row.setdefault(idx, []).extend(pp["between_panels"])
    rows = []
    total = 0
    for idx, panels in by_row.items():
        lo, hi = min(panels), max(panels)
        count = hi - lo + 1
        total += count
        rows.append({
            "physical_row": _south_row(idx, n_rows),
            "panel_from": lo,
            "panel_to": hi,
            "panel_count": count,
        })
    rows.sort(key=lambda r: r["physical_row"])
    return {"rows": rows, "total_panels": total, "optimizer_count": round(total / 2)}


def _row_crossing_guess(r_a, r_b, horiz, panel_rows):
    """Fallback crossing point when no clean vertical jump run is found:
    the end of row r_a's horizontal run nearest row r_b."""
    cands = []
    for mid, p, q in horiz:
        if assign_row(mid, panel_rows) == r_a:
            cands.extend([p, q])
    if not cands:
        row = panel_rows[r_a - 1]
        return ((float(row["south_x"]) + float(row["north_x"])) / 2, (float(row["south_y"]) + float(row["north_y"])) / 2)
    # Pick the candidate whose y is closest to row r_b.
    rb_row = panel_rows[r_b - 1]
    rb_y = (float(rb_row["south_y"]) + float(rb_row["north_y"])) / 2
    return min(cands, key=lambda c: abs(c[1] - rb_y))


MARKER_ON_CABLE_MAX = 18.0  # green/red sit ON the cable ribbon


def _min_vertex_dist(ribbon, point) -> float:
    return min(_dist(v, point) for v in ribbon)


def reconstruct_topology(e20_page, panel_rows, label_words: list[dict[str, Any]] | None = None, include_geometry: bool = False) -> dict[str, Any]:
    """Full reconstruction. Returns {"strings": [...], "stats": {...}}.

    When include_geometry is set, each string gains a ``segments`` list of
    [x0, y0, x1, y1, kind] centerline runs ("h" traversal / "jump"), for map
    rendering and visual verification.
    """
    prims = load_be_strings(e20_page)
    greens, reds, ribbons = prims["greens"], prims["reds"], prims["ribbons"]

    # Each green/red marker sits ON exactly one cable ribbon. Assign every
    # marker to the ribbon with the nearest vertex.
    green_ribbon = [_argmin_ribbon(ribbons, g) for g in greens]
    red_ribbon = [_argmin_ribbon(ribbons, r) for r in reds]

    by_ribbon: dict[int, dict[str, Any]] = {}
    for gi, ri_idx in enumerate(green_ribbon):
        if ri_idx is None:
            continue
        by_ribbon.setdefault(ri_idx, {}).setdefault("greens", []).append(gi)
    for rdi, ri_idx in enumerate(red_ribbon):
        if ri_idx is None:
            continue
        by_ribbon.setdefault(ri_idx, {}).setdefault("reds", []).append(rdi)

    strings: list[dict[str, Any]] = []
    for ribbon_idx, members in by_ribbon.items():
        g_list = members.get("greens") or []
        r_list = members.get("reds") or []
        if not g_list or not r_list:
            continue
        ribbon = ribbons[ribbon_idx]
        # Pick the green/red closest to the ribbon (most confident).
        gi = min(g_list, key=lambda i: _min_vertex_dist(ribbon, greens[i]))
        rdi = min(r_list, key=lambda i: _min_vertex_dist(ribbon, reds[i]))
        green, red = greens[gi], reds[rdi]
        runs = ribbon_centerline_runs(ribbon)
        events = route_events(runs, green, red, panel_rows)
        coverage = row_coverage(runs, green, red, panel_rows)
        entry = {
            "string": None,
            "ribbon_idx": ribbon_idx,
            "start_xy": [round(green[0], 2), round(green[1], 2)],
            "end_xy": [round(red[0], 2), round(red[1], 2)],
            "_green": green,
            "_ribbon": ribbon,
            "events": events,
            "rows": coverage["rows"],
            "total_panels": coverage["total_panels"],
            "optimizer_count": coverage["optimizer_count"],
            "jump_count": sum(1 for e in events if e["type"] == "enter_row"),
        }
        if include_geometry:
            horiz, vert = classify_runs(runs)
            segs = [[round(p[0], 2), round(p[1], 2), round(q[0], 2), round(q[1], 2), "h"] for _m, p, q in horiz]
            segs += [[round(p[0], 2), round(p[1], 2), round(q[0], 2), round(q[1], 2), "jump"] for p, q in vert]
            entry["segments"] = segs
        strings.append(entry)

    if label_words:
        _assign_labels(strings, label_words)
    for s in strings:
        s.pop("_green", None)
        s.pop("_ribbon", None)

    multi = sum(1 for s in strings if s["jump_count"] >= 1)
    on_target = sum(1 for s in strings if 42 <= int(s.get("total_panels", 0)) <= 46)
    return {
        "strings": strings,
        "stats": {
            "ribbons": len(ribbons),
            "greens": len(greens),
            "reds": len(reds),
            "matched_strings": len(strings),
            "multi_row_strings": multi,
            "labeled_strings": sum(1 for s in strings if s["string"]),
            "strings_at_44_panels": on_target,
        },
    }


LABEL_ASSIGN_MAX = 200.0  # reject Hungarian matches farther than this


def _label_cost(label_pt, s) -> float:
    """Cost of attaching a label to a cable.

    The label names the string and is drawn along the FIRST row run, right
    by the green start triangle. So the best anchor is the start: take the
    distance from the label to the green start, but allow the label to sit
    anywhere along the start row by also crediting closeness to the ribbon.
    Combine: mostly start-distance, with the ribbon distance as a tie-breaker
    so a label sitting further out along its own row still wins over a
    different cable whose start happens to be nearer.
    """
    start_d = _dist(label_pt, s["_green"])
    ribbon_d = _min_vertex_dist(s["_ribbon"], label_pt)
    return 0.65 * start_d + 0.35 * ribbon_d


def _assign_labels(strings, label_words) -> None:
    """Assign each dotted x.x.x.x label to its cable via global 1:1 matching.

    Labels are drawn along the first row run by the green start triangle, so
    we score each (label, cable) pair with _label_cost and solve the optimal
    assignment (Hungarian), rejecting matches beyond a sane radius. Falls
    back to greedy nearest if scipy is unavailable.
    """
    if not strings:
        return
    labels = [(w["text"], (w["x"], w["y"])) for w in label_words]
    if not labels:
        return
    try:
        import numpy as np
        from scipy.optimize import linear_sum_assignment

        cost = np.zeros((len(labels), len(strings)))
        for i, (_t, lp) in enumerate(labels):
            for j, s in enumerate(strings):
                cost[i][j] = _label_cost(lp, s)
        rows, cols = linear_sum_assignment(cost)
        for i, j in zip(rows, cols):
            if cost[i][j] <= LABEL_ASSIGN_MAX:
                strings[j]["string"] = labels[i][0]
    except Exception:
        for s in strings:
            best = None
            for t, lp in labels:
                d = _label_cost(lp, s)
                if best is None or d < best[0]:
                    best = (d, t)
            if best and best[0] <= LABEL_ASSIGN_MAX:
                s["string"] = best[1]


def _argmin_ribbon(ribbons, point) -> int | None:
    best = None
    for idx, ribbon in enumerate(ribbons):
        d = _min_vertex_dist(ribbon, point)
        if d <= MARKER_ON_CABLE_MAX and (best is None or d < best[0]):
            best = (d, idx)
    return best[1] if best else None


def _nearest_label(point, label_words) -> str | None:
    best = None
    for w in label_words:
        d = _dist(point, (w["x"], w["y"]))
        if best is None or d < best[0]:
            best = (d, w["text"])
    return best[1] if best and best[0] <= START_MATCH_MAX else None
