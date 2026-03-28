import struct, re
from pathlib import Path

DATA_DIR = Path(r"C:\Users\salma\Documents\hamadya_data")
files = sorted(DATA_DIR.glob("*.SUI"))[:6]

# Find offsets where values DIFFER between files (= per-measurement data)
print("=== Offsets where floats DIFFER between files (400-2470) ===")
print(f"{'off':>4}  " + "  ".join(f"{p.name[11:19]:>10}" for p in files))
for off in range(128, 2470, 4):
    floats = []
    for path in files:
        data = path.read_bytes()
        if off + 4 <= len(data):
            v = struct.unpack_from("<f", data, off)[0]
            floats.append(v)
    if len(set(f"{v:.3f}" for v in floats)) > 1:  # differs across files
        if any(0.001 < abs(v) < 100000 for v in floats):
            vals = "  ".join(f"{v:10.4f}" for v in floats)
            print(f"{off:4d}  {vals}")

print()
print("=== Last 300 bytes text per file ===")
for path in files:
    data = path.read_bytes()
    tail = data[-300:]
    enc = tail.decode("latin-1", errors="replace")
    # find printable runs
    runs = re.findall(r'[ -~\t]{4,}', enc)
    print(f"\n{path.name}:")
    for r in runs:
        print(f"  {repr(r.strip())}")
