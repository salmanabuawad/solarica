"""Reconstruct per-string topology from the PANELS plan (E_41).

The panels plan is far cleaner than the cable plan (E_20):
  * BE-STRINGS carries exactly one green start triangle + one red end circle
    per string (no avocado-tree noise to filter).
  * Every panel is a single coloured rectangle on an EN-PANEL <colour> layer,
    and a string's start and end sit on panels of the SAME colour.

Strings are found by pairing start->end (same colour + row span <= 4, optimal
assignment) and recovering each string's panels with a grid-graph same-colour
flood-fill (structural row adjacency, not pixel distance). The route is drawn
as a ladder: one horizontal run per occupied row + short jumps between
adjacent rows -- so no cross-sheet diagonal lines can appear.

Output matches ``string_topology.reconstruct_topology`` so the rest of the
pipeline and the map render unchanged. All geometry is in the E_41 frame
(same as ``panel_rows``); only the x.x.x.x labels come from E_20 and are
translated into the E_41 frame by a rigid offset derived from the markers.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any

from .string_topology import assign_row, _south_row, _row_id, panel_pair_at, _dist

MAX_SPAN_ROWS = 4          # a string occupies up to 2-4 nearby rows end-to-end
PANEL_W = (4.5, 7.2)       # panel rectangle width range (pdf pt)
PANEL_H = (9.0, 12.2)      # panel rectangle height range
SAME_ROW_T = 0.03          # along-row gap (t units) for same-row adjacency
CROSS_ROW_T = 0.03         # along-row gap to link a panel to the adjacent row
MAX_JUMP_LEN = 70.0        # never draw a jump longer than this (a few row pitches)


def _is_green(s) -> bool:
    return bool(s) and s[1] > 0.5 and s[0] < 0.5 and s[2] < 0.5


def _is_red(s) -> bool:
    return bool(s) and s[0] > 0.5 and s[1] < 0.4 and s[2] < 0.4


def load_panel_primitives(page) -> dict[str, Any]:
    greens: list[tuple[float, float]] = []
    reds: list[tuple[float, float]] = []
    panels: list[dict[str, Any]] = []
    for dr in page.get_drawings():
        layer = str(dr.get("layer") or "")
        items = dr.get("items") or []
        rect = dr.get("rect")
        if rect is None:
            continue
        cx = (float(rect.x0) + float(rect.x1)) / 2.0
        cy = (float(rect.y0) + float(rect.y1)) / 2.0
        if "EN-PANEL" in layer:
            if len(items) == 1 and items[0][0] == "qu":
                w = abs(float(rect.x1) - float(rect.x0))
                h = abs(float(rect.y1) - float(rect.y0))
                if PANEL_W[0] <= w <= PANEL_W[1] and PANEL_H[0] <= h <= PANEL_H[1]:
                    panels.append({"cx": cx, "cy": cy, "color": layer.split("|")[-1]})
            continue
        if "BE-STRINGS" not in layer:
            continue
        nl = sum(1 for it in items if it and it[0] == "l")
        nc = sum(1 for it in items if it and it[0] == "c")
        stroke = dr.get("color")
        if nl >= 3 and nc == 0 and _is_green(stroke):
            greens.append((cx, cy))
        elif nc >= 3 and _is_red(stroke):
            reds.append((cx, cy))
    return {"greens": greens, "reds": reds, "panels": panels}


def _row_axis(row):
    return float(row["south_x"]), float(row["south_y"]), float(row["north_x"]), float(row["north_y"])


def _row_t(point, panel_rows, row_idx: int) -> float:
    sx, sy, nx, ny = _row_axis(panel_rows[row_idx - 1])
    dx, dy = nx - sx, ny - sy
    denom = dx * dx + dy * dy or 1.0
    return ((point[0] - sx) * dx + (point[1] - sy) * dy) / denom


def _load_e20_labels(page):
    out = []
    for w in page.get_text("words") or []:
        t = str(w[4]).strip()
        if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", t):
            out.append({"text": t, "x": (float(w[0]) + float(w[2])) / 2, "y": (float(w[1]) + float(w[3])) / 2})
    return out


def _load_e20_greens(page):
    g = []
    for dr in page.get_drawings():
        if "BE-STRINGS" not in str(dr.get("layer") or ""):
            continue
        items = dr.get("items") or []
        nl = sum(1 for it in items if it and it[0] == "l")
        nc = sum(1 for it in items if it and it[0] == "c")
        if nl >= 3 and nc == 0 and _is_green(dr.get("color")):
            r = dr.get("rect")
            g.append(((float(r.x0) + float(r.x1)) / 2, (float(r.y0) + float(r.y1)) / 2))
    return g


def _pair_start_end(greens, reds, g_color, r_color, g_row, r_row):
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    G = np.array(greens, dtype=float)
    R = np.array(reds, dtype=float)
    D = np.sqrt(((G[:, None, :] - R[None, :, :]) ** 2).sum(-1))
    BIG = 1e9
    cost = D.copy()
    for i in range(len(greens)):
        for j in range(len(reds)):
            if g_color[i] != r_color[j] or g_row[i] is None or r_row[j] is None:
                cost[i, j] = BIG
            elif abs(g_row[i] - r_row[j]) > MAX_SPAN_ROWS:
                cost[i, j] = BIG
    ri, ci = linear_sum_assignment(cost)
    return [(int(i), int(j)) for i, j in zip(ri, ci) if cost[i, j] < BIG]


def _build_grid_adjacency(panels, prow, ptv):
    by_row = defaultdict(list)
    for i in range(len(panels)):
        if prow[i] is not None:
            by_row[prow[i]].append(i)
    for r in by_row:
        by_row[r].sort(key=lambda i: ptv[i])
    adj = defaultdict(set)
    for idxs in by_row.values():
        for a, b in zip(idxs, idxs[1:]):
            if abs(ptv[b] - ptv[a]) < SAME_ROW_T:
                adj[a].add(b); adj[b].add(a)
    import numpy as np
    for r in sorted(by_row):
        nr = r + 1
        if nr not in by_row:
            continue
        B = by_row[nr]
        Bt = np.array([ptv[i] for i in B])
        for i in by_row[r]:
            j = B[int(np.argmin(np.abs(Bt - ptv[i])))]
            if abs(ptv[j] - ptv[i]) < CROSS_ROW_T:
                adj[i].add(j); adj[j].add(i)
    return adj, by_row


def reconstruct_topology_from_panels(e41_page, panel_rows, e20_page=None, include_geometry: bool = True) -> dict[str, Any]:
    import numpy as np
    from scipy.spatial import cKDTree

    prims = load_panel_primitives(e41_page)
    greens, reds, panels = prims["greens"], prims["reds"], prims["panels"]
    n_rows = len(panel_rows)
    if not panels or not greens or not reds:
        return {"strings": [], "piers": [], "stats": {"status": "no_panel_primitives",
                "greens": len(greens), "reds": len(reds), "panels": len(panels)}}

    pxy = np.array([(p["cx"], p["cy"]) for p in panels], dtype=float)
    pcolor = [p["color"] for p in panels]
    prow = [assign_row((p["cx"], p["cy"]), panel_rows) for p in panels]
    ptv = [(_row_t((p["cx"], p["cy"]), panel_rows, prow[i]) if prow[i] else 0.0) for i, p in enumerate(panels)]
    ptree = cKDTree(pxy)
    adj, _by_row = _build_grid_adjacency(panels, prow, ptv)

    def marker(pt):
        _, k = ptree.query(pt)
        return pcolor[k], prow[k], int(k)

    g_color, g_row, g_panel = [], [], []
    for g in greens:
        c, r, k = marker(g); g_color.append(c); g_row.append(r); g_panel.append(k)
    r_color, r_row, r_panel = [], [], []
    for r in reds:
        c, rr, k = marker(r); r_color.append(c); r_row.append(rr); r_panel.append(k)

    pairs = _pair_start_end(greens, reds, g_color, r_color, g_row, r_row)

    # labels: only on E_20 -> register by green centroid (rigid) + translate
    labels_e41 = []
    if e20_page is not None:
        e20_labels = _load_e20_labels(e20_page)
        e20_greens = _load_e20_greens(e20_page)
        if e20_greens and greens:
            dx = float(np.array(e20_greens).mean(0)[0] - np.array(greens).mean(0)[0])
            dy = float(np.array(e20_greens).mean(0)[1] - np.array(greens).mean(0)[1])
            labels_e41 = [{"text": l["text"], "x": l["x"] - dx, "y": l["y"] - dy} for l in e20_labels]

    def flood(start_idx, color):
        seen = {start_idx}; stack = [start_idx]
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if v not in seen and pcolor[v] == color:
                    seen.add(v); stack.append(v)
        return seen

    strings: list[dict[str, Any]] = []
    for idx, (gi, rj) in enumerate(pairs):
        start_pt, end_pt = greens[gi], reds[rj]
        sr, er = g_row[gi], r_row[rj]
        comp = flood(g_panel[gi], g_color[gi])

        # The string's panels are a grid-connected component, so its rows are
        # contiguous. Draw the route over THOSE rows only (no interpolation):
        # one vertical run per row + a short jump between adjacent rows. This
        # makes a long cross-sheet jump structurally impossible.
        comp_rows = sorted({prow[i] for i in comp if prow[i] is not None}) or [sr]
        runs: dict[int, tuple[tuple[float, float], tuple[float, float]]] = {}
        for r in comp_rows:
            pts = sorted((pxy[i] for i in comp if prow[i] == r), key=lambda p: p[1])
            if pts:
                runs[r] = ((float(pts[0][0]), float(pts[0][1])), (float(pts[-1][0]), float(pts[-1][1])))
        comp_rows = [r for r in comp_rows if r in runs] or [sr]
        if sr not in runs:
            runs[sr] = (start_pt, start_pt)
            if sr not in comp_rows:
                comp_rows = sorted(set(comp_rows + [sr]))
        # orient so the run nearest the start marker comes first
        ordered = comp_rows if abs(comp_rows[0] - sr) <= abs(comp_rows[-1] - sr) else comp_rows[::-1]

        events = [{"type": "start", "row": _row_id(_south_row(sr, n_rows)), "physical_row": _south_row(sr, n_rows),
                   "between_panels": panel_pair_at(start_pt, panel_rows, sr)["between_panels"]}]
        segs = []
        jump_count = 0
        prev_r = None
        for r in ordered:
            a, b = runs[r]
            if include_geometry:
                segs.append([round(a[0], 2), round(a[1], 2), round(b[0], 2), round(b[1], 2), "h"])
            if prev_r is not None:
                pa, pb = runs[prev_r]
                # connect nearest endpoints between the two row runs (the turn)
                cands = [(pa, a), (pa, b), (pb, a), (pb, b)]
                u, v = min(cands, key=lambda uv: _dist(uv[0], uv[1]))
                if include_geometry and _dist(u, v) <= MAX_JUMP_LEN:
                    segs.append([round(u[0], 2), round(u[1], 2), round(v[0], 2), round(v[1], 2), "jump"])
                jump_count += 1
                events.append({"type": "exit_row", "row": _row_id(_south_row(prev_r, n_rows)), "physical_row": _south_row(prev_r, n_rows),
                               "between_panels": panel_pair_at(u, panel_rows, prev_r)["between_panels"]})
                events.append({"type": "enter_row", "row": _row_id(_south_row(r, n_rows)), "physical_row": _south_row(r, n_rows),
                               "between_panels": panel_pair_at(v, panel_rows, r)["between_panels"]})
            prev_r = r
        events.append({"type": "end", "row": _row_id(_south_row(er, n_rows)), "physical_row": _south_row(er, n_rows),
                       "between_panels": panel_pair_at(end_pt, panel_rows, er)["between_panels"]})

        rows_cov = []
        for r in sorted(set(comp_rows)):
            cnt = sum(1 for i in comp if prow[i] == r)
            rows_cov.append({"physical_row": _south_row(r, n_rows), "panel_count": cnt})

        entry: dict[str, Any] = {
            "string": None,
            "ribbon_idx": idx,
            "start_xy": [round(start_pt[0], 2), round(start_pt[1], 2)],
            "end_xy": [round(end_pt[0], 2), round(end_pt[1], 2)],
            "_start": start_pt,
            "events": events,
            "rows": rows_cov,
            "total_panels": len(comp),
            "optimizer_count": round(len(comp) / 2),
            "jump_count": jump_count,
        }
        if include_geometry:
            entry["segments"] = segs
        strings.append(entry)

    if labels_e41 and strings:
        S = np.array([s["_start"] for s in strings], dtype=float)
        L = np.array([(l["x"], l["y"]) for l in labels_e41], dtype=float)
        D = np.sqrt(((S[:, None, :] - L[None, :, :]) ** 2).sum(-1))
        from scipy.optimize import linear_sum_assignment
        ri, ci = linear_sum_assignment(D)
        for i, j in zip(ri, ci):
            strings[i]["string"] = labels_e41[j]["text"]

    for s in strings:
        s.pop("_start", None)

    return {
        "strings": strings,
        "piers": [],
        "stats": {
            "status": "ok",
            "method": "panels_plan_color_pairing",
            "strings": len(strings),
            "labeled": sum(1 for s in strings if s.get("string")),
            "multi_row": sum(1 for s in strings if s["jump_count"] >= 1),
            "greens": len(greens), "reds": len(reds), "panels": len(panels),
        },
    }
