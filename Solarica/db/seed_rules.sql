-- Starter admin-editable rules
insert into validation_rules
(rule_code, rule_name, category, scope, severity, is_active, engine_type, message_template, description)
values
('STRING_CODE_PATTERN', 'String code format', 'id_naming', 'string', 'error', true, 'regex_match',
 'String {string_code} does not match required pattern.',
 'Validates S.<section>.<inverter>.<string_index>'),
('STRING_ID_UNIQUE', 'String ID unique', 'id_naming', 'project', 'blocker', true, 'uniqueness_check',
 'Duplicate string code found: {string_code}.',
 'Every string code must be unique in project'),
('STRING_SEQUENCE_STARTS_AT_ONE', 'String sequence starts at 1', 'id_naming', 'inverter', 'error', true, 'sequence_check',
 'Section {section}, inverter {inverter} must start from string 1.',
 'Minimum string index must be 1'),
('STRING_SEQUENCE_NO_GAPS', 'String sequence no gaps', 'id_naming', 'inverter', 'blocker', true, 'sequence_check',
 'Section {section}, inverter {inverter} has gaps. Expected {expected}; found {actual}.',
 'String sequence must be continuous'),
('MODULES_PER_STRING_RANGE', 'Modules per string range', 'electrical', 'string', 'error', true, 'range_check',
 'String {string_code} has invalid module count {actual_modules}.',
 'Checks module count range'),
('MAX_STRINGS_PER_INVERTER', 'Max strings per inverter', 'electrical', 'inverter', 'blocker', true, 'range_check',
 'Inverter {inverter_code} exceeds max strings.',
 'Checks inverter string capacity'),
('PRE_ENERGIZATION_TESTS_REQUIRED', 'Required tests before energization', 'commissioning', 'inverter', 'blocker', true, 'required_tests_check',
 'Inverter {inverter_code} missing required passed tests before energization.',
 'Commissioning gate')
on conflict (rule_code) do nothing;
