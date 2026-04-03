# Detailed Documentation

## Supported Inputs
- PDF
- DXF

## Step-by-step progress
Every run stores progress in `.map_parser_jobs/<job_id>.json`.

## Relative positions
The `simple_layout` section returns normalized page coordinates:
- `x`, `y`, `w`, `h`
- `cx`, `cy`
- shape = rectangle

These are intended for frontend charting libraries.

## Installation type fields
Returned under `project_metadata.installation`:
- `primary_type`
- `types`
- `mounting`
- `structure`
- `tracking.enabled`
- `tracking.type`
- `confidence`
- `evidence`

## Trackers
Tracker detection is supported and will mark:
- `mounting = single_axis_tracker`
- `structure = tracker_rows`
- `tracking.enabled = true`
- `tracking.type = single_axis`
when tracker clues are found.
