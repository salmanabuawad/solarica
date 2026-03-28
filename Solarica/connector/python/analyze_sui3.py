"""
Hunt for Voc, Isc, Ppk, FF in SUI files by scanning for floats
that change between files but stay in physically plausible ranges.

Physical ranges expected:
  Voc:  20 – 55 V
  Isc:  1  – 15 A
  Ppk:  50 – 500 W
  FF:   50 – 95 %
  Rs:   0.1 – 5 Ohm
  Rp:   10 – 2000 Ohm
  Irr:  50 – 1500 W/m2
  Temp: -10 – 70 C
"""
import struct, re
from pathlib import Path

DATA_DIR = Path(r"C:\Users\salma\Documents\hamadya_data")
files = sorted(DATA_DIR.glob("*.SUI"))[:8]
all_data = [f.read_bytes() for f in files]

RANGES = {
    "Voc":  (20,  55),
    "Isc":  (1,   15),
    "Ppk":  (50,  500),
    "FF":   (50,  95),
    "Rs":   (0.05, 5),
    "Rp":   (10,  2000),
    "Irr":  (50,  1500),
    "Temp": (5,   70),
}

def in_any_range(v):
    for name, (lo, hi) in RANGES.items():
        if lo <= v <= hi:
            return name
    return None

print("=== Float values that VARY between files AND are in physical ranges ===")
print(f"{'off':>6}  {'label':>5}  " + "  ".join(f"{f.name[11:19]:>10}" for f in files))

found = []
for off in range(130, 2470, 2):   # try every 2 bytes to catch non-aligned floats
    vals = []
    labels = []
    for data in all_data:
        if off + 4 <= len(data):
            v = struct.unpack_from("<f", data, off)[0]
            vals.append(v)
            labels.append(in_any_range(v))
        else:
            vals.append(None)
            labels.append(None)

    # All values must be in a plausible range
    if not all(l is not None for l in labels):
        continue
    # Must have same range label
    if len(set(l for l in labels)) != 1:
        continue
    label = labels[0]
    # Values must vary (not all identical) - it's a measurement
    if len(set(f"{v:.3f}" for v in vals)) == 1:
        continue

    found.append((off, label, vals))

for off, label, vals in found:
    row = "  ".join(f"{v:10.4f}" for v in vals)
    print(f"{off:6d}  {label:>5}  {row}")

if not found:
    print("  (no varying plausible floats found in 2-byte steps)")
    print()
    print("=== Trying fixed-offset block scan around known STC params ===")
    # The STC params at offset 46-82 are constant. The measured params might be
    # at a fixed offset relative to them.
    # Let's look at what's at specific offsets around 126-160
    for off in range(126, 160, 2):
        vals = [struct.unpack_from("<f", d, off)[0] for d in all_data if off+4<=len(d)]
        rng = set(f"{v:.3f}" for v in vals)
        if len(rng) > 1:
            row = "  ".join(f"{v:10.4f}" for v in vals)
            label = in_any_range(vals[0]) or "?"
            print(f"{off:6d}  {label:>5}  {row}")

print()
print("=== Sample of IV curve point data (float pairs every 4 bytes from offset 395) ===")
data = all_data[0]
print(f"File: {files[0].name}")
print(f"{'off':>6}  {'Voltage(?)':>12}  {'Current(?)':>12}")
for i in range(0, 60):
    off = 395 + i * 8
    if off + 8 <= len(data):
        v = struct.unpack_from("<f", data, off)[0]
        c = struct.unpack_from("<f", data, off+4)[0]
        if 0 < v < 60 and 0 < c < 15:
            print(f"{off:6d}  {v:12.4f}  {c:12.4f}")
