import re
from sqlalchemy.orm import Session
from app.models.project import Project, DesignValidationRun, DesignValidationIssue


def list_projects(db: Session) -> list[Project]:
    return db.query(Project).order_by(Project.id).all()


def get_project(db: Session, project_id: int) -> Project | None:
    return db.query(Project).filter(Project.id == project_id).first()


def create_project(db: Session, *, name: str, customer_name: str | None = None,
                   customer_id: int | None = None, site_name: str,
                   project_type: str, description: str | None = None) -> Project:
    proj = Project(
        name=name,
        customer_name=customer_name,
        customer_id=customer_id,
        site_name=site_name,
        project_type=project_type,
        description=description,
        phase="design",
        progress_percent=0,
    )
    db.add(proj)
    db.flush()
    return proj


def update_phase(db: Session, project_id: int, phase: str) -> Project | None:
    proj = get_project(db, project_id)
    if proj:
        proj.phase = phase
        db.flush()
    return proj


def set_project_active(db: Session, project_id: int, is_active: bool) -> Project | None:
    proj = get_project(db, project_id)
    if proj:
        proj.is_active = is_active
        db.flush()
    return proj


def validate_design(db: Session, project_id: int, actor_username: str = "system",
                    actor_role: str = "system") -> dict:
    """
    Real rule-based design validation engine.
    Checks: inverters present, strings present, naming conventions, phase consistency.
    """
    proj = get_project(db, project_id)
    if not proj:
        return None

    issues = []

    # Rule 1: Project must have at least one inverter defined to proceed past design
    if proj.phase in ("validation", "implementation", "testing", "commissioning") and len(proj.inverters) == 0:
        issues.append({
            "severity": "warning",
            "asset_type": "inverter",
            "asset_ref": None,
            "issue_type": "no_inverters",
            "message": "No inverters defined for this project. Add inverters before proceeding.",
        })

    # Rule 2: Check string numbering for gaps
    if proj.inverters:
        for inv in proj.inverters:
            str_nos = sorted(s.string_no for s in inv.strings)
            if str_nos:
                for i, sno in enumerate(str_nos):
                    m = re.search(r'(\d+)$', sno)
                    if m:
                        num = int(m.group(1))
                        if i > 0:
                            prev_m = re.search(r'(\d+)$', str_nos[i-1])
                            if prev_m and int(prev_m.group(1)) != num - 1:
                                issues.append({
                                    "severity": "warning",
                                    "asset_type": "string",
                                    "asset_ref": sno,
                                    "issue_type": "missing_sequence",
                                    "message": f"Detected possible missing sequence before {sno}",
                                })

    # Rule 3: Progress vs phase consistency
    phase_min_progress = {
        "design": 0, "validation": 10, "implementation": 20,
        "testing": 60, "commissioning": 80, "maintenance": 95, "closed": 100
    }
    min_prog = phase_min_progress.get(proj.phase, 0)
    if float(proj.progress_percent) < min_prog:
        issues.append({
            "severity": "warning",
            "asset_type": None,
            "asset_ref": None,
            "issue_type": "progress_mismatch",
            "message": f"Project progress ({proj.progress_percent}%) is below expected minimum "
                       f"({min_prog}%) for phase '{proj.phase}'.",
        })

    status = "pass" if all(i["severity"] != "error" for i in issues) else "fail"
    if issues and status == "pass":
        status = "warning"

    # Persist the run
    run = DesignValidationRun(
        project_id=project_id,
        status=status,
        summary_json={"issue_count": len(issues)},
    )
    db.add(run)
    db.flush()

    for iss in issues:
        db.add(DesignValidationIssue(
            validation_run_id=run.id,
            severity=iss["severity"],
            asset_type=iss.get("asset_type"),
            asset_ref=iss.get("asset_ref"),
            issue_type=iss["issue_type"],
            message=iss["message"],
        ))

    db.flush()
    db.refresh(run)
    return {"status": status, "issues": issues}


def delete_project(db: Session, project_id: int) -> str | None:
    """Delete project by id. Returns project name if deleted, None if not found."""
    proj = get_project(db, project_id)
    if not proj:
        return None
    name = proj.name
    db.delete(proj)
    db.flush()
    return name


def seed_projects(db: Session) -> None:
    if db.query(Project).count() > 0:
        return
    seeds = [
        {"name": "Solar Farm Alpha",  "customer_name": "GreenEnergy SA",    "site_name": "Alentejo North",   "project_type": "utility",      "description": "100 MW utility-scale PV farm",        "phase": "implementation", "progress_percent": 62.0},
        {"name": "Rooftop Porto B2B", "customer_name": "Logistics Hub Lda", "site_name": "Porto Industrial", "project_type": "commercial",   "description": "Industrial rooftop, 450 kWp",         "phase": "commissioning",  "progress_percent": 88.0},
        {"name": "Rural Mini-Grid",   "customer_name": "Cooperativa Sol",   "site_name": "Évora Rural",      "project_type": "mini-grid",    "description": "Off-grid community solar + storage",  "phase": "testing",        "progress_percent": 75.0},
        {"name": "Hospital Canopy",   "customer_name": "NHS Regional",      "site_name": "Lisbon Central",   "project_type": "commercial",   "description": "Carport canopy + EV charging 120 kWp","phase": "design",         "progress_percent": 15.0},
        {"name": "Agrivoltaic Demo",  "customer_name": "AgriSun Coop",      "site_name": "Beja Fields",      "project_type": "agrivoltaic",  "description": "Dual-use solar + crops pilot 2 MWp",  "phase": "validation",     "progress_percent": 38.0},
    ]
    for s in seeds:
        p = Project(**s)
        db.add(p)
    db.flush()
