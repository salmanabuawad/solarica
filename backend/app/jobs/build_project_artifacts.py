import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import PROJECTS_ROOT
from app.parser import run_pipeline
from app.site_profiles import load_site_profile
from app.services.repositories import upsert_project, clear_project, save_snapshot
from app.services.project_artifacts import write_manifest

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--construction-pdf", required=True)
    parser.add_argument("--ramming-pdf", required=True)
    parser.add_argument("--overlay-image", required=True, help="Image or PDF used to derive block regions")
    parser.add_argument("--site-profile", default="auto", help="Built-in profile name or 'auto'")
    parser.add_argument("--profile-config", help="Optional JSON file with per-site overrides")
    parser.add_argument("--save-db", action="store_true")
    args = parser.parse_args()

    out_dir = PROJECTS_ROOT / args.project_id
    out_dir.mkdir(parents=True, exist_ok=True)
    # Persist inputs so we can auto-rebuild JSON artifacts later if anything is missing.
    write_manifest(
        out_dir,
        project_id=args.project_id,
        construction_pdf=args.construction_pdf,
        ramming_pdf=args.ramming_pdf,
        overlay_image=args.overlay_image,
        site_profile=args.site_profile,
        profile_config=args.profile_config,
    )
    profile = load_site_profile(
        profile_name=args.site_profile,
        input_paths=[args.construction_pdf, args.ramming_pdf, args.overlay_image],
        config_path=args.profile_config,
    )
    result = run_pipeline(args.construction_pdf, args.ramming_pdf, args.overlay_image, str(out_dir), profile)

    if args.save_db:
        pid = upsert_project(args.project_id, args.project_id)
        clear_project(pid)
        save_snapshot(pid, result["blocks"], result["trackers"], result["piers"], result["zoom_targets"], result["drawing_bundles"])

    print(f"Artifacts written to {out_dir}")

if __name__ == "__main__":
    main()
