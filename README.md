# Solarica final complete repo

This repo includes:
- FastAPI backend
- row-first parser
- PostgreSQL/PostGIS schema
- React frontend
- layered engineering map with blocks / trackers / piers
- pier details panel
- drawing-bundle resolver
- relative local coordinate system
- site-profile driven ingestion for multi-site tuning

## Input files

Put files here:
- `data/source/construction.pdf`
- `data/source/ramming_plan.pdf`
- `data/source/block_names.jpeg`

The overlay input may also be a PDF color map now, not just a JPEG/PNG.

## Database

```bash
psql -U postgres -f db/create_db.sql
psql -U postgres -d solarica_local -f db/solarica_local_schema.sql
```

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.jobs.build_project_artifacts --project-id ashalim3 --construction-pdf ../data/source/construction.pdf --ramming-pdf ../data/source/ramming_plan.pdf --overlay-image ../data/source/block_names.jpeg --site-profile auto --save-db
uvicorn app.main:app --reload --port 8000
```

### Multi-site usage

The parser is no longer locked to one site. It can:
- auto-detect a built-in profile from filenames
- use a named built-in profile with `--site-profile`
- load a JSON override file with `--profile-config`
- pick construction / ramming / overlay PDF pages using text keywords and fallbacks
- accept a PDF overlay source in addition to image files

Built-in profiles:
- `default`
- `ashalim3`
- `hmd`
- `qun`

Example with an explicit profile:

```bash
python -m app.jobs.build_project_artifacts \
  --project-id qun_site \
  --construction-pdf ../data/source/construction.pdf \
  --ramming-pdf ../data/source/ramming_plan.pdf \
  --overlay-image ../data/source/color_map.pdf \
  --site-profile qun
```

Example with a custom JSON override:

```json
{
  "extends": "default",
  "construction": {
    "keywords": ["electrical cable plan", "site plan"],
    "candidate_pages": [0, 1, 2]
  },
  "ramming": {
    "candidate_pages": [0]
  },
  "overlay": {
    "keywords": ["color map"],
    "candidate_pages": [0]
  },
  "heuristics": {
    "trackers": {
      "cluster_eps": 44
    },
    "piers": {
      "merge_gap": 10
    }
  }
}
```

Run with:

```bash
python -m app.jobs.build_project_artifacts \
  --project-id custom_site \
  --construction-pdf ../data/source/construction.pdf \
  --ramming-pdf ../data/source/ramming_plan.pdf \
  --overlay-image ../data/source/color_map.pdf \
  --profile-config ../data/source/site_profile.json
```

### Exact vector pier extraction

For PDFs that keep pier labels and symbols in the vector layer, use the dedicated vector job.
This reads `P#` labels from the PDF text layer and matches them to nearby vector symbols instead of relying on raster contour guesses.

```bash
python -m app.jobs.extract_vector_piers \
  --ramming-pdf ../data/source/ramming_plan.pdf \
  --json-out ../data/projects/ashalim3/piers_vector_labeled.json \
  --csv-out ../data/projects/ashalim3/piers_vector_labeled.csv \
  --type-map-svg-out ../data/projects/ashalim3/piers_vector_type_map.svg
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Relative coordinates

- reference = `P1` of lowest-leftmost valid tracker
- `x_local` = across rows
- `y_local` = along rows

Saved per pier:
- `x`, `y`
- `x_local`, `y_local`
- `x_tracker_local`, `y_tracker_local`

Saved per tracker:
- `center_local`
- `bbox_local`

Saved per block:
- `centroid_local`
- `polygon_local`
- `bbox_local`

## Important

This is a working production-style scaffold.  
The parser is still heuristic and should be tuned on your exact drawings for best accuracy, but the intended way to do that now is through site profiles and JSON overrides instead of editing parser code per site.
