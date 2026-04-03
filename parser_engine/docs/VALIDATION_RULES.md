# Validation Rules

## Naming
- One string naming pattern per site: `S.<station>.<inverter>.<string>`
- One inverter naming pattern per site: `<station>.<inverter>`
- `A/B` suffix labels are invalid strings

## Profiles
- Allowed string counts per inverter are parsed from drawing text where possible
- Default allowed values: 20, 21, 22
- Allowed modules per string parsed where possible
- Default fallback is drawing-declared value or 27

## Output validation
- Compare declared DC power with calculated module power
- Compare modules with strings × modules_per_string
- Report mismatch flags

## Installation
- Detect floating / rooftop / tracker / utility-scale clues from text and metadata
