# Admin-editable Validation Rules

## Rule goals

- Detect design conflicts before construction
- Be updateable by admin without code changes
- Support severity and stage gating

## Rule categories

1. `id_naming`
2. `quantity_consistency`
3. `electrical`
4. `layout_routing`
5. `construction`
6. `commissioning`
7. `maintenance`

## Required starter rules

### ID and sequencing
- `STRING_CODE_PATTERN`
- `STRING_ID_UNIQUE`
- `STRING_SEQUENCE_STARTS_AT_ONE`
- `STRING_SEQUENCE_NO_GAPS`

### Quantity
- `TOTAL_STRING_COUNT_MATCH`
- `TOTAL_MODULE_COUNT_MATCH`
- `TOTAL_INVERTER_COUNT_MATCH`

### Electrical
- `MODULES_PER_STRING_RANGE`
- `MAX_STRINGS_PER_INVERTER`
- `DC_AC_RATIO_RANGE`
- `STRING_VOC_BELOW_MAX_DC`
- `STRING_VMP_WITHIN_MPPT_RANGE`

### Layout / routing
- `CABLE_PATH_MAX_LENGTH`
- `NO_PATH_CROSSING_RESTRICTED_ZONE`

### Commissioning
- `PRE_ENERGIZATION_TESTS_REQUIRED`
- `PASS_REQUIRED_BEFORE_ENERGIZATION`

## Rule schema pattern

```json
{
  "rule_code": "STRING_SEQUENCE_NO_GAPS",
  "rule_name": "String sequence has no gaps",
  "scope": "inverter",
  "category": "id_naming",
  "severity": "blocker",
  "is_active": true,
  "engine_type": "sequence_check",
  "parameters": {
    "prefix": "S",
    "start_from": 1,
    "require_continuous": true
  },
  "message_template": "Section {section}, inverter {inverter} has non-sequential strings. Expected {expected}, found {actual}."
}
```

## Example semantics for your string code

`S.<section>.<inverter>.<string_index>`

Example:
- `S.1.2.3` = section 1, inverter 2, string 3

Rules for this pattern:
- exact regex match
- uniqueness within project
- sequence starts from 1
- sequence has no gaps per `(section, inverter)`

## Exceptions

Do not disable rules globally just because one project is special. Use project/entity-scoped exceptions with approval.
