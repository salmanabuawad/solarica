"""
PVPM SUI binary parser — v5 (full).
Parses UIKenn0File binaries from PVPM 1540X devices.
Returns device metadata, sensor info, STC module reference values,
IV curve points and derived electrical metrics.
"""
from __future__ import annotations
import math, re, struct
from typing import Any

_ALL_MAGICS = [b"UIKenn%dFile" % i for i in range(7)]

OFFSETS = {
    "format_version":          153,
    "device_model_serial":     160,
    "device_calibration_date": 175,
    "sensor_name":             233,
    "sensor_type":             247,
    "sensor_calibration_date": 280,
    "module_manufacturer":     300,
    "module_part_number":      326,
    "module_technology":       375,
    "module_imp_stc":          388,
    "module_voc_stc":          392,
    "module_isc_stc":          396,
    "module_vmp_stc":          400,
    "module_pmax_stc":         404,
    "module_temp_coeff_current": 416,
    "module_temp_coeff_voltage": 420,
    "module_temp_coeff_power":   424,
    "label_date_short":        2477,
    "label_time":              2486,
    "label_site_name":         2546,
    "label_string_name":       2597,
    "label_timestamp_text":    2648,
    "curve_current_start":     503,
    "curve_current_count":     110,
    "curve_voltage_start":     1475,
    "curve_voltage_count":     130,
}


def _f32(data: bytes, offset: int) -> float | None:
    if offset + 4 > len(data):
        return None
    try:
        v = struct.unpack_from("<f", data, offset)[0]
        return float(v) if math.isfinite(v) else None
    except Exception:
        return None


def _lp_string(data: bytes, offset: int, max_len: int = 120) -> str | None:
    i = offset
    while i < len(data) and data[i] == 0:
        i += 1
    if i >= len(data):
        return None
    length = data[i]
    if length <= 0 or length > max_len or i + 1 + length > len(data):
        return None
    text = data[i + 1: i + 1 + length].decode("latin1", errors="ignore").replace("\x00", "").strip()
    return text or None


def _float_series(data: bytes, start: int, count: int) -> list[float]:
    vals = []
    for i in range(count):
        v = _f32(data, start + i * 4)
        if v is None:
            break
        vals.append(v)
    return vals


def _trim_tail(values: list[float], eps: float = 1e-12) -> list[float]:
    last = -1
    for i, v in enumerate(values):
        if math.isfinite(v) and abs(v) > eps:
            last = i
    return values[: last + 1] if last >= 0 else []


def _extract_curve(data: bytes) -> list[dict[str, float]]:
    current = _trim_tail(_float_series(data, OFFSETS["curve_current_start"], OFFSETS["curve_current_count"]))
    voltage = _trim_tail(_float_series(data, OFFSETS["curve_voltage_start"], OFFSETS["curve_voltage_count"]))
    # Drop leading reversed voltage values (PDF artefact)
    while len(voltage) > 3 and voltage[0] > voltage[1] + 1e-6:
        voltage = voltage[1:]

    points = []
    for u, i in zip(voltage, current):
        if not (math.isfinite(u) and math.isfinite(i)):
            continue
        if u < -1 or i < -1 or u > 2500 or i > 100:
            continue
        points.append({"u_v": round(u, 4), "i_a": round(i, 4), "p_w": round(u * i, 4)})
    return points


def _derive(points: list[dict[str, float]]) -> dict[str, Any]:
    if not points:
        return {}
    mpp = max(points, key=lambda p: p["p_w"])
    voc = max(points, key=lambda p: p["u_v"])
    isc = max(points, key=lambda p: p["i_a"])
    ff = None
    if voc["u_v"] and isc["i_a"]:
        try:
            ff = round(mpp["p_w"] / (voc["u_v"] * isc["i_a"]), 4)
        except ZeroDivisionError:
            pass
    return {
        "voc_v":       round(voc["u_v"], 4),
        "isc_a":       round(isc["i_a"], 4),
        "pmax_w":      round(mpp["p_w"], 4),
        "vmp_v":       round(mpp["u_v"], 4),
        "imp_a":       round(mpp["i_a"], 4),
        "fill_factor": ff,
        "point_count": len(points),
    }


def parse_sui_bytes(data: bytes, file_name: str = "upload.sui") -> dict[str, Any]:
    """
    Parse a PVPM SUI binary.
    Raises ValueError if the magic bytes are not recognised.
    Returns a dict with: file_name, format_version, device, sensor,
    module_reference (STC params), labels, curve, derived.
    """
    if not any(data.startswith(m) for m in _ALL_MAGICS):
        raise ValueError(f"Not a valid PVPM SUI file: {file_name!r}")

    curve = _extract_curve(data)

    return {
        "file_name":      file_name,
        "file_size":      len(data),
        "format_version": _lp_string(data, OFFSETS["format_version"], 20),
        "device": {
            "model_serial":      _lp_string(data, OFFSETS["device_model_serial"], 40),
            "calibration_date":  _lp_string(data, OFFSETS["device_calibration_date"], 20),
        },
        "sensor": {
            "name":             _lp_string(data, OFFSETS["sensor_name"], 60),
            "type":             _lp_string(data, OFFSETS["sensor_type"], 20),
            "calibration_date": _lp_string(data, OFFSETS["sensor_calibration_date"], 20),
        },
        "module_reference": {
            "manufacturer":        _lp_string(data, OFFSETS["module_manufacturer"], 40),
            "part_number":         _lp_string(data, OFFSETS["module_part_number"], 80),
            "technology":          _lp_string(data, OFFSETS["module_technology"], 20),
            "imp_stc_a":           _f32(data, OFFSETS["module_imp_stc"]),
            "voc_stc_v":           _f32(data, OFFSETS["module_voc_stc"]),
            "isc_stc_a":           _f32(data, OFFSETS["module_isc_stc"]),
            "vmp_stc_v":           _f32(data, OFFSETS["module_vmp_stc"]),
            "pmax_stc_w":          _f32(data, OFFSETS["module_pmax_stc"]),
            "temp_coeff_current":  _f32(data, OFFSETS["module_temp_coeff_current"]),
            "temp_coeff_voltage":  _f32(data, OFFSETS["module_temp_coeff_voltage"]),
            "temp_coeff_power":    _f32(data, OFFSETS["module_temp_coeff_power"]),
        },
        "labels": {
            "date_short":      _lp_string(data, OFFSETS["label_date_short"], 20),
            "time":            _lp_string(data, OFFSETS["label_time"], 20),
            "site_name_raw":   _lp_string(data, OFFSETS["label_site_name"], 80),
            "string_name_raw": _lp_string(data, OFFSETS["label_string_name"], 80),
            "timestamp_text":  _lp_string(data, OFFSETS["label_timestamp_text"], 40),
        },
        "curve":   {"point_count": len(curve), "points": curve},
        "derived": _derive(curve),
    }
