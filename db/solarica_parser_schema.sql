-- Solarica Parsing Engine schema.
-- Standalone DB for the parser — isolated from any other 'solarica' DB on the host.
-- Stores parsed artifacts (blocks/trackers/piers), user annotations (pier_statuses),
-- uploaded source files, and extracted metadata/validation.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id TEXT UNIQUE NOT NULL,          -- user-visible code, e.g. "ashalim3"
    name TEXT NOT NULL,
    site_profile TEXT,
    status TEXT NOT NULL DEFAULT 'draft',     -- draft | parsing | ready | error
    parse_error TEXT,
    parsed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Uploaded source files (construction PDF, ramming PDF, overlay image, etc.)
CREATE TABLE IF NOT EXISTS project_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,                       -- construction_pdf | ramming_pdf | overlay_image | other
    filename TEXT NOT NULL,
    original_name TEXT,
    storage_path TEXT NOT NULL,               -- absolute path on server disk
    size_bytes BIGINT,
    sha256 TEXT,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_project_files_project_id ON project_files(project_id);

-- Metadata / plant info / extracted electrical / validation targets (flexible JSONB)
CREATE TABLE IF NOT EXISTS project_metadata (
    project_id UUID PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,       -- full summary.json equivalent
    plant_info JSONB NOT NULL DEFAULT '{}'::jsonb,    -- user-editable overrides + extracted
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Parsed entities
CREATE TABLE IF NOT EXISTS blocks (
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
    data JSONB NOT NULL DEFAULT '{}'::jsonb,   -- remaining fields from blocks.json
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(project_id, block_code)
);
CREATE INDEX IF NOT EXISTS ix_blocks_project_id ON blocks(project_id);

CREATE TABLE IF NOT EXISTS trackers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    tracker_code TEXT NOT NULL,
    block_code TEXT,
    row_num TEXT,
    trk TEXT,
    tracker_type_code TEXT,
    tracker_sheet TEXT,
    orientation TEXT,
    pier_count INT,
    bbox_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(project_id, tracker_code)
);
CREATE INDEX IF NOT EXISTS ix_trackers_project_id ON trackers(project_id);
CREATE INDEX IF NOT EXISTS ix_trackers_block_code ON trackers(project_id, block_code);
CREATE INDEX IF NOT EXISTS ix_trackers_row_num ON trackers(project_id, row_num);

CREATE TABLE IF NOT EXISTS piers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    pier_code TEXT NOT NULL,
    tracker_code TEXT,
    block_code TEXT,
    row_num TEXT,
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
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(project_id, pier_code)
);
CREATE INDEX IF NOT EXISTS ix_piers_project_id ON piers(project_id);
CREATE INDEX IF NOT EXISTS ix_piers_block ON piers(project_id, block_code);
CREATE INDEX IF NOT EXISTS ix_piers_tracker ON piers(project_id, tracker_code);
CREATE INDEX IF NOT EXISTS ix_piers_type ON piers(project_id, pier_type);
CREATE INDEX IF NOT EXISTS ix_piers_row ON piers(project_id, row_num);

-- User annotations (replaces pier_statuses.json)
CREATE TABLE IF NOT EXISTS pier_statuses (
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    pier_code TEXT NOT NULL,
    status TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, pier_code)
);
CREATE INDEX IF NOT EXISTS ix_pier_statuses_project ON pier_statuses(project_id);

-- Drawing bundles and zoom targets (kept as JSONB for now — rarely queried)
CREATE TABLE IF NOT EXISTS drawing_bundles (
    project_id UUID PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    bundles JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS zoom_targets (
    project_id UUID PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    targets JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Aggregation views for fast queries without re-scanning 25k rows
CREATE OR REPLACE VIEW project_pier_type_counts AS
SELECT
    project_id,
    pier_type,
    COUNT(*)::BIGINT AS count
FROM piers
WHERE pier_type IS NOT NULL
GROUP BY project_id, pier_type;

CREATE OR REPLACE VIEW project_block_summary AS
SELECT
    project_id,
    block_code,
    COUNT(*)::BIGINT AS pier_count,
    COUNT(DISTINCT tracker_code)::BIGINT AS tracker_count,
    COUNT(DISTINCT row_num)::BIGINT AS row_count
FROM piers
WHERE block_code IS NOT NULL
GROUP BY project_id, block_code;

CREATE OR REPLACE VIEW project_tracker_summary AS
SELECT
    project_id,
    block_code,
    row_num,
    trk,
    tracker_code,
    pier_count
FROM trackers;

CREATE OR REPLACE VIEW project_row_summary AS
SELECT
    project_id,
    row_num,
    COUNT(DISTINCT tracker_code)::BIGINT AS tracker_count,
    COUNT(*)::BIGINT AS pier_count
FROM piers
WHERE row_num IS NOT NULL AND row_num <> ''
GROUP BY project_id, row_num;
