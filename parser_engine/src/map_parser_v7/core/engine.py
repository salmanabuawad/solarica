from __future__ import annotations

import re
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from map_parser_v7.core.extractors import extract_dxf_text, extract_pdf_text, optional_ocr_pdf
from map_parser_v7.core.progress import ProgressStore, ProgressTracker
from map_parser_v7.steps.registry import STEPS, resolve_steps
from map_parser_v7.utils.text_patterns import (
    COORD_RE,
    NUMBER_RE,
    PANELS_PER_STRING_RE,
    STRINGS_COUNT_RE,
    _detect_level,
    derive_inverter_groups_from_strings,
    detect_duplicates,
    find_invalid_labels,
    find_inverter_groups,
    find_mppts,
    find_string_labels,
    group_strings,
    missing_indices_for_group,
    sort_key,
)


class ParserEngine:
    def __init__(self, jobs_dir: str = ".map_parser_jobs") -> None:
        self.store = ProgressStore(jobs_dir)

    def run_full(self, files: list[str], force_ocr: bool = False) -> dict[str, Any]:
        return self._run(files=files, target_step=None, force_ocr=force_ocr)

    def run_step(self, step_id: str, files: list[str], resolve_dependencies: bool = True, force_ocr: bool = False) -> dict[str, Any]:
        return self._run(files=files, target_step=step_id if resolve_dependencies else step_id, force_ocr=force_ocr)

    def get_progress(self, job_id: str) -> dict[str, Any]:
        return self.store.load(job_id)

    def _run(self, files: list[str], target_step: str | None, force_ocr: bool) -> dict[str, Any]:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        tracker = ProgressTracker(job_id, STEPS, self.store)
        ctx: dict[str, Any] = {"files": files, "job_id": job_id}
        try:
            step_ids = resolve_steps(target_step)
            for step in STEPS:
                sid = step["id"]
                if sid not in step_ids:
                    tracker.finish(sid, "skipped", "Not required for this run")
                    continue
                tracker.start(sid)
                result = getattr(self, f"step_{sid}")(ctx, force_ocr=force_ocr)
                if isinstance(result, dict):
                    ctx.update(result)
                tracker.finish(sid, result.get("status", "done"), result.get("summary"), result.get("checkpoint_output"), result.get("warnings", []), result.get("errors", []))
            tracker.set_results(self._final_results(ctx))
            tracker.complete()
            return self.store.load(job_id)
        except Exception as exc:
            tracker.fail(str(exc))
            raise

    def step_load_files(self, ctx: dict[str, Any], force_ocr: bool = False) -> dict[str, Any]:
        files = [str(Path(f)) for f in ctx["files"]]
        if not files:
            raise ValueError("No files provided")
        unsupported = [f for f in files if not f.lower().endswith((".pdf", ".dxf"))]
        if unsupported:
            raise ValueError(f"Unsupported files: {unsupported}. Allowed: PDF, DXF")
        ctx["file_kind"] = "pdf" if all(f.lower().endswith(".pdf") for f in files) else "dxf"
        return {"status": "done", "summary": f"Loaded {len(files)} files", "checkpoint_output": {"files": files, "file_kind": ctx['file_kind']}}

    def step_extract_text(self, ctx: dict[str, Any], force_ocr: bool = False) -> dict[str, Any]:
        if ctx["file_kind"] == "pdf":
            extracted = optional_ocr_pdf(ctx["files"]) if force_ocr else extract_pdf_text(ctx["files"])
        else:
            extracted = extract_dxf_text(ctx["files"])
        text = extracted["text"]
        warnings = []
        if not text.strip() and ctx["file_kind"] == "pdf" and not force_ocr:
            extracted = optional_ocr_pdf(ctx["files"])
            text = extracted["text"]
            warnings.append("Primary text extraction was empty, OCR fallback used")
        return {"extracted": extracted, "status": "warning" if warnings else "done", "summary": f"Extracted text from {len(extracted['pages'])} pages", "warnings": warnings, "checkpoint_output": {"pages": len(extracted['pages']), "chars": len(text)}}

    def step_extract_metadata(self, ctx: dict[str, Any], force_ocr: bool = False) -> dict[str, Any]:
        text = ctx["extracted"]["text"]
        md: dict[str, Any] = {}
        md["site_name"] = self._find_first(text, [r"Solar Plant\s+([A-Za-z\- ]+)", r"(Qunitra-FPV)", r"(Hamadiya)"])
        md["country"] = self._find_first(text, [r"Country\s*-\s*([A-Za-z]+)"])
        md["region"] = self._find_first(text, [r"Region\s*/\s*Province\s*-\s*([A-Za-z]+)", r"Region\s*-\s*([A-Za-z]+)"])
        md["coordinates"] = self._find_coords(text)
        md["declared_dc_power_kwp"] = self._find_number_after(text, ["Plant System Rating -", "System Capacity -"]) 
        md["declared_modules"] = self._find_int_after(text, ["Number of Modules -"])
        md["module_wattages"] = self._find_module_watts(text)
        md["declared_modules_per_string"] = self._find_modules_per_string(text)
        md["declared_inverters"] = self._find_int_after(text, ["Strings Inverters -", "String Inverter -"])
        md["inverter_model"] = self._find_first(text, [r"String Inverter\s*-\s*([A-Z0-9\-X]+)", r"Strings Inverters\s*-\s*[0-9]+\s*x\s*([A-Za-z0-9\- ]+)"])
        md["installation"] = {}
        return {"project_metadata": md, "status": "done", "summary": f"Extracted metadata for {md.get('site_name') or 'site'}", "checkpoint_output": md}

    def step_classify_installation(self, ctx: dict[str, Any], force_ocr: bool = False) -> dict[str, Any]:
        text = ctx["extracted"]["text"].lower()
        install = {
            "primary_type": "utility_scale",
            "types": ["utility_scale"],
            "mounting": "ground_mount",
            "structure": "fixed_tables",
            "tracking": {"enabled": False, "type": None},
            "confidence": 0.6,
            "evidence": [],
        }
        if "fpv" in text or "floating" in text:
            install.update({"primary_type": "floating", "types": ["floating", "utility_scale"], "mounting": "fpv", "structure": "floating_platform", "confidence": 0.85})
            install["evidence"].append("FPV / floating keywords")
        if "roof" in text or "rooftop" in text:
            install.update({"primary_type": "rooftop", "types": ["rooftop"], "mounting": "roof_mount", "structure": "roof_arrays", "confidence": 0.8})
            install["evidence"].append("roof keywords")
        if "rotation - +-60 deg" in text or "tracker" in text or "+-60 deg" in text:
            install.update({"mounting": "single_axis_tracker", "structure": "tracker_rows"})
            install["tracking"] = {"enabled": True, "type": "single_axis"}
            if install["primary_type"] == "utility_scale":
                install["types"] = ["utility_scale", "trackers"]
            install["confidence"] = max(install["confidence"], 0.9)
            install["evidence"].append("tracker / +-60 deg / rotation keywords")
        ctx["project_metadata"]["installation"] = install
        return {"status": "done", "summary": f"Classified installation as {install['primary_type']}", "checkpoint_output": install}

    def step_detect_patterns(self, ctx: dict[str, Any], force_ocr: bool = False) -> dict[str, Any]:
        text = ctx["extracted"]["text"]
        strings = find_string_labels(text)
        invalid = find_invalid_labels(text)
        level = _detect_level(strings)
        inv_groups = find_inverter_groups(text, level=level)
        if level == 4:
            str_pattern = "S.<section>.<block>.<inverter>.<string>"
            str_regex   = r"^S\.(\d+)\.(\d+)\.(\d+)\.(\d+)$"
            inv_pattern = "<section>.<block>.<inverter>"
            inv_regex   = r"^(\d+)\.(\d+)\.(\d+)$"
        else:
            str_pattern = "S.<section>.<inverter>.<string>"
            str_regex   = r"^S\.(\d+)\.(\d+)\.(\d+)$"
            inv_pattern = "<section>.<inverter>"
            inv_regex   = r"^(\d+)\.(\d+)$"
        patterns = {
            "level": level,
            "strings": {
                "detected_pattern": str_pattern,
                "regex": str_regex,
                "single_pattern_enforced": True,
                "examples_valid": strings[:5],
                "examples_invalid": invalid[:10],
            },
            "inverters": {
                "detected_pattern": inv_pattern,
                "regex": inv_regex,
                "single_pattern_enforced": True,
                "examples_valid": inv_groups[:5],
                "examples_invalid": invalid[:5],
            },
        }
        return {"naming_patterns": patterns, "string_level": level, "status": "done", "summary": f"Detected {level}-level naming pattern", "checkpoint_output": patterns}

    def step_extract_inverters(self, ctx: dict[str, Any], force_ocr: bool = False) -> dict[str, Any]:
        text = ctx["extracted"]["text"]
        level = ctx.get("string_level", 3)
        string_labels = find_string_labels(text)
        groups_from_text = find_inverter_groups(text, level=level)
        groups_from_strings = derive_inverter_groups_from_strings(string_labels)
        groups = sorted(set(groups_from_text) | set(groups_from_strings), key=sort_key)
        grouped_strings = group_strings(string_labels)
        inverters = []
        for g in groups:
            strs = grouped_strings.get(g, [])
            inverters.append({
                "id": g,
                "label": g,
                "string_count": len(strs),
                "missing_indices": missing_indices_for_group(strs),
            })
        return {"inverters": inverters, "status": "done", "summary": f"Extracted {len(inverters)} inverter groups", "checkpoint_output": {"count": len(inverters), "examples": groups[:10]}}

    def step_extract_strings(self, ctx: dict[str, Any], force_ocr: bool = False) -> dict[str, Any]:
        text = ctx["extracted"]["text"]
        valid = find_string_labels(text)
        invalid = find_invalid_labels(text)
        groups = group_strings(valid)
        strings = {
            "valid_strings": valid,
            "invalid_strings": invalid,
            "duplicates": detect_duplicates(valid),
            "by_inverter": {k: {"count": len(v), "strings": v} for k, v in groups.items()},
        }
        return {"strings": strings, "status": "done", "summary": f"Extracted {len(valid)} valid strings and {len(invalid)} invalid labels", "checkpoint_output": {"valid_count": len(valid), "invalid_count": len(invalid)}}

    def step_extract_mppts(self, ctx: dict[str, Any], force_ocr: bool = False) -> dict[str, Any]:
        text = ctx["extracted"]["text"]
        mppts = find_mppts(text)
        data = {"labels": mppts, "count": len(mppts), "max_mppt_number": max([int(m[4:]) for m in mppts], default=0)}
        return {"mppts": data, "status": "warning" if not mppts else "done", "summary": f"Extracted {len(mppts)} MPPT labels", "checkpoint_output": data, "warnings": ["No clear MPPT labels found"] if not mppts else []}

    def step_extract_ac_equipment(self, ctx: dict[str, Any], force_ocr: bool = False) -> dict[str, Any]:
        text = ctx["extracted"]["text"]
        equipment = []
        for label in ["RMU", "ICB", "SCADA", "PLC", "AUX", "TRAFO", "Transformer", "PCS", "MVS", "MV Room", "Disconnector"]:
            if label.lower() in text.lower():
                equipment.append(label)
        data = {"items": sorted(set(equipment))}
        return {"ac_equipment": data, "status": "done", "summary": f"Detected {len(data['items'])} AC equipment labels", "checkpoint_output": data}

    def step_extract_batteries(self, ctx: dict[str, Any], force_ocr: bool = False) -> dict[str, Any]:
        text = ctx["extracted"]["text"]
        data = {
            "has_battery": any(k in text.lower() for k in ["battery", "bess", "storage"]),
            "storage_capacity_mwh": self._find_number_after(text, ["Storage Capacity -", "BESS kWh BoL -"]),
            "labels": [k for k in ["BESS", "Battery", "Storage Station", "PCS"] if k.lower() in text.lower()],
        }
        return {"batteries": data, "status": "done", "summary": "Extracted battery/storage data", "checkpoint_output": data}

    def step_extract_simple_layout(self, ctx: dict[str, Any], force_ocr: bool = False) -> dict[str, Any]:
        pages_out = []
        valid_set = set(ctx["strings"]["valid_strings"])
        inv_set = {inv["id"] for inv in ctx["inverters"]}
        for p in ctx["extracted"]["pages"]:
            page_items_strings = []
            page_items_inverters = []
            words = p.get("words", [])
            if words:
                pw = max(float(w.get("page_width", 1.0)) for w in words) or 1.0
                ph = max(float(w.get("page_height", 1.0)) for w in words) or 1.0
                for w in words:
                    txt = str(w.get("text", "")).strip()
                    norm_txt = txt
                    if re.match(r"^S\d+\.\d+\.\d+(\.\d+)?$", txt):
                        norm_txt = "S." + txt[1:]
                    if norm_txt in valid_set:
                        page_items_strings.append(self._word_to_rect(norm_txt, w, pw, ph, "string"))
                    elif txt in inv_set:
                        page_items_inverters.append(self._word_to_rect(txt, w, pw, ph, "inverter"))
            # derive group bounds
            group_bounds = []
            by_group: dict[str, list[dict[str, Any]]] = {}
            level = ctx.get("string_level", 3)
            for s in page_items_strings:
                parts = s["id"].split(".")
                if level == 4 and len(parts) >= 5:
                    gid = f"{parts[1]}.{parts[2]}.{parts[3]}"
                else:
                    gid = f"{parts[1]}.{parts[2]}"
                by_group.setdefault(gid, []).append(s)
            for gid, arr in by_group.items():
                xs = [a["x"] for a in arr]
                ys = [a["y"] for a in arr]
                x2s = [a["x"] + a["w"] for a in arr]
                y2s = [a["y"] + a["h"] for a in arr]
                group_bounds.append({"inverter_id": gid, "x": min(xs), "y": min(ys), "w": max(x2s)-min(xs), "h": max(y2s)-min(ys), "string_count": len(arr)})
            pages_out.append({"page_number": p["page_number"], "inverters": page_items_inverters, "strings": page_items_strings, "group_bounds": group_bounds})
        data = {"coordinate_system": "page_normalized_top_left", "pages": pages_out}
        return {"simple_layout": data, "status": "done", "summary": "Built simple relative layout", "checkpoint_output": {"pages": len(pages_out), "strings": sum(len(p['strings']) for p in pages_out), "inverters": sum(len(p['inverters']) for p in pages_out)}}

    def step_assign_profiles(self, ctx: dict[str, Any], force_ocr: bool = False) -> dict[str, Any]:
        text = ctx["extracted"]["text"]
        allowed_spi = sorted({int(x) for x in STRINGS_COUNT_RE.findall(text)} or {20, 21, 22})
        allowed_mps = sorted({int(x) for x in PANELS_PER_STRING_RE.findall(text)} or {ctx["project_metadata"].get("declared_modules_per_string") or 27})
        profiles = {
            "allowed_strings_per_inverter": allowed_spi,
            "allowed_modules_per_string": allowed_mps,
            "inverter_profiles": [{"inverter_id": inv["id"], "expected_string_count": inv["string_count"] if inv["string_count"] in allowed_spi else None} for inv in ctx["inverters"]],
        }
        return {"profiles": profiles, "status": "done", "summary": "Assigned validation profiles", "checkpoint_output": profiles}

    def step_validate_strings(self, ctx: dict[str, Any], force_ocr: bool = False) -> dict[str, Any]:
        allowed = set(ctx["profiles"]["allowed_strings_per_inverter"])
        by_inv = ctx["strings"]["by_inverter"]
        missing = []
        count_issues = []
        for gid, info in by_inv.items():
            ss = info["strings"]
            gap = missing_indices_for_group(ss)
            if gap:
                missing.append({"inverter": gid, "missing_strings": gap})
            if info["count"] not in allowed:
                count_issues.append({"inverter": gid, "count": info["count"], "allowed": sorted(allowed)})
        val = {
            "duplicates": ctx["strings"]["duplicates"],
            "invalid_strings": ctx["strings"]["invalid_strings"],
            "missing_by_inverter": missing,
            "count_issues": count_issues,
            "status": "OK" if not (ctx["strings"]["duplicates"] or ctx["strings"]["invalid_strings"] or missing or count_issues) else "ISSUES_FOUND",
        }
        return {"string_validation": val, "status": "warning" if val['status'] != 'OK' else "done", "summary": f"Validated strings; {len(missing)} gap groups, {len(count_issues)} count issues", "checkpoint_output": val, "warnings": ["String issues found"] if val['status'] != 'OK' else []}

    def step_validate_output(self, ctx: dict[str, Any], force_ocr: bool = False) -> dict[str, Any]:
        md = ctx["project_metadata"]
        strings_count = len(ctx["strings"]["valid_strings"])
        modules_per_string = md.get("declared_modules_per_string") or (ctx["profiles"]["allowed_modules_per_string"][0] if ctx.get("profiles") else None)
        calc_modules = strings_count * modules_per_string if modules_per_string else None
        wattages = md.get("module_wattages") or []
        calc_kwp = None
        flags = []
        if md.get("declared_modules") and wattages:
            if len(wattages) == 1:
                calc_kwp = round((md["declared_modules"] * wattages[0]) / 1000, 5)
            elif md.get("module_mix"):
                calc_kwp = round(sum(count * watt for count, watt in md["module_mix"]) / 1000, 5)
        elif calc_modules and wattages:
            calc_kwp = round((calc_modules * wattages[0]) / 1000, 5)
        declared = md.get("declared_dc_power_kwp")
        power_match = declared is None or calc_kwp is None or abs(float(declared) - float(calc_kwp)) < 0.5
        if not power_match:
            flags.append("declared_output_mismatch")
        modules_match = md.get("declared_modules") is None or calc_modules is None or int(md["declared_modules"]) == int(calc_modules)
        if not modules_match:
            flags.append("module_count_mismatch")
        result = {
            "declared_dc_power_kwp": declared,
            "calculated_dc_power_kwp": calc_kwp,
            "power_match": power_match,
            "declared_modules": md.get("declared_modules"),
            "calculated_modules": calc_modules,
            "declared_strings": strings_count,
            "calculated_strings": strings_count,
            "declared_modules_per_string": modules_per_string,
            "allowed_modules_per_string": ctx["profiles"]["allowed_modules_per_string"],
            "declared_inverters": md.get("declared_inverters"),
            "parsed_inverters": len(ctx["inverters"]),
            "allowed_strings_per_inverter": ctx["profiles"]["allowed_strings_per_inverter"],
            "avg_strings_per_inverter": round(strings_count / len(ctx["inverters"]), 3) if ctx["inverters"] else None,
            "flags": flags,
            "status": "OK" if not flags else "ISSUES_FOUND",
        }
        return {"design_validation": result, "status": "warning" if flags else "done", "summary": "Validated design against declared output", "checkpoint_output": result, "warnings": flags}

    def step_build_report(self, ctx: dict[str, Any], force_ocr: bool = False) -> dict[str, Any]:
        return {"status": "done", "summary": "Final report assembled", "checkpoint_output": self._final_results(ctx)}

    def _final_results(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "project_metadata": ctx.get("project_metadata", {}),
            "naming_patterns": ctx.get("naming_patterns", {}),
            "inverters": ctx.get("inverters", []),
            "strings": ctx.get("strings", {}),
            "mppts": ctx.get("mppts", {}),
            "ac_equipment": ctx.get("ac_equipment", {}),
            "batteries": ctx.get("batteries", {}),
            "simple_layout": ctx.get("simple_layout", {}),
            "profiles": ctx.get("profiles", {}),
            "string_validation": ctx.get("string_validation", {}),
            "design_validation": ctx.get("design_validation", {}),
        }

    @staticmethod
    def _word_to_rect(label: str, w: dict[str, Any], pw: float, ph: float, kind: str) -> dict[str, Any]:
        x0, y0, x1, y1 = float(w.get("x0", 0)), float(w.get("top", 0)), float(w.get("x1", 0)), float(w.get("bottom", 0))
        x, y, ww, hh = x0 / pw, y0 / ph, max((x1 - x0) / pw, 0.001), max((y1 - y0) / ph, 0.001)
        return {"id": label, "label": label, "kind": kind, "shape": "rectangle", "x": x, "y": y, "w": ww, "h": hh, "cx": x + ww / 2, "cy": y + hh / 2}

    @staticmethod
    def _find_first(text: str, patterns: list[str]) -> str | None:
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None

    @staticmethod
    def _find_number_after(text: str, prefixes: list[str]) -> float | None:
        for prefix in prefixes:
            m = re.search(re.escape(prefix) + r"\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)", text, re.IGNORECASE)
            if m:
                return float(m.group(1).replace(",", ""))
        return None

    @staticmethod
    def _find_int_after(text: str, prefixes: list[str]) -> int | None:
        val = ParserEngine._find_number_after(text, prefixes)
        return int(val) if val is not None else None

    @staticmethod
    def _find_modules_per_string(text: str) -> int | None:
        vals = [int(v) for v in PANELS_PER_STRING_RE.findall(text)]
        return vals[0] if vals else None

    @staticmethod
    def _find_module_watts(text: str) -> list[int]:
        watts = sorted({int(x) for x in re.findall(r"\b(5\d\d|6[01]\d|620)W[pP]?\b", text)})
        # Mixed module sections like TYPE xxx - 17170 ... 610W and TYPE ... 2268 ... 620W
        return watts

    @staticmethod
    def _find_coords(text: str):
        m = COORD_RE.search(text)
        if not m:
            return None
        return {"lat": m.group(1).strip(), "lon": m.group(2).strip()}
