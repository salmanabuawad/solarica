from __future__ import annotations

import argparse
import json
import math
import re
import struct
from pathlib import Path
from typing import Any


class SUIParseError(Exception):
    pass


def f32(data: bytes, offset: int) -> float:
    return struct.unpack_from('<f', data, offset)[0]


def read_lp_string(data: bytes, offset: int, max_len: int = 120, skip_nuls: bool = True) -> tuple[str, int]:
    """
    Read a length-prefixed string from the binary blob.
    Observed SUI samples store many strings as: [len][bytes...], often with leading NUL padding.
    """
    i = offset
    if skip_nuls:
        while i < len(data) and data[i] == 0:
            i += 1
    if i >= len(data):
        raise SUIParseError(f'Offset out of range: {offset}')

    length = data[i]
    if length <= 0 or length > max_len or i + 1 + length > len(data):
        raise SUIParseError(f'Invalid LP string length at {i}: {length}')

    raw = data[i + 1 : i + 1 + length]
    return raw.decode('latin1', errors='replace').strip(), i + 1 + length


def extract_curve(data: bytes, start: int, count: int) -> list[float]:
    out: list[float] = []
    for i in range(count):
        off = start + i * 4
        if off + 4 > len(data):
            break
        out.append(f32(data, off))
    return out


def trim_tail(values: list[float]) -> list[float]:
    last = -1
    for i, v in enumerate(values):
        if math.isfinite(v) and abs(v) > 1e-12:
            last = i
    return values[: last + 1] if last >= 0 else []


def safe_lp(data: bytes, offset: int) -> str | None:
    try:
        value, _ = read_lp_string(data, offset)
        return value
    except Exception:
        return None


def ascii_strings(data: bytes, min_len: int = 4) -> list[str]:
    found = re.findall(rb'[ -~]{%d,}' % min_len, data)
    return [s.decode('latin1', errors='replace') for s in found]


# Sample-derived offsets from provided PVPMdisp/Curvealyzer .SUI files.
OFFSETS = {
    'format_version': 153,
    'device': 160,
    'device_calibration_date': 175,
    'sensor_name': 233,
    'sensor_type': 247,
    'sensor_calibration_date': 280,
    'module_manufacturer': 300,
    'module_type': 326,
    'module_technology': 375,
    'module_imp_stc': 388,
    'module_voc_stc': 392,
    'module_isc_stc': 396,
    'module_vmp_stc': 400,
    'module_pmax_stc': 404,
    'module_tc_current': 416,
    'module_tc_voltage': 420,
    'module_tc_power': 424,
    'curve_current_start': 503,
    'curve_voltage_start': 1475,
    'label_date_short': 2477,
    'label_time': 2486,
    'label_code_1': 2546,
    'label_code_2': 2597,
    'label_timestamp_text': 2648,
}


def parse_sui(path: str | Path, include_curve: bool = True, include_ascii_dump: bool = False) -> dict[str, Any]:
    path = Path(path)
    data = path.read_bytes()

    if not data.startswith(b'UIKenn0File'):
        raise SUIParseError('Unrecognized SUI header')

    out: dict[str, Any] = {
        'file_name': path.name,
        'file_size': len(data),
        'format': 'UIKenn0File',
    }

    version = safe_lp(data, OFFSETS['format_version'])
    if version:
        out['format_version'] = version

    device = safe_lp(data, OFFSETS['device'])
    device_cal = safe_lp(data, OFFSETS['device_calibration_date'])
    if device or device_cal:
        out['device'] = {
            'model_serial': device,
            'calibration_date': device_cal,
        }

    sensor_name = safe_lp(data, OFFSETS['sensor_name'])
    sensor_type = safe_lp(data, OFFSETS['sensor_type'])
    sensor_cal = safe_lp(data, OFFSETS['sensor_calibration_date'])
    if sensor_name or sensor_type or sensor_cal:
        out['sensor'] = {
            'name': sensor_name,
            'type': sensor_type,
            'calibration_date': sensor_cal,
        }

    module_manufacturer = safe_lp(data, OFFSETS['module_manufacturer'])
    module_type = safe_lp(data, OFFSETS['module_type'])
    module_technology = safe_lp(data, OFFSETS['module_technology'])
    if module_manufacturer or module_type or module_technology:
        out['module'] = {
            'manufacturer': module_manufacturer,
            'type': module_type,
            'technology': module_technology,
            'imp_stc': f32(data, OFFSETS['module_imp_stc']),
            'voc_stc': f32(data, OFFSETS['module_voc_stc']),
            'isc_stc': f32(data, OFFSETS['module_isc_stc']),
            'vmp_stc': f32(data, OFFSETS['module_vmp_stc']),
            'pmax_stc': f32(data, OFFSETS['module_pmax_stc']),
            'temp_coeff_current': f32(data, OFFSETS['module_tc_current']),
            'temp_coeff_voltage': f32(data, OFFSETS['module_tc_voltage']),
            'temp_coeff_power': f32(data, OFFSETS['module_tc_power']),
        }

    date_short = safe_lp(data, OFFSETS['label_date_short'])
    time_text = safe_lp(data, OFFSETS['label_time'])
    code1 = safe_lp(data, OFFSETS['label_code_1'])
    code2 = safe_lp(data, OFFSETS['label_code_2'])
    timestamp_text = safe_lp(data, OFFSETS['label_timestamp_text'])
    if any([date_short, time_text, code1, code2, timestamp_text]):
        out['labels'] = {
            'date_short': date_short,
            'time': time_text,
            'code_1': code1,
            'code_2': code2,
            'timestamp_text': timestamp_text,
        }

    if include_curve:
        current = trim_tail(extract_curve(data, OFFSETS['curve_current_start'], 110))
        voltage = trim_tail(extract_curve(data, OFFSETS['curve_voltage_start'], 130))

        if current and voltage:
            while len(voltage) > 5 and voltage[0] > voltage[1] + 1e-6:
                voltage = voltage[1:]

            n = min(len(current), len(voltage))
            points = []
            for i in range(n):
                u = float(voltage[i])
                c = float(current[i])
                points.append({'u_v': u, 'i_a': c, 'p_w': u * c})

            out['curve'] = {
                'point_count': n,
                'points': points,
            }

    if include_ascii_dump:
        out['ascii_strings'] = ascii_strings(data)

    return out


def main() -> None:
    parser = argparse.ArgumentParser(description='Best-effort parser for PVPMdisp/Curvealyzer .SUI files')
    parser.add_argument('input_file', help='Path to .SUI file')
    parser.add_argument('-o', '--output', help='Write JSON output to this file')
    parser.add_argument('--no-curve', action='store_true', help='Skip curve extraction')
    parser.add_argument('--ascii-dump', action='store_true', help='Include readable ASCII strings found in the file')
    args = parser.parse_args()

    parsed = parse_sui(
        args.input_file,
        include_curve=not args.no_curve,
        include_ascii_dump=args.ascii_dump,
    )
    text = json.dumps(parsed, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(text, encoding='utf-8')
    else:
        print(text)


if __name__ == '__main__':
    main()
