"""Seed sample site details and string rows into the database."""

from pathlib import Path
import re
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import settings
from database import get_connection, init_db


SITE_DETAILS = {
    "site_code": "QUN_E_10",
    "site_name": "Qunitra-FPV",
    "layout_name": "QUN_E_10_Color Map",
    "source_document": "Qun_E_10_Color Map_revE1.pdf",
    "country": "ISRAEL",
    "region": "NORTH",
    "latitude": 33.13062,
    "longitude": 35.81224,
    "plant_capacity_mw": 11.8584,
    "module_type": "JKM615-620N66-HL4M-BDV",
    "module_count": 19438,
    "notes": "Sample site extracted from color map PDF.",
}


def load_string_codes(file_path: Path) -> list[str]:
    pattern = re.compile(r"^S\.(\d+)\.(\d+)\.(\d+)$")
    codes: list[str] = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        code = line.strip()
        if not code or code.startswith("Total "):
            continue
        if pattern.fullmatch(code):
            codes.append(code)
    return codes


def sqlite_upsert_site(cur) -> int:
    cur.execute(
        """
        INSERT INTO site_details (
            site_code, site_name, layout_name, source_document, country, region,
            latitude, longitude, plant_capacity_mw, module_type, module_count, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(site_code) DO UPDATE SET
            site_name = excluded.site_name,
            layout_name = excluded.layout_name,
            source_document = excluded.source_document,
            country = excluded.country,
            region = excluded.region,
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            plant_capacity_mw = excluded.plant_capacity_mw,
            module_type = excluded.module_type,
            module_count = excluded.module_count,
            notes = excluded.notes
        """,
        tuple(SITE_DETAILS.values()),
    )
    cur.execute("SELECT id FROM site_details WHERE site_code = ?", (SITE_DETAILS["site_code"],))
    return int(cur.fetchone()[0])


def postgres_upsert_site(cur) -> int:
    cur.execute(
        """
        INSERT INTO site_details (
            site_code, site_name, layout_name, source_document, country, region,
            latitude, longitude, plant_capacity_mw, module_type, module_count, notes
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT(site_code) DO UPDATE SET
            site_name = EXCLUDED.site_name,
            layout_name = EXCLUDED.layout_name,
            source_document = EXCLUDED.source_document,
            country = EXCLUDED.country,
            region = EXCLUDED.region,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            plant_capacity_mw = EXCLUDED.plant_capacity_mw,
            module_type = EXCLUDED.module_type,
            module_count = EXCLUDED.module_count,
            notes = EXCLUDED.notes
        RETURNING id
        """,
        tuple(SITE_DETAILS.values()),
    )
    return int(cur.fetchone()[0])


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    strings_file = project_root / "solar_string_list_formatted.txt"
    if not strings_file.exists():
        raise FileNotFoundError(f"Missing string list file: {strings_file}")

    string_codes = load_string_codes(strings_file)
    init_db()
    conn = get_connection()
    is_sqlite = settings.database_url.strip().lower().startswith("sqlite")
    placeholder = "?" if is_sqlite else "%s"

    try:
        with conn.cursor() as cur:
            site_id = sqlite_upsert_site(cur) if is_sqlite else postgres_upsert_site(cur)
            cur.execute(
                f"DELETE FROM site_strings WHERE site_id = {placeholder}",
                (site_id,),
            )

            insert_sql = (
                "INSERT INTO site_strings (site_id, string_code, section_no, block_no, string_no) "
                f"VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})"
            )

            for code in string_codes:
                section_no, block_no, string_no = map(int, code.split(".")[1:])
                cur.execute(
                    insert_sql,
                    (site_id, code, section_no, block_no, string_no),
                )
        conn.commit()
        print(f"Seeded site {SITE_DETAILS['site_code']} with {len(string_codes)} strings")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
