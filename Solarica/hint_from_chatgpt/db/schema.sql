-- PostgreSQL schema starter for Solar EPC Platform

create table users (
    id bigserial primary key,
    full_name varchar(200) not null,
    email varchar(255) not null unique,
    password_hash text not null,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

create table roles (
    id bigserial primary key,
    role_code varchar(50) not null unique,
    role_name varchar(100) not null,
    scope_type varchar(20) not null check (scope_type in ('global', 'project'))
);

create table user_global_roles (
    id bigserial primary key,
    user_id bigint not null references users(id) on delete cascade,
    role_id bigint not null references roles(id),
    assigned_at timestamptz not null default now(),
    unique (user_id, role_id)
);

create table sites (
    id bigserial primary key,
    site_code varchar(100) not null unique,
    site_name varchar(200) not null,
    country varchar(100),
    region varchar(100),
    latitude numeric(10,7),
    longitude numeric(10,7),
    address text,
    created_at timestamptz not null default now()
);

create table projects (
    id bigserial primary key,
    site_id bigint not null references sites(id),
    project_code varchar(100) not null unique,
    project_name varchar(200) not null,
    status varchar(50) not null default 'planning',
    dc_capacity_mwp numeric(12,3),
    ac_capacity_mw numeric(12,3),
    start_date date,
    planned_end_date date,
    created_at timestamptz not null default now()
);

create table user_project_roles (
    id bigserial primary key,
    user_id bigint not null references users(id) on delete cascade,
    project_id bigint not null references projects(id) on delete cascade,
    role_id bigint not null references roles(id),
    assigned_at timestamptz not null default now(),
    unique (user_id, project_id, role_id)
);

create table project_stage_history (
    id bigserial primary key,
    project_id bigint not null references projects(id) on delete cascade,
    from_status varchar(50),
    to_status varchar(50) not null,
    changed_by bigint references users(id),
    note text,
    changed_at timestamptz not null default now()
);

create table design_files (
    id bigserial primary key,
    project_id bigint not null references projects(id) on delete cascade,
    file_name varchar(255) not null,
    storage_path text not null,
    mime_type varchar(100),
    checksum varchar(128),
    parser_status varchar(30) not null default 'pending',
    uploaded_by bigint references users(id),
    uploaded_at timestamptz not null default now()
);

create table sections (
    id bigserial primary key,
    project_id bigint not null references projects(id) on delete cascade,
    section_code varchar(50) not null,
    section_name varchar(200),
    unique (project_id, section_code)
);

create table inverters (
    id bigserial primary key,
    project_id bigint not null references projects(id) on delete cascade,
    section_id bigint references sections(id) on delete set null,
    inverter_code varchar(50) not null,
    model_code varchar(100),
    dc_capacity_kw numeric(12,3),
    ac_capacity_kw numeric(12,3),
    unique (project_id, inverter_code)
);

create table strings (
    id bigserial primary key,
    project_id bigint not null references projects(id) on delete cascade,
    section_id bigint references sections(id) on delete set null,
    inverter_id bigint references inverters(id) on delete set null,
    string_code varchar(50) not null,
    string_index integer not null,
    module_count integer,
    status varchar(30) not null default 'planned',
    unique (project_id, string_code),
    unique (project_id, section_id, inverter_id, string_index)
);

create table panel_groups (
    id bigserial primary key,
    project_id bigint not null references projects(id) on delete cascade,
    string_id bigint not null references strings(id) on delete cascade,
    panel_model varchar(100),
    panel_count integer not null,
    optimizer_count integer
);

create table cable_paths (
    id bigserial primary key,
    project_id bigint not null references projects(id) on delete cascade,
    string_id bigint references strings(id) on delete set null,
    inverter_id bigint references inverters(id) on delete set null,
    path_code varchar(100),
    estimated_length_m numeric(12,2),
    actual_length_m numeric(12,2),
    notes text
);

create table validation_rules (
    id bigserial primary key,
    rule_code varchar(100) not null unique,
    rule_name varchar(200) not null,
    category varchar(50) not null,
    scope varchar(50) not null,
    severity varchar(20) not null,
    is_active boolean not null default true,
    engine_type varchar(50) not null,
    message_template text,
    description text,
    version_no integer not null default 1,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table validation_rule_parameters (
    id bigserial primary key,
    rule_id bigint not null references validation_rules(id) on delete cascade,
    param_key varchar(100) not null,
    param_value text not null,
    param_type varchar(30) not null,
    unique (rule_id, param_key)
);

create table validation_rule_overrides (
    id bigserial primary key,
    rule_id bigint not null references validation_rules(id) on delete cascade,
    project_id bigint references projects(id) on delete cascade,
    section_code varchar(50),
    inverter_model varchar(100),
    is_active boolean,
    severity varchar(20),
    override_params jsonb,
    created_at timestamptz not null default now()
);

create table validation_runs (
    id bigserial primary key,
    project_id bigint not null references projects(id) on delete cascade,
    design_file_id bigint references design_files(id) on delete set null,
    run_status varchar(30) not null default 'pending',
    started_at timestamptz,
    finished_at timestamptz,
    created_by bigint references users(id)
);

create table validation_issues (
    id bigserial primary key,
    validation_run_id bigint not null references validation_runs(id) on delete cascade,
    rule_code varchar(100) not null,
    severity varchar(20) not null,
    entity_type varchar(50) not null,
    entity_key varchar(200) not null,
    issue_message text not null,
    details jsonb,
    suggested_fix text,
    status varchar(30) not null default 'open'
);

create table validation_exceptions (
    id bigserial primary key,
    project_id bigint not null references projects(id) on delete cascade,
    rule_code varchar(100) not null,
    entity_type varchar(50) not null,
    entity_key varchar(200) not null,
    approved_by bigint references users(id),
    reason text not null,
    valid_from timestamptz,
    valid_to timestamptz
);

create table work_packages (
    id bigserial primary key,
    project_id bigint not null references projects(id) on delete cascade,
    package_code varchar(100) not null,
    title varchar(200) not null,
    section_id bigint references sections(id),
    inverter_id bigint references inverters(id),
    status varchar(30) not null default 'planned',
    planned_start_date date,
    planned_end_date date,
    assigned_to_user_id bigint references users(id),
    unique (project_id, package_code)
);

create table daily_progress_reports (
    id bigserial primary key,
    project_id bigint not null references projects(id) on delete cascade,
    report_date date not null,
    reported_by bigint references users(id),
    crew_count integer,
    weather_notes text,
    blockers text,
    created_at timestamptz not null default now(),
    unique (project_id, report_date, reported_by)
);

create table progress_items (
    id bigserial primary key,
    report_id bigint not null references daily_progress_reports(id) on delete cascade,
    work_package_id bigint references work_packages(id) on delete set null,
    entity_type varchar(50) not null,
    entity_id bigint,
    completed_qty numeric(12,2) not null default 0,
    uom varchar(30),
    status varchar(30),
    note text
);

create table inventory_items (
    id bigserial primary key,
    project_id bigint not null references projects(id) on delete cascade,
    sku varchar(100) not null,
    item_name varchar(200) not null,
    category varchar(100),
    uom varchar(30) not null,
    reorder_level numeric(12,2),
    unique (project_id, sku)
);

create table inventory_transactions (
    id bigserial primary key,
    project_id bigint not null references projects(id) on delete cascade,
    inventory_item_id bigint not null references inventory_items(id) on delete cascade,
    txn_type varchar(30) not null,
    quantity numeric(12,2) not null,
    reference_type varchar(50),
    reference_id bigint,
    note text,
    created_by bigint references users(id),
    created_at timestamptz not null default now()
);

create table test_types (
    id bigserial primary key,
    test_code varchar(50) not null unique,
    test_name varchar(100) not null
);

create table test_records (
    id bigserial primary key,
    project_id bigint not null references projects(id) on delete cascade,
    test_type_id bigint not null references test_types(id),
    entity_type varchar(50) not null,
    entity_id bigint not null,
    test_date date not null,
    result_status varchar(30) not null,
    measured_values jsonb,
    attachment_path text,
    recorded_by bigint references users(id),
    approved_by bigint references users(id)
);

create table maintenance_plans (
    id bigserial primary key,
    project_id bigint not null references projects(id) on delete cascade,
    plan_name varchar(200) not null,
    interval_days integer not null,
    is_active boolean not null default true
);

create table maintenance_events (
    id bigserial primary key,
    project_id bigint not null references projects(id) on delete cascade,
    plan_id bigint references maintenance_plans(id) on delete set null,
    due_date date not null,
    completed_date date,
    status varchar(30) not null default 'scheduled',
    note text
);
