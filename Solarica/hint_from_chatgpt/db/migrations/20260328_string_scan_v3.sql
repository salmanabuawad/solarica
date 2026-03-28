create table if not exists string_id_pattern (
    id bigserial primary key,
    pattern_code varchar(50) not null unique,
    pattern_name varchar(100) not null,
    match_regex text not null,
    parse_regex text not null,
    example_value varchar(100),
    level_count integer not null,
    levels_json jsonb not null,
    max_digits_per_level integer not null default 2,
    no_leading_zero boolean not null default true,
    is_active boolean not null default true,
    created_at timestamp not null default now(),
    updated_at timestamp not null default now()
);

create table if not exists site_string_pattern (
    id bigserial primary key,
    site_id bigint not null,
    pattern_id bigint not null references string_id_pattern(id),
    is_active boolean not null default true,
    assigned_at timestamp not null default now(),
    assigned_by bigint null
);

create unique index if not exists uq_site_one_active_pattern
    on site_string_pattern(site_id)
    where is_active = true;

create table if not exists map_scan_rectangle (
    id bigserial primary key,
    design_file_id bigint not null,
    section_code varchar(50) not null,
    page_no integer not null default 1,
    x_pct numeric(6,2) not null,
    y_pct numeric(6,2) not null,
    w_pct numeric(6,2) not null,
    h_pct numeric(6,2) not null,
    created_by bigint null,
    created_at timestamp not null default now()
);

create table if not exists string_scan_run (
    id bigserial primary key,
    design_file_id bigint not null,
    site_id bigint not null,
    pattern_id bigint not null references string_id_pattern(id),
    detected_pattern_code varchar(50) not null,
    confidence numeric(5,4) not null,
    page_no integer not null default 1,
    compare_to_design boolean not null default true,
    created_at timestamp not null default now()
);

create table if not exists string_scan_issue (
    id bigserial primary key,
    scan_run_id bigint not null references string_scan_run(id) on delete cascade,
    issue_type varchar(100) not null,
    severity varchar(20) not null,
    entity_type varchar(50) not null,
    entity_key varchar(200) not null,
    message text not null,
    details jsonb not null default '{}'::jsonb
);

create table if not exists string_scan_summary (
    id bigserial primary key,
    scan_run_id bigint not null references string_scan_run(id) on delete cascade,
    expected_total_strings integer,
    found_total_valid_strings integer not null,
    total_invalid_string_names integer not null,
    total_duplicates integer not null,
    expected_inverter_groups integer,
    found_inverter_groups integer not null,
    matches_design boolean not null
);

insert into string_id_pattern (
    pattern_code, pattern_name, match_regex, parse_regex, example_value,
    level_count, levels_json, max_digits_per_level, no_leading_zero, is_active
) values
(
    'S_DOT_3',
    'S.1.2.3 format',
    '^S\.(?:[1-9]\d?)\.(?:[1-9]\d?)\.(?:[1-9]\d?)$',
    '^S\.([1-9]\d?)\.([1-9]\d?)\.([1-9]\d?)$',
    'S.1.2.3',
    3,
    '["section","inverter","string"]'::jsonb,
    2,
    true,
    true
),
(
    'S4_LEVEL',
    'S1.1.2.3 format',
    '^S(?:[1-9]\d?)\.(?:[1-9]\d?)\.(?:[1-9]\d?)\.(?:[1-9]\d?)$',
    '^S([1-9]\d?)\.([1-9]\d?)\.([1-9]\d?)\.([1-9]\d?)$',
    'S1.1.2.3',
    4,
    '["major_section","block","inverter","string"]'::jsonb,
    2,
    true,
    true
)
on conflict (pattern_code) do update
set
    pattern_name = excluded.pattern_name,
    match_regex = excluded.match_regex,
    parse_regex = excluded.parse_regex,
    example_value = excluded.example_value,
    level_count = excluded.level_count,
    levels_json = excluded.levels_json,
    max_digits_per_level = excluded.max_digits_per_level,
    no_leading_zero = excluded.no_leading_zero,
    is_active = excluded.is_active,
    updated_at = now();
