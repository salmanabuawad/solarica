import re
from collections import defaultdict, Counter

VALID_PATTERN = re.compile(r"^S\.\d+\.\d+\.\d+$")

def extract_labels(text):
    return re.findall(r"[A-Za-z0-9\.]+", text)

def classify(label):
    return "valid" if VALID_PATTERN.match(label) else "invalid"

def extract_valid(labels):
    return [l for l in labels if classify(l) == "valid"]

def detect_duplicates(valid):
    counts = Counter(valid)
    return {k:v for k,v in counts.items() if v > 1}

def group(valid):
    g = defaultdict(set)
    for s in valid:
        _, st, inv, num = s.split(".")
        g[f"{st}.{inv}"].add(int(num))
    return g

def detect_missing(groups):
    out = {}
    for inv, nums in groups.items():
        expected = set(range(1, max(nums)+1))
        missing = sorted(expected - nums)
        if missing:
            out[inv] = missing
    return out

def run(text):
    labels = extract_labels(text)
    valid = extract_valid(labels)
    invalid = [l for l in labels if classify(l) == "invalid"]
    return {
        "valid_total": len(set(valid)),
        "invalid_total": len(invalid),
        "duplicates": detect_duplicates(valid),
        "missing": detect_missing(group(valid))
    }
