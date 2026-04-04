"""Text / label utilities for inverter ordering and pattern hints."""


def sort_key(label: str) -> tuple[int, ...]:
    """Sort inverter keys such as '1.16', '2.12', '10.3' numerically by segment."""
    parts = str(label).split(".")
    out: list[int] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        try:
            out.append(int(p, 10))
        except ValueError:
            out.append(10**9)
    return tuple(out)


def _detect_level(_sample: str) -> int:
    """Reserved for string template depth detection (3 vs 4 segment codes)."""
    return 3
