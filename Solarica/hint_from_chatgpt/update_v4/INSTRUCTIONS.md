
# CLAUDE INSTRUCTIONS — STRING SCAN SYSTEM V4

Goal:
Implement full solar string parsing, validation, and design comparison system.

---

## 1. Patterns (DB Driven)

Support:

Pattern A:
S.1.2.3
Regex:
^S\.(?:[1-9]\d?)\.(?:[1-9]\d?)\.(?:[1-9]\d?)$

Pattern B:
S1.1.2.3
Regex:
^S(?:[1-9]\d?)\.(?:[1-9]\d?)\.(?:[1-9]\d?)\.(?:[1-9]\d?)$

Rules:
- max 2 digits
- no leading zeros
- must start with S

---

## 2. Classification

if token.startswith("S"):
    if matches regex:
        valid_string
    else:
        invalid_string_name
else:
    non_string

---

## 3. Section Rectangles

Accept UI rectangles:
- scan only inside regions
- fallback full scan if none

---

## 4. Fast Detection

- sample tokens
- count matches
- return confidence

---

## 5. Grouping

Pattern A:
(section, inverter)

Pattern B:
(major_section, block, inverter)

---

## 6. Validation

- invalid_string_name → error
- duplicates → error
- missing sequence → error
- per inverter string count
- total vs design

---

## 7. Summary

Project:
- total_valid_strings
- total_invalid_string_names
- total_duplicates
- total_inverters_found

Section + inverter summaries required

---

## 8. Design Comparison

Compare:
- total strings
- inverter count
- per inverter counts

---

## 9. System Support

- tracker sites (±60 deg)
- variable string counts (18–22)

---

## 10. Issues

- invalid_string_name
- duplicate_string
- missing_sequence
- inverter_string_count_mismatch
- design_total_mismatch

---

## 11. DO NOT

- do not auto fix
- do not ignore invalid
- do not mix non-strings

---

## END
