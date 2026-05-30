-- Solarica Parsing Engine schema for MySQL / MariaDB (port of solarica_parser_schema.sql).
-- UUIDs are CHAR(36) (matches existing string UUIDs); generated via UUID() server-side or by the app.
-- JSONB -> JSON; TIMESTAMPTZ -> DATETIME (UTC convention); SERIAL -> INT AUTO_INCREMENT.
-- TEXT columns that participate in keys/indexes are kept as VARCHAR(255).

SET NAMES utf8mb4;

-- ---------- Projects ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    id            CHAR(36)     NOT NULL DEFAULT (UUID()),
    project_id    VARCHAR(255) NOT NULL,
    name          TEXT         NOT NULL,
    site_profile  TEXT,
    status        VARCHAR(32)  NOT NULL DEFAULT 'draft',
    parse_error   TEXT,
    parsed_at     DATETIME,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    scan_analytics_json JSON    NOT NULL DEFAULT ('{}'),
    string_pattern      TEXT,
    PRIMARY KEY (id),
    UNIQUE KEY uq_projects_project_id (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- Uploaded source files --------------------------------------------
CREATE TABLE IF NOT EXISTS project_files (
    id             CHAR(36)     NOT NULL DEFAULT (UUID()),
    project_id     CHAR(36)     NOT NULL,
    kind           VARCHAR(64)  NOT NULL,
    filename       TEXT         NOT NULL,
    original_name  TEXT,
    storage_path   TEXT         NOT NULL,
    size_bytes     BIGINT,
    sha256         VARCHAR(128),
    uploaded_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_project_files_project_id (project_id),
    CONSTRAINT fk_project_files_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- Project metadata (JSON blobs) ------------------------------------
CREATE TABLE IF NOT EXISTS project_metadata (
    project_id  CHAR(36)  NOT NULL,
    summary     JSON      NOT NULL,
    plant_info  JSON      NOT NULL,
    updated_at  DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id),
    CONSTRAINT fk_project_metadata_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- Parsed entities --------------------------------------------------
CREATE TABLE IF NOT EXISTS blocks (
    id                     CHAR(36)     NOT NULL DEFAULT (UUID()),
    project_id             CHAR(36)     NOT NULL,
    block_code             VARCHAR(255) NOT NULL,
    label                  TEXT,
    color                  VARCHAR(64),
    original_block_id      VARCHAR(255),
    block_pier_plan_sheet  VARCHAR(255),
    bbox_json              JSON         NOT NULL DEFAULT ('{}'),
    centroid_json          JSON         NOT NULL DEFAULT ('{}'),
    polygon_json           JSON         NOT NULL DEFAULT ('[]'),
    data                   JSON         NOT NULL DEFAULT ('{}'),
    created_at             DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_blocks_project_block_code (project_id, block_code),
    KEY ix_blocks_project_id (project_id),
    CONSTRAINT fk_blocks_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS trackers (
    id                 CHAR(36)     NOT NULL DEFAULT (UUID()),
    project_id         CHAR(36)     NOT NULL,
    tracker_code       VARCHAR(255) NOT NULL,
    block_code         VARCHAR(255),
    row_num            VARCHAR(64),
    trk                VARCHAR(64),
    tracker_type_code  VARCHAR(64),
    tracker_sheet      VARCHAR(255),
    orientation        VARCHAR(32),
    pier_count         INT,
    bbox_json          JSON         NOT NULL DEFAULT ('{}'),
    data               JSON         NOT NULL DEFAULT ('{}'),
    created_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_trackers_project_tracker_code (project_id, tracker_code),
    KEY ix_trackers_project_id (project_id),
    KEY ix_trackers_block_code (project_id, block_code),
    KEY ix_trackers_row_num    (project_id, row_num),
    CONSTRAINT fk_trackers_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS piers (
    id                 CHAR(36)     NOT NULL DEFAULT (UUID()),
    project_id         CHAR(36)     NOT NULL,
    pier_code          VARCHAR(255) NOT NULL,
    tracker_code       VARCHAR(255),
    block_code         VARCHAR(255),
    row_num            VARCHAR(64),
    row_pier_count     INT,
    tracker_type_code  VARCHAR(64),
    tracker_sheet      VARCHAR(255),
    structure_code     VARCHAR(64),
    structure_sheet    VARCHAR(255),
    pier_type          VARCHAR(32),
    pier_type_sheet    VARCHAR(255),
    slope_band         VARCHAR(64),
    slope_sheet        VARCHAR(255),
    x                  DOUBLE,
    y                  DOUBLE,
    bbox_json          JSON         NOT NULL DEFAULT ('{}'),
    assignment_method  VARCHAR(64),
    data               JSON         NOT NULL DEFAULT ('{}'),
    created_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_piers_project_pier_code (project_id, pier_code),
    KEY ix_piers_project_id (project_id),
    KEY ix_piers_block      (project_id, block_code),
    KEY ix_piers_tracker    (project_id, tracker_code),
    KEY ix_piers_type       (project_id, pier_type),
    KEY ix_piers_row        (project_id, row_num),
    CONSTRAINT fk_piers_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- User annotations --------------------------------------------------
CREATE TABLE IF NOT EXISTS pier_statuses (
    project_id  CHAR(36)     NOT NULL,
    pier_code   VARCHAR(255) NOT NULL,
    status      VARCHAR(64)  NOT NULL,
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, pier_code),
    KEY ix_pier_statuses_project (project_id),
    CONSTRAINT fk_pier_statuses_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS drawing_bundles (
    project_id  CHAR(36)  NOT NULL,
    bundles     JSON      NOT NULL DEFAULT ('{}'),
    PRIMARY KEY (project_id),
    CONSTRAINT fk_drawing_bundles_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS zoom_targets (
    project_id  CHAR(36)  NOT NULL,
    targets     JSON      NOT NULL DEFAULT ('{}'),
    PRIMARY KEY (project_id),
    CONSTRAINT fk_zoom_targets_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- Users / access ----------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id             INT          NOT NULL AUTO_INCREMENT,
    username       VARCHAR(255) NOT NULL,
    password_hash  TEXT         NOT NULL,
    display_name   TEXT,
    role           VARCHAR(32)  NOT NULL DEFAULT 'viewer',
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_project_access (
    user_id     INT       NOT NULL,
    project_id  CHAR(36)  NOT NULL,
    created_at  DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, project_id),
    KEY ix_user_project_access_project (project_id),
    CONSTRAINT fk_upa_user    FOREIGN KEY (user_id)    REFERENCES users(id)    ON DELETE CASCADE,
    CONSTRAINT fk_upa_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- Events / records (originally created dynamically in main.py) -----
CREATE TABLE IF NOT EXISTS pier_status_events (
    id           INT          NOT NULL AUTO_INCREMENT,
    project_id   CHAR(36)     NOT NULL,
    pier_code    VARCHAR(255) NOT NULL,
    status       VARCHAR(64)  NOT NULL,
    description  TEXT,
    attachments  JSON         NOT NULL DEFAULT ('[]'),
    created_by   VARCHAR(255),
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_pier_status_events_lookup (project_id, pier_code, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS string_records (
    project_id  CHAR(36)     NOT NULL,
    string_id   VARCHAR(255) NOT NULL,
    status      VARCHAR(32)  NOT NULL DEFAULT 'new',
    comment     TEXT         NOT NULL,
    images      JSON         NOT NULL DEFAULT ('[]'),
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, string_id),
    CONSTRAINT fk_string_records_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- Aggregation views (read by db_store) -----------------------------
CREATE OR REPLACE VIEW project_pier_type_counts AS
SELECT project_id, pier_type, COUNT(*) AS count
  FROM piers
 WHERE pier_type IS NOT NULL
 GROUP BY project_id, pier_type;

CREATE OR REPLACE VIEW project_block_summary AS
SELECT project_id,
       block_code,
       COUNT(*)                            AS pier_count,
       COUNT(DISTINCT tracker_code)        AS tracker_count,
       COUNT(DISTINCT row_num)             AS row_count
  FROM piers
 WHERE block_code IS NOT NULL
 GROUP BY project_id, block_code;

CREATE OR REPLACE VIEW project_tracker_summary AS
SELECT project_id, block_code, row_num, trk, tracker_code, pier_count
  FROM trackers;

CREATE OR REPLACE VIEW project_row_summary AS
SELECT project_id,
       row_num,
       COUNT(DISTINCT tracker_code) AS tracker_count,
       COUNT(*)                      AS pier_count
  FROM piers
 WHERE row_num IS NOT NULL AND row_num <> ''
 GROUP BY project_id, row_num;
