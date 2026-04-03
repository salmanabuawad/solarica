STEPS = [
    {"id": "load_files", "title": "Load files"},
    {"id": "extract_text", "title": "Extract text / OCR / DXF text"},
    {"id": "extract_metadata", "title": "Extract project metadata"},
    {"id": "classify_installation", "title": "Classify installation type"},
    {"id": "detect_patterns", "title": "Detect naming patterns"},
    {"id": "extract_inverters", "title": "Extract inverters"},
    {"id": "extract_strings", "title": "Extract strings"},
    {"id": "extract_mppts", "title": "Extract MPPTs"},
    {"id": "extract_ac_equipment", "title": "Extract AC equipment"},
    {"id": "extract_batteries", "title": "Extract batteries"},
    {"id": "extract_simple_layout", "title": "Extract simple layout"},
    {"id": "assign_profiles", "title": "Assign inverter/string profiles"},
    {"id": "validate_strings", "title": "Validate strings"},
    {"id": "validate_output", "title": "Validate designed output vs declared output"},
    {"id": "build_report", "title": "Build final report"},
]

REQUIRES = {
    "extract_text": ["load_files"],
    "extract_metadata": ["extract_text"],
    "classify_installation": ["extract_metadata"],
    "detect_patterns": ["extract_text"],
    "extract_inverters": ["detect_patterns"],
    "extract_strings": ["detect_patterns"],
    "extract_mppts": ["extract_text"],
    "extract_ac_equipment": ["extract_text"],
    "extract_batteries": ["extract_text"],
    "extract_simple_layout": ["extract_text", "extract_inverters", "extract_strings"],
    "assign_profiles": ["extract_metadata", "extract_inverters", "extract_strings"],
    "validate_strings": ["assign_profiles"],
    "validate_output": ["extract_metadata", "extract_inverters", "extract_strings", "assign_profiles"],
    "build_report": [
        "extract_metadata", "classify_installation", "detect_patterns", "extract_inverters", "extract_strings",
        "extract_mppts", "extract_ac_equipment", "extract_batteries", "extract_simple_layout", "assign_profiles",
        "validate_strings", "validate_output"
    ],
}


def resolve_steps(target: str | None = None) -> list[str]:
    if target is None:
        return [s["id"] for s in STEPS]

    resolved: list[str] = []

    def visit(step: str):
        for dep in REQUIRES.get(step, []):
            visit(dep)
        if step not in resolved:
            resolved.append(step)

    visit(target)
    return resolved
