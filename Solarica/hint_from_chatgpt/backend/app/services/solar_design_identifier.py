
import re

PATTERNS = {
    "S_DOT_3": re.compile(r"^S\.(?:[1-9]\d?)\.(?:[1-9]\d?)\.(?:[1-9]\d?)$"),
    "S4_LEVEL": re.compile(r"^S(?:[1-9]\d?)\.(?:[1-9]\d?)\.(?:[1-9]\d?)\.(?:[1-9]\d?)$")
}

def detect_pattern(tokens):
    counts = {k: 0 for k in PATTERNS}
    for t in tokens:
        for name, pattern in PATTERNS.items():
            if pattern.match(t):
                counts[name] += 1
    return max(counts, key=counts.get)

def parse_string(token, pattern_name):
    pattern = PATTERNS[pattern_name]
    if not pattern.match(token):
        return None
    return token
