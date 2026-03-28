REQUIRED_PRE_ENERGIZATION = ["continuity", "polarity", "megger", "iv_curve"]

def commissioning_ready(passed_tests: list[str], required_tests: list[str] | None = None) -> bool:
    required = required_tests or REQUIRED_PRE_ENERGIZATION
    return all(test in passed_tests for test in required)
