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
    json.dump({"status": "FAILED", "model": model_name,
               "input": str(input_path), "reason": reason},
              sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 1


def cmd_generate(input_path, model_name, output_dir, part_type_override,
                 use_subfolder=False):
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

    if use_subfolder:
        out_subdir = output_dir / slug(matched["name"])
    else:
        out_subdir = output_dir
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

    val_args = [sys.executable, str(SCRIPT_DIR / "validate.py"),
                "--asy", str(asy_path), "--lib", str(lib_path),
                "--model", matched["name"]]
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

    summary = {
        "model": matched["name"], "kind": kind, "part_type": part_type,
        "confidence": confidence, "output_dir": str(out_subdir),
        "files": {"asy": str(asy_path), "lib": str(lib_path)},
        "validation": val_json, "status": status,
        "pspice_warnings": pspice_warnings,
        "norm_changes": norm_changes,
        "missing_includes": missing_includes,
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
        rc = cmd_generate(fp, candidates[0], output_dir, part_type_override,
                          use_subfolder=True)
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
