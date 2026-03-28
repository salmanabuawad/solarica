-- Fix: make design_file_id nullable in string_scan_run and map_scan_rectangle
-- The column was NOT NULL in v3 migration but save_scan_run never provides it.

ALTER TABLE string_scan_run
    ALTER COLUMN design_file_id DROP NOT NULL;

ALTER TABLE map_scan_rectangle
    ALTER COLUMN design_file_id DROP NOT NULL;

-- Update pattern regexes to v4 spec (max 2 digits, no leading zeros)
INSERT INTO string_id_pattern (
    pattern_code, pattern_name, match_regex, parse_regex, example_value,
    level_count, levels_json, max_digits_per_level, no_leading_zero, is_active
) VALUES
(
    'S_DOT_3', 'S.1.2.3 format',
    '^S\.(?:[1-9]\d?)\.(?:[1-9]\d?)\.(?:[1-9]\d?)$',
    '^S\.([1-9]\d?)\.([1-9]\d?)\.([1-9]\d?)$',
    'S.1.2.3', 3, '["section","inverter","string"]'::JSONB, 2, TRUE, TRUE
),
(
    'S4_LEVEL', 'S1.1.2.3 format',
    '^S(?:[1-9]\d?)\.(?:[1-9]\d?)\.(?:[1-9]\d?)\.(?:[1-9]\d?)$',
    '^S([1-9]\d?)\.([1-9]\d?)\.([1-9]\d?)\.([1-9]\d?)$',
    'S1.1.2.3', 4, '["major_section","block","inverter","string"]'::JSONB, 2, TRUE, TRUE
)
ON CONFLICT (pattern_code) DO UPDATE SET
    pattern_name = EXCLUDED.pattern_name,
    match_regex = EXCLUDED.match_regex,
    parse_regex = EXCLUDED.parse_regex,
    example_value = EXCLUDED.example_value,
    level_count = EXCLUDED.level_count,
    levels_json = EXCLUDED.levels_json,
    max_digits_per_level = EXCLUDED.max_digits_per_level,
    no_leading_zero = EXCLUDED.no_leading_zero,
    updated_at = NOW();
