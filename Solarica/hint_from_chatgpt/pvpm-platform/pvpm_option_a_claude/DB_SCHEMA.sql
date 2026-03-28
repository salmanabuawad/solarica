create extension if not exists pgcrypto;

create table sites (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);

create table measurement_missions (
  id uuid primary key default gen_random_uuid(),
  site_id uuid not null references sites(id),
  mission_name text not null,
  status text not null check (status in ('draft','ready','in_progress','completed','cancelled')) default 'draft',
  created_by text,
  assigned_to text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz
);

create table measurement_mission_items (
  id uuid primary key default gen_random_uuid(),
  mission_id uuid not null references measurement_missions(id) on delete cascade,
  sequence_no integer not null,
  string_name text not null,
  expected_module_count integer,
  expected_pattern text,
  status text not null check (status in ('pending','measuring','completed','skipped','failed')) default 'pending',
  note text,
  created_at timestamptz not null default now(),
  unique (mission_id, sequence_no)
);

create table measurements (
  id uuid primary key default gen_random_uuid(),
  mission_id uuid not null references measurement_missions(id) on delete cascade,
  mission_item_id uuid not null references measurement_mission_items(id) on delete cascade,
  site_id uuid references sites(id),
  string_name text not null,
  operator_name text,
  device_serial text,
  measured_at timestamptz not null default now(),
  raw_payload jsonb not null,
  voc numeric,
  isc numeric,
  vmp numeric,
  imp numeric,
  pmax numeric,
  ff numeric,
  rs numeric,
  rp numeric,
  irradiance numeric,
  module_temp numeric,
  created_at timestamptz not null default now()
);

create table measurement_attempts (
  id uuid primary key default gen_random_uuid(),
  mission_item_id uuid not null references measurement_mission_items(id) on delete cascade,
  attempt_no integer not null,
  status text not null check (status in ('started','completed','failed')),
  error_message text,
  raw_payload jsonb,
  created_at timestamptz not null default now(),
  unique (mission_item_id, attempt_no)
);
