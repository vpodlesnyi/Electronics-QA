#!/usr/bin/env python3
"""
process_input.py — Orchestrator for the ltspice-symbol-creation skill.

Modes:
  --scan                Inventory INPUT/SYMBOL/, print JSON.
  --generate <path> --model <NAME>
                        Run full per-model pipeline. Writes to
                        OUTPUT/SYMBOL/<NAME>/.
  --all                 Run --generate for every file with one unambiguous
                        candidate.

Other flags:
  --input-dir <path>    Override INPUT/SYMBOL location.
  --output-dir <path>   Override OUTPUT/SYMBOL location.
  --part-type <tag>     Override detected part type.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent

SUPPORTED_EXTS = {
    ".lib", ".sub", ".cir", ".ckt", ".mod", ".mdl",
    ".sp", ".spi", ".spice", ".net", ".inc", ".txt", ".asy",
}


def slug(name):
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)


def detect_part_type(model):
    name = model.get("name", "").upper()
    pins = [p.upper() for p in model.get("pins", [])]
    pin_set = set(pins)
    mt = model.get("type", "").upper()
    if mt == "D":
        if "ZENER" in name or "VZ" in (model.get("body") or "").upper():
            return "zener"
        if "TVS" in name:
            return "tvs"
        return "diode"
    if mt == "NPN":
        return "npn"
    if mt == "PNP":
        return "pnp"
    if mt == "NMOS":
        return "nmos"
    if mt == "PMOS":
        return "pmos"
    if mt == "NJF":
        return "njf"
    if mt == "PJF":
        return "pjf"
    has_plus = any(p in pin_set for p in ("+IN", "IN+", "INP", "VINP", "NONINV"))
    has_minus = any(p in pin_set for p in ("-IN", "IN-", "INN", "VINM", "INV"))
    has_out = any(p in pin_set for p in ("OUT", "OUTPUT", "VOUT", "OUTA", "OUTB"))
    if has_plus and has_minus and has_out:
        if "COMP" in name or "CMP" in name:
            return "comparator"
        return "opamp"
    if pins == ["A", "K"] or pins == ["AN", "CA"] or pins == ["ANODE", "CATHODE"]:
        return "diode"
    if {"D", "G", "S"}.issubset(pin_set) and len(pins) <= 4:
        return "nmos"
    if {"C", "B", "E"}.issubset(pin_set) and len(pins) <= 4:
        return "npn"
    return "generic"


def confidence_for_part_type(model, part_type):
    if model.get("kind") == "model":
        return "high"
    if part_type == "generic":
        return "low"
    pins = [p.upper() for p in model.get("pins", [])]
    pin_set = set(pins)
    if part_type == "opamp":
        canonical = (
            {"+IN", "-IN", "V+", "V-", "OUT"}.issubset(pin_set) or
            {"IN+", "IN-", "VCC", "VEE", "OUT"}.issubset(pin_set)
        )
        return "high" if canonical else "medium"
    return "medium"


def cmd_scan(input_dir):
    items = []
    if not input_dir.exists():
        json.dump({"input_dir": str(input_dir), "exists": False, "files": []},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    for fp in sorted(input_dir.iterdir()):
        if not fp.is_file():
            continue
        ext = fp.suffix.lower()
        if ext == ".zip":
            with zipfile.ZipFile(fp) as zf:
                names = zf.namelist()
            items.append({"path": str(fp), "type": "archive", "contents": names})
            continue
        if ext not in SUPPORTED_EXTS:
            items.append({"path": str(fp), "type": "ignored",
                          "reason": f"extension {ext} not in supported set"})
            continue
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "parse_spice.py"),
             str(fp), "--no-includes"],
            capture_output=True, text=True,
        )
        try:
            parsed = json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError:
            parsed = {"parse_error": result.stdout, "stderr": result.stderr}
        items.append({"path": str(fp), "type": "model_file", "parsed": parsed})
    json.dump({"input_dir": str(input_dir), "exists": True, "files": items},
              sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _emit_failed(output_dir, model_name, input_path, reason, parsed):
    sub = output_dir / slug(model_name)
    sub.mkdir(parents=True, exist_ok=True)
    report = sub / f"{slug(model_name)}_symbol_report.md"
    body = (
        f"# Symbol generation report - {model_name}\n\n"
        f"**Generated:** {dt.datetime.now().isoformat(timespec='seconds')}\n"
        f"**Source file:** `{input_path}` (preserved unchanged)\n"
        f"**Output folder:** `{sub}`\n"
        f"**Status:** `FAILED`\n\n"
        f"## Reason\n\n{reason}\n\n"
        f"## Parser output\n\n```json\n"
        f"{json.dumps(parsed, indent=2, default=str)[:4000]}\n```\n\n"
        f"Status: FAILED\n"
    )
    report.write_text(body)
    json.dump({"status": "FAILED", "reason": reason, "report": str(report)},
              sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 1


def _render_usage(name, lib_filename, pin_names):
    lines = [
        f"=== {name} - LTspice usage ===",
        "",
        "1. Copy these files into the same folder as your LTspice schematic,",
        "   OR into your user library folder:",
        f"     - {name}.asy",
        f"     - {lib_filename}",
        "",
        "2. In LTspice, press F2, then 'Top Directory', and navigate to the",
        f"   folder containing the .asy file. Find {name} in the symbol list.",
        "",
        "3. Add this directive to your schematic so the model is loaded:",
        f"     .include {lib_filename}",
        "   (or .lib if you prefer)",
        "",
        "4. Pin map (declaration order = SpiceOrder):",
    ]
    for i, n in enumerate(pin_names, start=1):
        lines.append(f"     {i}. {n}")
    lines += ["", "5. Wire pins, run.", ""]
    return "\n".join(lines)


def _render_report(*, model_name, kind, parsed, spec, val_json,
                   norm_changes, pspice_warnings, missing_includes,
                   status, input_path, out_subdir, confidence):
    pins = spec.get("pins", [])
    out = []
    out.append(f"# Symbol generation report - {model_name}\n")
    out.append(f"**Generated:** {dt.datetime.now().isoformat(timespec='seconds')}")
    out.append(f"**Source file:** `{input_path}` (preserved unchanged)")
    out.append(f"**Output folder:** `{out_subdir}`")
    out.append(f"**Status:** `{status}`\n")

    out.append("## 1. Input scan\n")
    out.append(f"- Detected dialect: `{parsed.get('dialect','unknown')}`")
    out.append(f"- Encryption flags: {parsed.get('encryption') or 'none'}")
    out.append(f"- Encoding used: `{parsed.get('encoding','?')}`\n")

    out.append("## 2. Detected model\n")
    out.append(f"- Model name: `{model_name}`")
    out.append(f"- Model type: `{kind}`")
    if kind == "model":
        m = next((m for m in parsed.get("models", [])
                  if m["name"] == model_name), {})
        out.append(f"- Primitive: `{m.get('type','?')}`")
    out.append(f"- Inferred part type: `{spec.get('part_type','generic')}`")
    out.append(f"- Confidence: {confidence}\n")

    out.append("## 3. Pin map\n")
    out.append("| # | Pin name |")
    out.append("|---|---|")
    for i, p in enumerate(pins, start=1):
        out.append(f"| {i} | `{p['name']}` |")
    out.append("")

    out.append("## 4. Output files\n")
    out.append(f"- `{model_name}.asy` - LTspice symbol")
    out.append(f"- `{model_name}.lib` - Normalized model file")
    out.append(f"- `{model_name}_test.asc` - Minimal test schematic")
    out.append(f"- `{model_name}_usage_example.txt` - Plain-text usage notes")
    out.append(f"- `{model_name}_symbol_report.md` - This file\n")

    out.append("## 5. LTspice attributes used\n")
    out.append("- `SymbolType`: CELL")
    out.append(f"- `Prefix`: `{spec.get('prefix','?')}`")
    if kind == "subckt":
        out.append(f"- `SpiceModel`: `{model_name}`")
    else:
        out.append(f"- `Value`: `{model_name}`")
    out.append(f"- `ModelFile`: `{spec.get('model_file','')}`\n")

    out.append("## 6. Compatibility notes\n")
    if norm_changes:
        for c in norm_changes:
            out.append(f"- Line {c['line']}: rule `{c['rule']}` applied.")
    else:
        out.append("- No rewrites applied; the original model was already LTspice-compatible.")
    out.append("")

    out.append("## 7. PSpice / dialect warnings\n")
    if pspice_warnings:
        for w in pspice_warnings[:50]:
            out.append(f"- Line {w['line']}: `{w['match']}` - review `{w['text']}`.")
    else:
        out.append("- None.")
    out.append("")

    out.append("## 8. Dependencies\n")
    incs = parsed.get("includes", [])
    if incs:
        for i in incs:
            st = i.get("status", "unknown")
            out.append(f"- `{i.get('directive','include')} {i.get('target','?')}` - {st}")
    else:
        out.append("- None.")
    out.append("")

    out.append("## 9. Validation checklist\n")
    for c in val_json.get("checks", []):
        mark = "x" if c["passed"] else " "
        out.append(f"- [{mark}] {c['text']} - {c.get('evidence','')}")
    summary = val_json.get("summary", {})
    out.append(f"\n_Summary: {summary.get('passed',0)}/{summary.get('total',0)} checks passed._\n")

    out.append("## 10. Usage instructions\n")
    out.append(f"See `{model_name}_usage_example.txt` for the step-by-step.")
    out.append(f"In short: copy the .asy and .lib next to your schematic, ")
    out.append(f"add `.include {model_name}.lib` to the schematic, place the ")
    out.append(f"symbol, wire by pin name.\n")

    out.append("## 11. Manual actions required\n")
    actions = []
    if missing_includes:
        for m in missing_includes:
            actions.append(f"Locate and provide missing include: `{m['target']}`")
    if pspice_warnings:
        actions.append("Review PSpice warnings above; verify simulation matches expected behavior.")
    if not actions:
        actions.append("None.")
    for a in actions:
        out.append(f"- {a}")
    out.append("")

    out.append("## 12. Final status\n")
    out.append(f"`{status}`\n")
    out.append(f"Status: {status}\n")
    return "\n".join(out)


def cmd_generate(input_path, model_name, output_dir, part_type_override):
    parse = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "parse_spice.py"), str(input_path)],
        capture_output=True, text=True,
    )
    try:
        parsed = json.loads(parse.stdout)
    except Exception:
        parsed = {"error": "parse failed - non-json output",
                  "stdout": parse.stdout, "stderr": parse.stderr}
    if parse.returncode == 1:
        return _emit_failed(output_dir, model_name, input_path,
                            "parse failed (exit 1)", parsed)

    matched = None
    kind = ""
    for sub in parsed.get("subckts", []):
        if sub["name"].lower() == model_name.lower():
            matched = sub
            kind = "subckt"
            break
    if matched is None:
        for mod in parsed.get("models", []):
            if mod["name"].lower() == model_name.lower():
                matched = mod
                kind = "model"
                break
    if matched is None:
        return _emit_failed(output_dir, model_name, input_path,
                            f"model {model_name!r} not found in file", parsed)

    out_subdir = output_dir / slug(matched["name"])
    out_subdir.mkdir(parents=True, exist_ok=True)
    lib_filename = f"{slug(matched['name'])}.lib"
    pins = [{"name": p} for p in matched.get("pins", [])] if kind == "subckt" else []

    if kind == "model":
        prim = matched.get("type", "").upper()
        if prim == "D":
            pins = [{"name": "A"}, {"name": "K"}]
        elif prim in ("NPN", "PNP"):
            pins = [{"name": "C"}, {"name": "B"}, {"name": "E"}]
        elif prim in ("NMOS", "PMOS"):
            pins = [{"name": "D"}, {"name": "G"}, {"name": "S"}]
        elif prim in ("NJF", "PJF"):
            pins = [{"name": "D"}, {"name": "G"}, {"name": "S"}]

    prefix = "X" if kind == "subckt" else matched.get("prefix", "?")
    part_type = part_type_override or detect_part_type(matched)
    confidence = confidence_for_part_type(matched, part_type)

    spec = {
        "name": matched["name"], "kind": kind, "prefix": prefix,
        "part_type": part_type, "model_file": lib_filename,
        "lib_filename": lib_filename, "pins": pins, "description": "",
    }

    asy_path = out_subdir / f"{slug(matched['name'])}.asy"
    spec_json = json.dumps(spec)
    r = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "gen_asy.py"), "--out", str(asy_path)],
        input=spec_json, capture_output=True, text=True,
    )
    if r.returncode != 0:
        return _emit_failed(output_dir, model_name, input_path,
                            f"gen_asy failed: {r.stderr}", parsed)

    lib_path = out_subdir / lib_filename
    norm = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "normalize_lib.py"),
         "--in", str(input_path), "--out", str(lib_path)],
        capture_output=True, text=True,
    )
    norm_summary = {}
    if norm.returncode == 0 and norm.stdout.strip():
        try:
            norm_summary = json.loads(norm.stdout)
        except Exception:
            norm_summary = {"raw": norm.stdout}

    test_path = out_subdir / f"{slug(matched['name'])}_test.asc"
    subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "gen_test_asc.py"),
         "--out", str(test_path)],
        input=spec_json, capture_output=True, text=True,
    )

    usage_path = out_subdir / f"{slug(matched['name'])}_usage_example.txt"
    pin_names = [p["name"] for p in pins]
    usage_path.write_text(_render_usage(matched["name"], lib_filename, pin_names))

    # Write placeholder report so validate's "report exists" check passes
    report_path = out_subdir / f"{slug(matched['name'])}_symbol_report.md"
    report_path.write_text(
        f"# Symbol generation report - {matched['name']}\n\n"
        f"_Placeholder - being filled in._\n\nStatus: PENDING\n"
    )

    val_args = [sys.executable, str(SCRIPT_DIR / "validate.py"),
                "--asy", str(asy_path), "--lib", str(lib_path),
                "--model", matched["name"],
                "--report", str(report_path), "--usage", str(usage_path)]
    if kind == "subckt":
        val_args += ["--declared-pins", ",".join(matched["pins"])]

    val = subprocess.run(val_args, capture_output=True, text=True)
    val_json = {}
    try:
        val_json = json.loads(val.stdout)
    except Exception:
        val_json = {"raw": val.stdout, "stderr": val.stderr}

    structural_check_names = {
        "Every PIN has a PinName attribute",
        "Every PIN has a SpiceOrder attribute",
        "SpiceOrder values are unique",
        "SpiceOrder values are 1..N contiguous",
        "SpiceOrder order matches .SUBCKT declaration order",
        "Symbol Prefix is set and is a valid SPICE letter",
        "Subcircuit symbol uses Prefix X",
        "SpiceModel/Value names a model that exists in the .lib",
        "No absolute filesystem paths in .asy",
        "ModelFile attribute is a bare filename (no path separators)",
    }
    structural_failed = any(
        not c["passed"] for c in val_json.get("checks", [])
        if c["text"] in structural_check_names
    )

    pspice_warnings = parsed.get("warnings", [])
    norm_changes = norm_summary.get("changes", [])
    missing_includes = [i for i in parsed.get("includes", [])
                        if i.get("status") == "missing"]
    if structural_failed:
        status = "NEEDS_MANUAL_REVIEW"
    elif missing_includes:
        status = "NEEDS_MANUAL_REVIEW"
    elif pspice_warnings:
        status = "READY_WITH_WARNINGS"
    elif norm_changes:
        status = "READY_WITH_WARNINGS"
    else:
        status = "READY"

    report_path.write_text(_render_report(
        model_name=matched["name"], kind=kind, parsed=parsed,
        spec=spec, val_json=val_json, norm_changes=norm_changes,
        pspice_warnings=pspice_warnings,
        missing_includes=missing_includes, status=status,
        input_path=input_path, out_subdir=out_subdir,
        confidence=confidence,
    ))

    summary = {
        "model": matched["name"], "kind": kind, "part_type": part_type,
        "confidence": confidence, "output_dir": str(out_subdir),
        "files": {
            "asy": str(asy_path), "lib": str(lib_path),
            "test_asc": str(test_path), "report": str(report_path),
            "usage": str(usage_path),
        },
        "validation": val_json, "status": status,
    }
    json.dump(summary, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if status in ("READY", "READY_WITH_WARNINGS") else 1


def cmd_all(input_dir, output_dir, part_type_override):
    if not input_dir.exists():
        print(f"Input directory does not exist: {input_dir}", file=sys.stderr)
        return 1
    n_done, n_skipped, n_failed = 0, 0, 0
    summary = []
    for fp in sorted(input_dir.iterdir()):
        if not fp.is_file() or fp.suffix.lower() not in SUPPORTED_EXTS:
            continue
        r = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "parse_spice.py"),
             str(fp), "--no-includes"],
            capture_output=True, text=True,
        )
        try:
            parsed = json.loads(r.stdout)
        except Exception:
            n_failed += 1
            continue
        candidates = [s["name"] for s in parsed.get("subckts", [])] + \
            [m["name"] for m in parsed.get("models", [])]
        if len(candidates) == 0:
            n_failed += 1
            summary.append({"file": str(fp), "result": "no model definitions"})
            continue
        if len(candidates) > 1:
            n_skipped += 1
            summary.append({
                "file": str(fp),
                "result": "multiple candidates - rerun with --generate --model",
                "candidates": candidates,
            })
            continue
        rc = cmd_generate(fp, candidates[0], output_dir, part_type_override)
        n_done += (rc == 0)
        n_failed += (rc != 0)
        summary.append({"file": str(fp), "model": candidates[0], "exit_code": rc})
    json.dump({"done": n_done, "skipped": n_skipped, "failed": n_failed,
               "details": summary}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if n_failed == 0 else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--generate", help="Path to input file")
    ap.add_argument("--model", help="Model name to generate (used with --generate)")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--input-dir", default="INPUT/SYMBOL")
    ap.add_argument("--output-dir", default="OUTPUT/SYMBOL")
    ap.add_argument("--part-type")
    args = ap.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if args.scan:
        return cmd_scan(input_dir)
    if args.generate:
        if not args.model:
            print("--generate requires --model", file=sys.stderr)
            return 2
        return cmd_generate(Path(args.generate), args.model, output_dir,
                            args.part_type)
    if args.all:
        return cmd_all(input_dir, output_dir, args.part_type)

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
