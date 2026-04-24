CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    block_code TEXT NOT NULL,
    label TEXT,
    color TEXT,
    original_block_id TEXT,
    block_pier_plan_sheet TEXT,
    bbox_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    centroid_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    polygon_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(project_id, block_code)
);

CREATE TABLE trackers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    tracker_code TEXT NOT NULL,
    block_code TEXT,
    tracker_type_code TEXT,
    tracker_sheet TEXT,
    orientation TEXT,
    pier_count INT,
    bbox_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    assignment_method TEXT,
    assignment_confidence TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(project_id, tracker_code)
);

CREATE TABLE piers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    pier_code TEXT NOT NULL,
    tracker_code TEXT,
    block_code TEXT,
    row_pier_count INT,
    tracker_type_code TEXT,
    tracker_sheet TEXT,
    structure_code TEXT,
    structure_sheet TEXT,
    pier_type TEXT,
    pier_type_sheet TEXT,
    slope_band TEXT,
    slope_sheet TEXT,
    x DOUBLE PRECISION,
    y DOUBLE PRECISION,
    bbox_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    assignment_method TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(project_id, pier_code)
);

CREATE TABLE zoom_targets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    object_type TEXT NOT NULL,
    object_code TEXT NOT NULL,
    target_kind TEXT NOT NULL,
    sheet_id TEXT,
    bbox_json JSONB NOT NULL,
    padding INT DEFAULT 24,
    preferred_zoom DOUBLE PRECISION,
    overlay_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(project_id, object_type, object_code, target_kind)
);

CREATE TABLE drawing_bundles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    pier_code TEXT NOT NULL,
    block_pier_plan_sheet TEXT,
    tracker_typical_sheet TEXT,
    pier_tolerances_sheet TEXT,
    slope_detail_sheet TEXT,
    crops_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    highlights_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(project_id, pier_code)
);
