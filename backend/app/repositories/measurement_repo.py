from sqlalchemy.orm import Session
from app.models.measurement import Measurement


def list_measurements(db: Session, project_id: int | None = None, string_label: str | None = None, limit: int = 200, offset: int = 0) -> list[Measurement]:
    q = db.query(Measurement)
    if project_id is not None:
        q = q.filter(Measurement.project_id == project_id)
    if string_label:
        q = q.filter(Measurement.string_label.ilike(f"%{string_label}%"))
    return q.order_by(Measurement.id.desc()).offset(offset).limit(limit).all()


def get_measurement(db: Session, measurement_id: int) -> Measurement | None:
    return db.query(Measurement).filter(Measurement.id == measurement_id).first()


def create_measurement(db: Session, *, source_file_name: str, payload_json: dict,
                        project_id: int | None = None) -> Measurement:
    m = Measurement(
        source_file_name=source_file_name,
        payload_json=payload_json,
        project_id=project_id,
        site_label=payload_json.get("site_label"),
        string_label=payload_json.get("string_label"),
        device_serial=payload_json.get("device_serial"),
        module_part_number=payload_json.get("module_part_number"),
    )
    db.add(m)
    db.flush()
    return m


def auto_link_to_project_strings(db: Session, project_id: int) -> int:
    """
    Match unlinked measurements' string_label to actual String entities by string_no.
    Returns count of measurements linked.
    """
    from app.models.project import String as ProjectString
    linked = 0
    unlinked = (db.query(Measurement)
                .filter(Measurement.project_id == project_id, Measurement.string_id == None, Measurement.string_label != None)
                .all())
    for m in unlinked:
        match = (db.query(ProjectString)
                 .filter(ProjectString.project_id == project_id,
                         ProjectString.string_no == m.string_label)
                 .first())
        if match:
            m.string_id = match.id
            linked += 1
    db.flush()
    return linked
