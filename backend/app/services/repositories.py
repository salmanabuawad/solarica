from app.db import get_conn
import json

def upsert_project(project_code, project_name):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                '''
                INSERT INTO projects (code, name)
                VALUES (%s, %s)
                ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                ''',
                (project_code, project_name),
            )
            pid = cur.fetchone()["id"]
        conn.commit()
    return pid

def clear_project(project_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            for table in ["drawing_bundles", "zoom_targets", "piers", "trackers", "blocks"]:
                cur.execute(f"DELETE FROM {table} WHERE project_id = %s", (project_id,))
        conn.commit()

def save_snapshot(project_id, blocks, trackers, piers, zoom_targets, drawing_bundles):
    with get_conn() as conn:
        with conn.cursor() as cur:
            for b in blocks:
                cur.execute(
                    '''
                    INSERT INTO blocks (project_id, block_code, label, color, original_block_id, block_pier_plan_sheet, bbox_json, centroid_json, polygon_json)
                    VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)
                    ''',
                    (project_id, b["block_code"], b["label"], b["color"], b["original_block_id"], b["block_pier_plan_sheet"],
                     json.dumps(b["bbox"]), json.dumps(b["centroid"]), json.dumps(b["polygon"]))
                )
            for t in trackers:
                cur.execute(
                    '''
                    INSERT INTO trackers (project_id, tracker_code, block_code, tracker_type_code, tracker_sheet, orientation, pier_count, bbox_json, assignment_method, assignment_confidence)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
                    ''',
                    (project_id, t["tracker_code"], t.get("block_code"), t.get("tracker_type_code"), t.get("tracker_sheet"),
                     t.get("orientation"), t.get("pier_count"), json.dumps(t["bbox"]), t.get("assignment_method"), t.get("assignment_confidence"))
                )
            for p in piers:
                cur.execute(
                    '''
                    INSERT INTO piers (project_id, pier_code, tracker_code, block_code, row_pier_count, tracker_type_code, tracker_sheet, structure_code, structure_sheet, pier_type, pier_type_sheet, slope_band, slope_sheet, x, y, bbox_json, assignment_method)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                    ''',
                    (project_id, p["pier_code"], p["tracker_code"], p.get("block_code"), p.get("row_pier_count"),
                     p.get("tracker_type_code"), p.get("tracker_sheet"), p.get("structure_code"), p.get("structure_sheet"),
                     p.get("pier_type"), p.get("pier_type_sheet"), p.get("slope_band"), p.get("slope_sheet"),
                     p.get("x"), p.get("y"), json.dumps(p.get("bbox", {})), p.get("assignment_method"))
                )
            for object_code, z in zoom_targets.items():
                for target_kind, payload in z.items():
                    if not payload:
                        continue
                    cur.execute(
                        '''
                        INSERT INTO zoom_targets (project_id, object_type, object_code, target_kind, sheet_id, bbox_json, padding, preferred_zoom, overlay_ids_json)
                        VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb)
                        ''',
                        (project_id, payload["object_type"], object_code, target_kind, payload.get("sheet_id"),
                         json.dumps(payload.get("bbox", {})), payload.get("padding"), payload.get("preferred_zoom"),
                         json.dumps(payload.get("overlay_ids", [])))
                    )
            for pier_code, bndl in drawing_bundles.items():
                cur.execute(
                    '''
                    INSERT INTO drawing_bundles (project_id, pier_code, block_pier_plan_sheet, tracker_typical_sheet, pier_tolerances_sheet, slope_detail_sheet, crops_json, highlights_json)
                    VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)
                    ''',
                    (project_id, pier_code,
                     (bndl.get("block_pier_plan") or {}).get("sheet_no"),
                     (bndl.get("tracker_typical") or {}).get("sheet_no"),
                     (bndl.get("pier_tolerances") or {}).get("sheet_no"),
                     (bndl.get("slope_detail") or {}).get("sheet_no"),
                     json.dumps(bndl.get("crops", {})),
                     json.dumps(bndl.get("highlights", {})))
                )
        conn.commit()
