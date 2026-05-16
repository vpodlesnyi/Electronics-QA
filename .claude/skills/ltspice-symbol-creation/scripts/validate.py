#!/usr/bin/env python3
"""
validate.py — Validate a generated symbol package against the
ltspice-symbol-creation checklist.

Usage:
    python validate.py --asy <path.asy> --lib <path.lib> --model <NAME>
        [--report <path.md>] [--usage <path.txt>]
        [--declared-pins "PIN1,PIN2,PIN3,..."]

Outputs JSON. Exit 0 if all checks pass; exit 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ABS_PATH_PATTERNS = [
    re.compile(r"[A-Za-z]:\\"),
    re.compile(r"^\s*/(?:home|Users|root|tmp)/", re.MULTILINE),
    re.compile(r"\\Downloads\\", re.IGNORECASE),
    re.compile(r"^~", re.MULTILINE),
]

VALID_PREFIXES = {"X", "D", "Q", "M", "J", "R", "C", "L", "S", "W",
                  "V", "I", "B", "E", "F", "G", "H", "K"}


def parse_asy(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    sym_attrs = {}
    pins = []
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        toks = line.split(None, 1)
        kw = toks[0]
        rest = toks[1] if len(toks) > 1 else ""
        if kw == "SYMATTR":
            sub = rest.split(None, 1)
            if len(sub) == 2:
                sym_attrs[sub[0]] = sub[1]
            elif len(sub) == 1:
                sym_attrs[sub[0]] = ""
        elif kw == "PIN":
            parts = rest.split()
            current = {
                "x": int(parts[0]) if len(parts) > 0 else None,
                "y": int(parts[1]) if len(parts) > 1 else None,
                "orientation": parts[2] if len(parts) > 2 else None,
                "offset": int(parts[3]) if len(parts) > 3 else None,
                "PinName": None, "SpiceOrder": None,
            }
            pins.append(current)
        elif kw == "PINATTR" and current is not None:
            sub = rest.split(None, 1)
            if len(sub) == 2:
                key, val = sub
                if key == "SpiceOrder":
                    try:
                        current[key] = int(val)
                    except ValueError:
                        current[key] = val
                else:
                    current[key] = val
    return {"text": text, "sym_attrs": sym_attrs, "pins": pins}


def parse_lib_subckt_pins(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    out = {}
    joined = []
    for line in text.splitlines():
        if line.lstrip().startswith("+") and joined:
            joined[-1] += " " + line.lstrip()[1:].strip()
        else:
            joined.append(line)
    for line in joined:
        s = line.strip()
        if not s.lower().startswith(".subckt"):
            continue
        parts = s.split()
        if len(parts) < 2:
            continue
        name = parts[1]
        pins = []
        for tok in parts[2:]:
            if tok.upper() == "PARAMS:" or "=" in tok:
                break
            pins.append(tok)
        out[name] = pins
    return out


def parse_lib_models(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    names = []
    for line in text.splitlines():
        s = line.strip()
        if s.lower().startswith(".model"):
            parts = s.split()
            if len(parts) >= 2:
                names.append(parts[1])
    return names


def validate(asy_path, lib_path, model_name, declared_pins=None):
    checks = []

    def check(name, passed, evidence=""):
        checks.append({"text": name, "passed": passed, "evidence": evidence})

    asy = parse_asy(asy_path)
    sym = asy["sym_attrs"]
    pins = asy["pins"]

    spice_orders = [p["SpiceOrder"] for p in pins if p["SpiceOrder"] is not None]
    n = len(pins)

    check("Every PIN has a PinName attribute",
          all(p.get("PinName") for p in pins),
          f"{sum(1 for p in pins if p.get('PinName'))}/{n} pins have PinName")
    check("Every PIN has a SpiceOrder attribute",
          all(p.get("SpiceOrder") is not None for p in pins),
          f"{sum(1 for p in pins if p.get('SpiceOrder') is not None)}/{n} have SpiceOrder")
    check("SpiceOrder values are unique",
          len(set(spice_orders)) == len(spice_orders),
          f"{len(spice_orders)} pins, {len(set(spice_orders))} unique orders")
    check("SpiceOrder values are 1..N contiguous",
          sorted(spice_orders) == list(range(1, n + 1)) if n > 0 else True,
          f"orders={sorted(spice_orders)}; expected 1..{n}")

    lib_subckts = parse_lib_subckt_pins(lib_path)
    decl_pins = declared_pins
    if decl_pins is None and model_name in lib_subckts:
        decl_pins = lib_subckts[model_name]

    if decl_pins is not None:
        pin_by_order = {p["SpiceOrder"]: p["PinName"] for p in pins}
        ordered_names = [pin_by_order.get(i + 1) for i in range(len(decl_pins))]
        match = ordered_names == decl_pins
        check("SpiceOrder order matches .SUBCKT declaration order",
              match,
              f".SUBCKT pins: {decl_pins} vs symbol order: {ordered_names}")
    else:
        # .MODEL primitive — pin order is conventional, no .SUBCKT to compare
        check("SpiceOrder order matches .SUBCKT declaration order",
              True,
              "N/A - .MODEL primitive uses conventional pin order")

    prefix = sym.get("Prefix", "")
    check("Symbol Prefix is set and is a valid SPICE letter",
          prefix in VALID_PREFIXES,
          f"Prefix={prefix!r}")

    if model_name in lib_subckts:
        check("Subcircuit symbol uses Prefix X",
              prefix == "X",
              f"Prefix={prefix!r}, model is .SUBCKT")

    spice_model = sym.get("SpiceModel", "")
    value = sym.get("Value", "")
    used_name = spice_model or value
    in_subckts = model_name in lib_subckts
    in_models = model_name in parse_lib_models(lib_path)
    check("SpiceModel/Value names a model that exists in the .lib",
          model_name == used_name and (in_subckts or in_models),
          f"used={used_name!r}; in_subckts={in_subckts}; in_models={in_models}")

    asy_text = asy["text"]
    abs_hits = []
    for pat in ABS_PATH_PATTERNS:
        for m in pat.finditer(asy_text):
            abs_hits.append(m.group(0))
    check("No absolute filesystem paths in .asy",
          len(abs_hits) == 0,
          f"hits={abs_hits[:5]}")

    model_file = sym.get("ModelFile", "")
    is_bare = (model_file and not any(c in model_file for c in "\\/")
               and not model_file.startswith("~"))
    check("ModelFile attribute is a bare filename (no path separators)",
          bool(is_bare),
          f"ModelFile={model_file!r}")

    n_pass = sum(1 for c in checks if c["passed"])
    n_fail = len(checks) - n_pass
    return {
        "asy": str(asy_path), "lib": str(lib_path),
        "model": model_name, "checks": checks,
        "summary": {"total": len(checks), "passed": n_pass, "failed": n_fail},
        "ok": n_fail == 0,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--asy", required=True)
    ap.add_argument("--lib", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--declared-pins")
    args = ap.parse_args()

    decl_pins = None
    if args.declared_pins:
        decl_pins = [p.strip() for p in args.declared_pins.split(",") if p.strip()]

    result = validate(
        Path(args.asy), Path(args.lib), args.model,
        decl_pins,
    )
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
