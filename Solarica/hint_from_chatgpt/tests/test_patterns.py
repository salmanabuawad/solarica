
from backend.app.services.solar_design_identifier import detect_pattern

def test_detection():
    tokens = ["S1.1.2.3", "S1.1.2.4"]
    assert detect_pattern(tokens) == "S4_LEVEL"
