import struct, re
from pathlib import Path

DATA_DIR = Path(r"C:\Users\salma\Documents\hamadya_data")
files = sorted(DATA_DIR.glob("*.SUI"))[:8]

print("=== FLOAT SCAN (4-byte LE) across first 8 files ===")
print(f"{'off':>4}  " + "  ".join(f"{p.name[:18]:>18}" for p in files))
for off in range(14, 160, 4):
    row = []
    floats = []
    for path in files:
        data = path.read_bytes()
        if off + 4 <= len(data):
            v = struct.unpack_from("<f", data, off)[0]
            floats.append(v)
            row.append(f"{v:18.4f}")
        else:
            row.append(f"{'N/A':>18}")
    if any(0.01 < abs(v) < 100000 for v in floats):
        print(f"{off:4d}  " + "  ".join(row))

print()
print("=== TEXT FIELDS (fixed offsets) ===")
f = files[0]
data = f.read_bytes()

# Known fixed text fields
for off, label in [
    (154, "firmware"),
    (161, "device_serial"),
    (233, "string_id"),
    (255, "cell_type"),
    (301, "manufacturer"),
    (326, "module_model"),
    (2478, "date_short"),
    (2487, "time"),
    (2649, "datetime_full"),
]:
    chunk = data[off:off+40]
    txt = chunk.split(b"\x00")[0].decode("latin-1", errors="replace").strip()
    print(f"  off={off:4d} [{label:20s}]: {repr(txt)}")
