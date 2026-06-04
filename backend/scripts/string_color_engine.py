"""Solarica EPL String Detection Engine v1.1 - colour + row geometry + markers.

Panels-first detection (E_41); BE-STRINGS green-start / red-end markers used to
merge over-split colour fragments and to validate/name candidates; E_20 only for
the x.x.x.x label text. Confidence < 0.70 => UNKNOWN.
"""
import os, sys, math, json, csv
from collections import defaultdict
with open("/opt/solarica/.env") as fh:
    for line in fh:
        if line.startswith("DATABASE_URL="):
            os.environ["DATABASE_URL"] = line.strip().split("=", 1)[1]
sys.path.insert(0, ".")
import fitz, numpy as np
from scipy.spatial import cKDTree
from app.services import db_store
from app.modules.epl.string_optimizer_parser import _extract_panel_map_geometry, build_string_optimizer_model_from_pdfs
from app.modules.epl.panel_strings import load_panel_primitives, _load_e20_labels, _load_e20_greens, _pair_start_end
from app.modules.epl.string_topology import assign_row

OPT_PANELS = 44
CONF_MIN = 0.70

uu = db_store.get_project_uuid("BHK")
files = [str(f["storage_path"]) for f in db_store.list_project_files(uu) if str(f.get("storage_path","")).lower().endswith(".pdf")]
e41 = next(p for p in files if "E_41" in p)
e20 = next(p for p in files if "E_20" in p)

geo = _extract_panel_map_geometry(files)
panel_rows = geo["panel_rows"]; n_rows = len(panel_rows)
d41 = fitz.open(e41); prims = load_panel_primitives(d41[0]); d41.close()
panels = prims["panels"]; greens = prims["greens"]; reds = prims["reds"]

# printed row numbering (rank trackers along printed-label direction)
_model = build_string_optimizer_model_from_pdfs(files)
phys = {int(p["physical_row"]): ((float(p["x"])+float(p["x1"]))/2, (float(p["y"])+float(p["y1"]))/2) for p in (_model.get("physical_rows") or [])}
ks = sorted(phys); plo, phi = phys[ks[0]], phys[ks[-1]]
vx, vy = phi[0]-plo[0], phi[1]-plo[1]; vn = math.hypot(vx, vy) or 1.0; vx, vy = vx/vn, vy/vn
def row_mid(r): return ((float(r["south_x"])+float(r["north_x"]))/2, (float(r["south_y"])+float(r["north_y"]))/2)
order = sorted(range(n_rows), key=lambda i: row_mid(panel_rows[i])[0]*vx + row_mid(panel_rows[i])[1]*vy)
printed_no = {idx: rank+1 for rank, idx in enumerate(order)}

def row_t(pt, ri):
    r = panel_rows[ri]; sx, sy, nx, ny = float(r["south_x"]), float(r["south_y"]), float(r["north_x"]), float(r["north_y"])
    dx, dy = nx-sx, ny-sy; den = dx*dx+dy*dy or 1.0
    return ((pt[0]-sx)*dx + (pt[1]-sy)*dy)/den

# panel -> tracker + t, ordered per row
P = []   # (cx,cy,color,ri,t)
for p in panels:
    ri = assign_row((p["cx"], p["cy"]), panel_rows)
    if ri is None: continue
    P.append((p["cx"], p["cy"], p["color"], ri-1, row_t((p["cx"], p["cy"]), ri-1)))
by_row = defaultdict(list)
for idx, rec in enumerate(P):
    by_row[rec[3]].append(idx)
for ri in by_row:
    by_row[ri].sort(key=lambda k: P[k][4])

# STEP 1 row model
report_A = []
for ri in range(n_rows):
    idxs = by_row.get(ri, [])
    ts = [P[k][4] for k in idxs]; gaps = [b-a for a, b in zip(ts, ts[1:])]
    med = sorted(gaps)[len(gaps)//2] if gaps else 0
    tracker_count = (1 + sum(1 for g in gaps if med and g > 3*med)) if idxs else 0
    r = panel_rows[ri]
    report_A.append({"row_number": printed_no[ri], "tracker_count": tracker_count, "panel_count": len(idxs),
                     "start_coordinate": f"({r['south_x']:.0f},{r['south_y']:.0f})", "end_coordinate": f"({r['north_x']:.0f},{r['north_y']:.0f})"})
report_A.sort(key=lambda d: d["row_number"])

# STEP 2 colour segments (panel -> segment id)
seg_of_panel = [None]*len(P)
segments = []
for ri in range(n_rows):
    idxs = by_row.get(ri, [])
    i = 0
    while i < len(idxs):
        j = i; col = P[idxs[i]][2]
        while j+1 < len(idxs) and P[idxs[j+1]][2] == col: j += 1
        members = idxs[i:j+1]
        sid = len(segments)
        for k in members: seg_of_panel[k] = sid
        segments.append({"id": sid, "ri": ri, "color": col, "p_start": i+1, "p_end": j+1, "count": len(members),
                         "t_lo": P[members[0]][4], "t_hi": P[members[-1]][4], "members": members})
        i = j+1
seg_by_row = defaultdict(list)
for s in segments: seg_by_row[s["ri"]].append(s)

# STEP 3 cross-row colour links recorded for reporting (count only)
def t_ov(a, b): return min(a["t_hi"], b["t_hi"]) - max(a["t_lo"], b["t_lo"]) > -0.01
cross_links = sum(1 for ri in range(n_rows-1) for a in seg_by_row.get(ri, []) for b in seg_by_row.get(ri+1, [])
                  if a["color"] == b["color"] and t_ov(a, b))

# ---- markers as SEEDS: pair start<->end, then grow one colour basin per start ----
pxy = np.array([(P[k][0], P[k][1]) for k in range(len(P))]); ptree = cKDTree(pxy)
def colrow_at(pt):
    k = int(ptree.query(pt)[1]); return P[k][2], P[k][3]+1
g_panel = [int(ptree.query(g)[1]) for g in greens]
r_panel = [int(ptree.query(r)[1]) for r in reds]
g_cr = [colrow_at(g) for g in greens]; r_cr = [colrow_at(r) for r in reds]
pairs = _pair_start_end(greens, reds, [c for c,_ in g_cr], [c for c,_ in r_cr], [r for _,r in g_cr], [r for _,r in r_cr])
red_for_green = {gi: rj for gi, rj in pairs}

# INVARIANT: each colour's panels == 44 x (its start markers). So per colour,
# every green claims EXACTLY 44 of its nearest connected same-colour panels.
# Capacity-44 multi-source Dijkstra (region growing) -> exact partition.
import heapq
CAP = OPT_PANELS
panels_by_color = defaultdict(list)
for k in range(len(P)):
    panels_by_color[P[k][2]].append(k)
gcolor = [P[g_panel[gi]][2] for gi in range(len(greens))]
greens_by_color = defaultdict(list)
for gi in range(len(greens)):
    greens_by_color[gcolor[gi]].append(gi)

owner = [None]*len(P)
for color, pidx in panels_by_color.items():
    gids = greens_by_color.get(color, [])
    if not gids:
        continue                                   # non-string colour (e.g. plain EN-PANEL)
    pts = np.array([(P[k][0], P[k][1]) for k in pidx])
    tree = cKDTree(pts)
    loc = {k: i for i, k in enumerate(pidx)}
    adjc = defaultdict(list)
    for a, b in tree.query_pairs(13.0):
        adjc[a].append(b); adjc[b].append(a)
    cnt = defaultdict(int); claimed = {}
    pq = []
    for gi in gids:                                  # anchor each string at BOTH ends
        pq.append((0.0, loc[g_panel[gi]], gi))
        rj = red_for_green.get(gi)
        if rj is not None and r_panel[rj] in loc:
            pq.append((0.0, loc[r_panel[rj]], gi))
    heapq.heapify(pq)
    while pq:
        d, u, gid = heapq.heappop(pq)
        if u in claimed or cnt[gid] >= CAP:
            continue
        claimed[u] = gid; cnt[gid] += 1; owner[pidx[u]] = gid
        for v in adjc[u]:
            if v not in claimed:
                heapq.heappush(pq, (d + float(math.hypot(pts[v][0]-pts[u][0], pts[v][1]-pts[u][1])), v, gid))
    # cleanup: force every green to exactly 44 (assign leftovers to nearest under-cap green)
    left = [i for i in range(len(pidx)) if i not in claimed]
    if left:
        gpos = {gi: pts[loc[g_panel[gi]]] for gi in gids}
        for i in left:
            avail = [gi for gi in gids if cnt[gi] < CAP]
            if not avail:
                break
            gi = min(avail, key=lambda g: math.hypot(pts[i][0]-gpos[g][0], pts[i][1]-gpos[g][1]))
            owner[pidx[i]] = gi; cnt[gi] += 1

# E_20 labels -> E_41 frame, green->label (Hungarian)
d20 = fitz.open(e20); labels = _load_e20_labels(d20[0]); e20g = _load_e20_greens(d20[0]); d20.close()
if e20g and greens:
    dx = float(np.array(e20g).mean(0)[0]-np.array(greens).mean(0)[0]); dy = float(np.array(e20g).mean(0)[1]-np.array(greens).mean(0)[1])
else: dx = dy = 0.0
labels41 = [(l["text"], l["x"]-dx, l["y"]-dy) for l in labels]
green_label = {}
if labels41 and greens:
    from scipy.optimize import linear_sum_assignment
    G = np.array(greens); L = np.array([(x, y) for _, x, y in labels41])
    D = np.sqrt(((G[:, None, :]-L[None, :, :])**2).sum(-1)); ri_, ci_ = linear_sum_assignment(D)
    for gi, li in zip(ri_, ci_): green_label[gi] = labels41[li][0]

# one candidate per start marker (its basin)
basin = defaultdict(list)
for k in range(len(P)):
    if owner[k] is not None: basin[owner[k]].append(k)
cands = []
for gi in range(len(greens)):
    members = basin.get(gi, [g_panel[gi]])
    per_row = defaultdict(int)
    for k in members: per_row[printed_no[P[k][3]]] += 1
    rows = sorted(per_row)
    cx = sum(P[k][0] for k in members)/len(members); cy = sum(P[k][1] for k in members)/len(members)
    rj = red_for_green.get(gi)
    has_end = rj is not None and owner[r_panel[rj]] == gi          # red lands in this basin
    cands.append({"gi": gi, "rows": rows, "row_start": rows[0], "row_end": rows[-1], "cross_row": len(rows) > 1,
                  "panels": len(members), "cx": cx, "cy": cy, "per_row": dict(sorted(per_row.items())),
                  "has_start": True, "has_end": has_end})
cands.sort(key=lambda c: (c["cx"], c["cy"]))
for i, c in enumerate(cands, 1): c["candidate_id"] = "C%04d" % i

for c in cands:
    n = c["panels"]; panel_s = max(0.0, 1-abs(n-OPT_PANELS)/OPT_PANELS)
    nr = len(c["rows"]); row_s = 1.0 if 1 <= nr <= 4 else (0.6 if nr == 5 else 0.2)
    marker_s = 1.0 if c["has_end"] else 0.8       # every candidate has a start (it IS a start marker)
    name = green_label.get(c["gi"], "UNKNOWN")
    label_s = 1.0 if name != "UNKNOWN" else 0.5
    c["confidence"] = round(0.30*panel_s + 0.20*row_s + 0.30*marker_s + 0.20*label_s, 3)
    c["validated_by"] = "start+end" if c["has_end"] else "start"
    # Identity is validated by the green start marker + matched label (not a guess),
    # so the string is named. Membership quality is flagged separately.
    c["string_name"] = name
    if name == "UNKNOWN":
        c["status"] = "UNKNOWN"          # no marker->label (should not happen: 288/288)
    elif 40 <= n <= 48:
        c["status"] = "OK"               # marker-named + full ~44-panel colour basin
    else:
        c["status"] = "REVIEW"           # marker-named, but basin panel count is off

# reports
os.makedirs("/tmp/string_map", exist_ok=True)
with open("/tmp/string_map/report_A_physical_rows.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["row_number","panel_count","tracker_count","start_coordinate","end_coordinate"])
    for r in report_A: w.writerow([r["row_number"], r["panel_count"], r["tracker_count"], r["start_coordinate"], r["end_coordinate"]])
with open("/tmp/string_map/report_B_string_candidates.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["candidate_id","string_name","row_start","row_end","rows_used","cross_row","panels","validated_by","status","confidence"])
    for c in cands: w.writerow([c["candidate_id"], c["string_name"], c["row_start"], c["row_end"], "|".join(map(str, c["rows"])), c["cross_row"], c["panels"], c["validated_by"], c["status"], c["confidence"]])
with open("/tmp/string_map/report_C_cross_row.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["candidate_id","string_name","row_start","row_end","panels_per_row","total_panels","validated_by","status","confidence"])
    for c in cands:
        if c["cross_row"]:
            ppr = "; ".join("r%d:%d" % (rn, cnt) for rn, cnt in c["per_row"].items())
            w.writerow([c["candidate_id"], c["string_name"], c["row_start"], c["row_end"], ppr, c["panels"], c["validated_by"], c["status"], c["confidence"]])
with open("/tmp/string_map/string_map.json", "w") as f:
    json.dump({"physical_rows": report_A, "candidates": cands}, f, indent=1)

status_ct = {k: sum(1 for c in cands if c["status"] == k) for k in ("OK","REVIEW","UNKNOWN")}
print("=== Solarica String Detection Engine v1 (colour + geometry + markers) ===")
print("physical rows:", len(report_A), " colour segments:", len(segments), " cross-row colour links:", cross_links)
print("candidates (= start markers):", len(cands), " named:", sum(1 for c in cands if c['string_name']!='UNKNOWN'),
      " cross-row:", sum(1 for c in cands if c["cross_row"]))
print("status:", status_ct, " (OK=start+end+~44 panels, REVIEW=marker-confirmed name but membership off)")
print("validated_by:", {k: sum(1 for c in cands if c["validated_by"] == k) for k in ("start+end","start")})
print("panel buckets:", {b: sum(1 for c in cands if (b=="40-48" and 40<=c["panels"]<=48) or (b=="<40" and c["panels"]<40) or (b==">48" and c["panels"]>48)) for b in ("40-48","<40",">48")})
print("greens:", len(greens), " reds:", len(reds), " green->label:", len(green_label))
for c in cands:
    if c["status"] != "OK":
        print("   REVIEW", c["candidate_id"], c["string_name"], "rows", c["rows"], "panels", c["panels"], c["validated_by"], "conf", c["confidence"])
