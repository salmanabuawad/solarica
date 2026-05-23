"""Debug overlays for visual verification of the base-map extraction.
(The deliverable is the structured GIS model; these are QA artifacts.)"""
import glob
import json
import os

import fitz

OUT = "/tmp/bhk_base_map"
model = json.load(open(os.path.join(OUT, "base_map_model.json")))
rows = model["rows"]
e41 = sorted(glob.glob("/opt/wavelync-ftp/uploads/BHK_E_41*.pdf"))[0]
SCALE = 0.85


def render(draw_fn, name):
    doc = fitz.open(e41)
    page = doc[0]
    shape = page.new_shape()
    draw_fn(shape)
    shape.commit()
    pix = page.get_pixmap(matrix=fitz.Matrix(SCALE, SCALE))
    pix.save(os.path.join(OUT, name))
    doc.close()
    print("wrote", name, pix.width, "x", pix.height)


def rows_overlay(shape):
    for r in rows:
        s, n = r["south_point"], r["north_point"]
        shape.draw_line(fitz.Point(*s), fitz.Point(*n))
        shape.finish(color=(0, 0.3, 1), width=2.5)
        shape.draw_circle(fitz.Point(*s), 6)  # south end marker
        shape.finish(color=(0, 0.6, 0), fill=(0, 0.6, 0))


def piers_overlay(shape):
    for r in rows:
        for p in r["piers"]:
            shape.draw_circle(fitz.Point(p["x"], p["y"]), 2.2)
            shape.finish(color=(0.85, 0, 0), fill=(0.85, 0, 0))


def panels_overlay(shape):
    for r in rows:
        for p in r["panels"]:
            shape.draw_circle(fitz.Point(p["cx"], p["cy"]), 1.4)
            shape.finish(color=(0, 0.55, 0), fill=(0, 0.55, 0))


render(rows_overlay, "debug_overlay_rows.png")
render(piers_overlay, "debug_overlay_piers.png")
render(panels_overlay, "debug_overlay_panels.png")
print("done")
