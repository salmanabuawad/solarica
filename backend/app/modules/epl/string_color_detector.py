"""Solarica EPL String Detection Engine - colour partition (panels plan E_41).

Deterministic, exact string map driven by three site invariants:
  * every string is exactly OPT_PANELS (44) panels,
  * all of a string's panels share one EN-PANEL colour,
  * each string has one green-triangle start + one red-circle end.

Per colour the panels are a clean partition (panel_count == 44 x start_markers),
so each start marker claims exactly its 44 nearest connected same-colour panels
via a capacity-44 region-grow seeded from BOTH the green and the red. Result:
one string per start marker, 44 panels each, anchored start->end.

x.x.x.x labels live only on E_20; they are translated into the panels-plan
frame by a rigid green-centroid offset and matched 1:1 to the start markers.

Output matches ``string_topology.reconstruct_topology`` so the model, map and
grid render unchanged.
"""
from __future__ import annotations

import heapq
import math
from collections import defaultdict
from typing import Any

from .panel_strings import load_panel_primitives, _pair_start_end, _load_e20_labels, _load_e20_greens, _row_t
from .string_topology import assign_row, _south_row, _row_id, panel_pair_at, _dist

OPT_PANELS = 44
NEIGHBOR_R = 13.0          # connect same-colour panels within this radius
MAX_JUMP_LEN = 70.0        # never draw a jump longer than a few row pitches


def _partition_panels(panels, greens, reds, panel_rows):
    """Assign every coloured panel to a start marker (capacity 44 per start).

    Returns: owner[panel_idx] -> green index (or None), g_panel/r_panel (each
    marker's nearest panel idx), pairs (green idx -> red idx).
    """
    import numpy as np
    from scipy.spatial import cKDTree

    pxy = np.array([(p["cx"], p["cy"]) for p in panels], dtype=float)
    pcolor = [p["color"] for p in panels]
    prow = [assign_row((p["cx"], p["cy"]), panel_rows) for p in panels]
    ptree = cKDTree(pxy)

    g_panel = [int(ptree.query(g)[1]) for g in greens]
    r_panel = [int(ptree.query(r)[1]) for r in reds]
    g_cr = [(pcolor[g_panel[i]], prow[g_panel[i]]) for i in range(len(greens))]
    r_cr = [(pcolor[r_panel[j]], prow[r_panel[j]]) for j in range(len(reds))]
    pairs = _pair_start_end(greens, reds, [c for c, _ in g_cr], [c for c, _ in r_cr],
                            [r for _, r in g_cr], [r for _, r in r_cr])
    red_for_green = {gi: rj for gi, rj in pairs}

    panels_by_color = defaultdict(list)
    for k in range(len(panels)):
        panels_by_color[pcolor[k]].append(k)
    gcolor = [pcolor[g_panel[gi]] for gi in range(len(greens))]
    greens_by_color = defaultdict(list)
    for gi in range(len(greens)):
        greens_by_color[gcolor[gi]].append(gi)

    owner = [None] * len(panels)
    for color, pidx in panels_by_color.items():
        gids = greens_by_color.get(color, [])
        if not gids:
            continue                                   # non-string colour (legend/typical)
        pts = np.array([(panels[k]["cx"], panels[k]["cy"]) for k in pidx])
        tree = cKDTree(pts)
        loc = {k: i for i, k in enumerate(pidx)}
        adjc = defaultdict(list)
        for a, b in tree.query_pairs(NEIGHBOR_R):
            adjc[a].append(b); adjc[b].append(a)
        cnt = defaultdict(int); claimed = {}
        pq = []
        for gi in gids:
            pq.append((0.0, loc[g_panel[gi]], gi))
            rj = red_for_green.get(gi)
            if rj is not None and r_panel[rj] in loc:
                pq.append((0.0, loc[r_panel[rj]], gi))
        heapq.heapify(pq)
        while pq:
            d, u, gid = heapq.heappop(pq)
            if u in claimed or cnt[gid] >= OPT_PANELS:
                continue
            claimed[u] = gid; cnt[gid] += 1; owner[pidx[u]] = gid
            for v in adjc[u]:
                if v not in claimed:
                    heapq.heappush(pq, (d + float(math.hypot(pts[v][0]-pts[u][0], pts[v][1]-pts[u][1])), v, gid))
        # cleanup: force every start to exactly 44 (leftovers -> nearest under-cap start)
        left = [i for i in range(len(pidx)) if i not in claimed]
        if left:
            gpos = {gi: pts[loc[g_panel[gi]]] for gi in gids}
            for i in left:
                avail = [gi for gi in gids if cnt[gi] < OPT_PANELS]
                if not avail:
                    break
                gi = min(avail, key=lambda g: math.hypot(pts[i][0]-gpos[g][0], pts[i][1]-gpos[g][1]))
                owner[pidx[i]] = gi; cnt[gi] += 1
    return owner, g_panel, r_panel, pairs


def detect_strings_topology(e41_page, panel_rows, e20_page=None, include_geometry: bool = True) -> dict[str, Any]:
    import numpy as np

    prims = load_panel_primitives(e41_page)
    panels, greens, reds = prims["panels"], prims["greens"], prims["reds"]
    n_rows = len(panel_rows)
    if not panels or not greens:
        return {"strings": [], "piers": [], "stats": {"status": "no_panel_primitives",
                "greens": len(greens), "reds": len(reds), "panels": len(panels)}}

    owner, g_panel, r_panel, pairs = _partition_panels(panels, greens, reds, panel_rows)
    red_for_green = {gi: rj for gi, rj in pairs}

    # panel coords + (row, t) cache
    prow = [assign_row((p["cx"], p["cy"]), panel_rows) for p in panels]
    basin = defaultdict(list)
    for k in range(len(panels)):
        if owner[k] is not None:
            basin[owner[k]].append(k)

    # labels: E_20 only -> translate into panels-plan frame, match 1:1 to starts
    green_label = {}
    if e20_page is not None:
        labels = _load_e20_labels(e20_page); e20g = _load_e20_greens(e20_page)
        if labels and e20g and greens:
            dx = float(np.array(e20g).mean(0)[0]-np.array(greens).mean(0)[0])
            dy = float(np.array(e20g).mean(0)[1]-np.array(greens).mean(0)[1])
            L = np.array([(l["x"]-dx, l["y"]-dy) for l in labels]); G = np.array(greens, dtype=float)
            from scipy.optimize import linear_sum_assignment
            D = np.sqrt(((G[:, None, :]-L[None, :, :])**2).sum(-1))
            ri, ci = linear_sum_assignment(D)
            for gi, li in zip(ri, ci):
                green_label[gi] = labels[li]["text"]

    strings: list[dict[str, Any]] = []
    for gi in range(len(greens)):
        members = basin.get(gi) or [g_panel[gi]]
        start_pt = greens[gi]
        rj = red_for_green.get(gi)
        end_pt = reds[rj] if rj is not None else start_pt
        sr = prow[g_panel[gi]]
        er = prow[r_panel[rj]] if rj is not None else sr

        # per-row runs from the exact basin (sorted along the tracker)
        prow_pts = defaultdict(list)
        for k in members:
            r = prow[k]
            if r is not None:
                prow_pts[r].append((_row_t((panels[k]["cx"], panels[k]["cy"]), panel_rows, r),
                                    panels[k]["cx"], panels[k]["cy"]))
        occupied = sorted(prow_pts)
        if sr in prow_pts and abs((occupied[0] if occupied else sr) - sr) > abs((occupied[-1] if occupied else sr) - sr):
            occupied = occupied[::-1]
        runs = {}
        rows_cov = []
        for r in sorted(prow_pts):
            pts = sorted(prow_pts[r])
            runs[r] = ((pts[0][1], pts[0][2]), (pts[-1][1], pts[-1][2]))
            rows_cov.append({"physical_row": _south_row(r, n_rows), "panel_count": len(pts)})
        if not occupied:
            occupied = [sr]; runs[sr] = (start_pt, start_pt)

        events = [{"type": "start", "row": _row_id(_south_row(sr, n_rows)), "physical_row": _south_row(sr, n_rows),
                   "between_panels": panel_pair_at(start_pt, panel_rows, sr)["between_panels"]}]
        segs = []
        jump_count = 0
        prev_r = None
        for r in occupied:
            a, b = runs[r]
            if include_geometry:
                segs.append([round(a[0], 2), round(a[1], 2), round(b[0], 2), round(b[1], 2), "h"])
            if prev_r is not None:
                pa, pb = runs[prev_r]
                u, v = min([(pa, a), (pa, b), (pb, a), (pb, b)], key=lambda uv: _dist(uv[0], uv[1]))
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

        entry = {
            "string": green_label.get(gi),
            "ribbon_idx": gi,
            "start_xy": [round(start_pt[0], 2), round(start_pt[1], 2)],
            "end_xy": [round(end_pt[0], 2), round(end_pt[1], 2)],
            "events": events,
            "rows": rows_cov,
            "total_panels": len(members),
            "optimizer_count": round(len(members) / 2),
            "jump_count": jump_count,
        }
        if include_geometry:
            entry["segments"] = segs
        strings.append(entry)

    exact = sum(1 for s in strings if s["total_panels"] == OPT_PANELS)
    return {
        "strings": strings,
        "piers": [],
        "stats": {
            "status": "ok",
            "method": "colour_partition_capacity44",
            "strings": len(strings),
            "labeled": sum(1 for s in strings if s.get("string")),
            "exact_44": exact,
            "cross_row": sum(1 for s in strings if s["jump_count"] >= 1),
            "greens": len(greens), "reds": len(reds), "panels": len(panels),
        },
    }
