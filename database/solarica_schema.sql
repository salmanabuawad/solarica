-- Solarica full schema starter
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    customer_name VARCHAR(255),
    site_name VARCHAR(255) NOT NULL,
    project_type VARCHAR(100) NOT NULL,
    phase VARCHAR(50) NOT NULL DEFAULT 'design',
    progress_percent NUMERIC(5,2) NOT NULL DEFAULT 0,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS naming_patterns (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    asset_type VARCHAR(50) NOT NULL,
    pattern_name VARCHAR(100) NOT NULL,
    pattern_regex TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS design_validation_runs (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL,
    summary_json JSONB,
    created_by_user_id INT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS design_validation_issues (
    id SERIAL PRIMARY KEY,
    validation_run_id INT NOT NULL REFERENCES design_validation_runs(id) ON DELETE CASCADE,
    severity VARCHAR(20) NOT NULL,
    asset_type VARCHAR(50),
    asset_ref VARCHAR(255),
    issue_type VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    details_json JSONB
);

CREATE TABLE IF NOT EXISTS inverters (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    inverter_no VARCHAR(255) NOT NULL,
    capacity_kw NUMERIC(10,2),
    metadata_json JSONB,
    UNIQUE(project_id, inverter_no)
);

CREATE TABLE IF NOT EXISTS strings (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    inverter_id INT REFERENCES inverters(id) ON DELETE SET NULL,
    string_no VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'planned',
    metadata_json JSONB,
    UNIQUE(project_id, string_no)
);

CREATE TABLE IF NOT EXISTS measurements (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES projects(id) ON DELETE SET NULL,
    string_id INT REFERENCES strings(id) ON DELETE SET NULL,
    source_file_name VARCHAR(255),
    measured_at TIMESTAMP,
    device_serial VARCHAR(255),
    site_label VARCHAR(255),
    string_label VARCHAR(255),
    module_part_number VARCHAR(255),
    payload_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS maintenance_tasks (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    site_name VARCHAR(255) NOT NULL,
    asset_type VARCHAR(50) NOT NULL,
    asset_ref VARCHAR(255),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    task_type VARCHAR(50) NOT NULL DEFAULT 'maintenance',
    priority VARCHAR(50) NOT NULL DEFAULT 'medium',
    status VARCHAR(50) NOT NULL DEFAULT 'new',
    assigned_to VARCHAR(255),
    requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
    requires_test_result BOOLEAN NOT NULL DEFAULT FALSE,
    task_material_mode VARCHAR(50) NOT NULL DEFAULT 'mixed',
    due_date TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS task_messages (
    id SERIAL PRIMARY KEY,
    task_id INT NOT NULL REFERENCES maintenance_tasks(id) ON DELETE CASCADE,
    author_name VARCHAR(255) NOT NULL,
    message_type VARCHAR(50) NOT NULL DEFAULT 'text',
    message_text TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS task_attachments (
    id SERIAL PRIMARY KEY,
    task_id INT NOT NULL REFERENCES maintenance_tasks(id) ON DELETE CASCADE,
    message_id INT REFERENCES task_messages(id) ON DELETE SET NULL,
    file_type VARCHAR(50) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    mime_type VARCHAR(255),
    uploaded_by VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS task_approvals (
    id SERIAL PRIMARY KEY,
    task_id INT NOT NULL REFERENCES maintenance_tasks(id) ON DELETE CASCADE,
    approval_level INT NOT NULL,
    approval_role VARCHAR(100) NOT NULL,
    approver_name VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    decision_note TEXT,
    decided_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_test_results (
    id SERIAL PRIMARY KEY,
    task_id INT NOT NULL REFERENCES maintenance_tasks(id) ON DELETE CASCADE,
    test_type VARCHAR(100) NOT NULL,
    measurement_id INT REFERENCES measurements(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    summary TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'informational',
    source_type VARCHAR(50) NOT NULL DEFAULT 'manual',
    raw_result_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS issues (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    asset_type VARCHAR(50),
    asset_ref VARCHAR(255),
    severity VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_reports (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_name VARCHAR(255) NOT NULL,
    report_date DATE NOT NULL,
    summary TEXT,
    weather TEXT,
    blockers TEXT,
    progress_percent NUMERIC(5,2),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS materials (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    unit VARCHAR(50) NOT NULL,
    sku VARCHAR(100),
    min_threshold NUMERIC(12,3) NOT NULL DEFAULT 0,
    unit_cost NUMERIC(12,2)
);

CREATE TABLE IF NOT EXISTS bom_definitions (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    asset_type VARCHAR(50) NOT NULL,
    asset_template VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bom_items (
    id SERIAL PRIMARY KEY,
    bom_id INT NOT NULL REFERENCES bom_definitions(id) ON DELETE CASCADE,
    material_id INT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    quantity_per_unit NUMERIC(12,3) NOT NULL
);

CREATE TABLE IF NOT EXISTS warehouses (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES projects(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    location TEXT,
    manager_name VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS warehouse_stock (
    id SERIAL PRIMARY KEY,
    warehouse_id INT NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    material_id INT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    quantity_available NUMERIC(12,3) NOT NULL DEFAULT 0,
    quantity_reserved NUMERIC(12,3) NOT NULL DEFAULT 0,
    last_updated TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(warehouse_id, material_id)
);

CREATE TABLE IF NOT EXISTS material_issue_transactions (
    id SERIAL PRIMARY KEY,
    warehouse_id INT NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    project_id INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    task_id INT REFERENCES maintenance_tasks(id) ON DELETE SET NULL,
    issued_to_user VARCHAR(255),
    issued_by_user VARCHAR(255),
    site_name VARCHAR(255),
    asset_type VARCHAR(50),
    asset_ref VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'issued',
    issued_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expected_usage_by_date TIMESTAMP,
    last_activity_at TIMESTAMP,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS material_issue_items (
    id SERIAL PRIMARY KEY,
    transaction_id INT NOT NULL REFERENCES material_issue_transactions(id) ON DELETE CASCADE,
    material_id INT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    quantity_issued NUMERIC(12,3) NOT NULL DEFAULT 0,
    quantity_returned NUMERIC(12,3) NOT NULL DEFAULT 0,
    quantity_consumed NUMERIC(12,3) NOT NULL DEFAULT 0,
    quantity_missing NUMERIC(12,3) NOT NULL DEFAULT 0,
    unit VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS material_usage_events (
    id SERIAL PRIMARY KEY,
    transaction_id INT NOT NULL REFERENCES material_issue_transactions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    related_entity_type VARCHAR(50),
    related_entity_id INT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS material_transaction_attachments (
    id SERIAL PRIMARY KEY,
    transaction_id INT NOT NULL REFERENCES material_issue_transactions(id) ON DELETE CASCADE,
    file_type VARCHAR(50) NOT NULL,
    file_path TEXT NOT NULL,
    uploaded_by VARCHAR(255),
    caption TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS inventory_variance_flags (
    id SERIAL PRIMARY KEY,
    transaction_id INT NOT NULL REFERENCES material_issue_transactions(id) ON DELETE CASCADE,
    material_id INT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    expected_quantity NUMERIC(12,3) NOT NULL,
    actual_quantity NUMERIC(12,3) NOT NULL,
    variance_quantity NUMERIC(12,3) NOT NULL,
    severity VARCHAR(50) NOT NULL,
    reason TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    reviewed_by VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES projects(id) ON DELETE CASCADE,
    asset_type VARCHAR(50),
    asset_ref VARCHAR(255),
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
