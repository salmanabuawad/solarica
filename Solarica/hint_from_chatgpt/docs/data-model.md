# Data model summary

## Active site pattern
Each site has one active string pattern.

Supported examples:
- `S.1.2.3`
- `S1.1.2.3`

Rules:
- each numeric segment is 1-2 digits
- no leading zeros
- if token starts with `S` and does not match active pattern, report as `invalid_string_name`
- non-`S` identifiers are `non_string`

## Scan flow
1. Load active site pattern from DB
2. Render preview map
3. Operator optionally draws rectangles
4. Fast detect pattern on sampled text
5. Full scan on cropped regions
6. Classify tokens
7. Group valid strings by logical parent
8. Build summary
9. Compare against design
10. Return issues + summary + match status

## Design comparison levels
- project level
- section level
- inverter level
