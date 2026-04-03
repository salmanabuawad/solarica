# Pipeline

1. load_files
2. extract_text
3. extract_metadata
4. classify_installation
5. detect_patterns
6. extract_inverters
7. extract_strings
8. extract_mppts
9. extract_ac_equipment
10. extract_batteries
11. extract_simple_layout
12. assign_profiles
13. validate_strings
14. validate_output
15. build_report

Each step returns checkpoint output and can be called indirectly through `step` with dependency resolution.
