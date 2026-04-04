"""
Step definitions for ParserEngine.
IDs and order must stay in sync with backend string_scan._PE_STEP_MAP.
"""

STEPS: list[dict[str, str]] = [
    {"id": "load_files", "title": "Loading files"},
    {"id": "extract_text", "title": "Extracting text"},
    {"id": "extract_metadata", "title": "Reading site metadata"},
    {"id": "classify_installation", "title": "Classifying installation"},
    {"id": "detect_patterns", "title": "Detecting naming patterns"},
    {"id": "extract_inverters", "title": "Mapping inverters"},
    {"id": "extract_strings", "title": "Extracting strings"},
    {"id": "extract_mppts", "title": "Extracting MPPTs"},
    {"id": "extract_ac_equipment", "title": "Reading AC equipment"},
    {"id": "extract_batteries", "title": "Reading storage"},
    {"id": "extract_simple_layout", "title": "Building site layout"},
    {"id": "assign_profiles", "title": "Assigning inverter profiles"},
    {"id": "validate_strings", "title": "Validating strings"},
    {"id": "validate_output", "title": "Validating output"},
    {"id": "build_report", "title": "Building report"},
]
