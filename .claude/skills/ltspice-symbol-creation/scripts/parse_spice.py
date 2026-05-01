#!/usr/bin/env python3
"""
parse_spice.py — Parse a SPICE model file and emit a structured JSON
description.

Reads a single .lib/.sub/.cir/.mod/.txt SPICE file, finds .SUBCKT and
.MODEL definitions, classifies the dialect, detects encryption, follows
.INCLUDE/.LIB references one level, emits JSON to stdout.

Usage:
    python parse_spice.py <path>
    python parse_spice.py <path> --pretty

Exit codes:
    0  — parsed something useful (at least one .SUBCKT or .MODEL).
    1  — file unreadable / encrypted / no model definitions found.
    2  — invalid arguments.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# ---------- patterns ----------

# Note: LIMIT() and IF() are intentionally NOT in this list — both work in
# LTspice natively (limit() is a builtin; ternary 'a?b:c' replaces IF).
PSPICE_INDICATORS = [
    re.compile(r"\bPARAMS\s*:", re.IGNORECASE),
    re.compile(r"VALUE\s*=\s*\{", re.IGNORECASE),
    re.compile(r"\bTABLE\s*\(", re.IGNORECASE),
    re.compile(r"\.STIMULUS\b", re.IGNORECASE),
    re.compile(r"^\*\$", re.MULTILINE),
    re.compile(r"^\*#", re.MULTILINE),
    re.compile(r"\bPSpice\b", re.IGNORECASE),
    re.compile(r"\bOrCAD\b", re.IGNORECASE),
    re.compile(r"\bCadence\b", re.IGNORECASE),
]

HSPICE_INDICATORS = [
    re.compile(r"\.OPTION\b", re.IGNORECASE),
    re.compile(r"\.MEAS(?:URE)?\b", re.IGNORECASE),
    re.compile(r"\bHSpice\b", re.IGNORECASE),
    re.compile(r"\bSynopsys\b", re.IGNORECASE),
]

ENCRYPTION_MARKERS = [
    re.compile(r"\bENCRYPTED\b", re.IGNORECASE),
    re.compile(r"^\*#FUNC\b", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\*#ENC\b", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\*#protected\b", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\*\$PROTECTED\b", re.MULTILINE | re.IGNORECASE),
]

PRIMITIVE_TYPES_TO_PREFIX = {
    "D": "D",
    "NPN": "Q", "PNP": "Q",
    "NMOS": "M", "PMOS": "M",
    "NJF": "J", "PJF": "J",
    "R": "R", "C": "C", "L": "L",
    "SW": "S", "CSW": "W",
}

MODEL_LINE_RE = re.compile(
    r"""^
        \.MODEL \s+
        (?P<name>\S+) \s+
        (?P<type>[A-Za-z][A-Za-z0-9_]*)
        (?: \s* \( (?P<body>.*?) \) )?
        \s* $
    """,
    re.VERBOSE | re.IGNORECASE,
)


# ---------- helpers ----------

def read_text_safely(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    printable = sum(1 for b in raw if 32 <= b < 127 or b in (9, 10, 13))
    if len(raw) > 0 and printable / len(raw) < 0.7:
        try:
            return raw.decode("latin-1", errors="replace"), "latin-1-fallback-binary"
        except Exception:
            return "", "binary"
    for enc in ("utf-8", "utf-16-le", "utf-16-be", "latin-1"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace"), "latin-1-fallback"


def join_continuations(lines):
    out = []
    for idx, raw in enumerate(lines, start=1):
        line = raw.rstrip("\r\n")
        if not line.strip():
            out.append((idx, line))
            continue
        if line.lstrip().startswith("+") and out:
            prev_idx, prev_text = out[-1]
            cont = line.lstrip()[1:]
            out[-1] = (prev_idx, prev_text + " " + cont.strip())
        else:
            out.append((idx, line))
    return out


def classify_dialect(text: str) -> str:
    pspice_hits = sum(1 for p in PSPICE_INDICATORS if p.search(text))
    hspice_hits = sum(1 for p in HSPICE_INDICATORS if p.search(text))
    if pspice_hits >= 1 and pspice_hits >= hspice_hits:
        return "pspice"
    if hspice_hits >= 1:
        return "hspice"
    return "ltspice"


def detect_encryption(text: str):
    fired = []
    for pat in ENCRYPTION_MARKERS:
        m = pat.search(text)
        if m:
            fired.append(m.group(0))
    long_dense, nonblank = 0, 0
    for line in text.splitlines():
        if not line.strip():
            continue
        nonblank += 1
        if len(line) >= 200 and " " not in line and "\t" not in line:
            long_dense += 1
    if nonblank > 10 and long_dense / nonblank > 0.5:
        fired.append("base64-like-body")
    return fired


def parse_subckt_decl(joined_line: str):
    stripped = joined_line.strip()
    if not stripped.lower().startswith(".subckt"):
        return None
    parts = stripped.split()
    if len(parts) < 2:
        return None
    name = parts[1]
    pins, params = [], []
    in_params = False
    for tok in parts[2:]:
        if tok.upper() == "PARAMS:":
            in_params = True
            continue
        if "=" in tok or in_params:
            in_params = True
            if "=" in tok:
                k, _, v = tok.partition("=")
                params.append({"name": k, "default": v})
            else:
                params.append({"name": tok, "default": None})
            continue
        pins.append(tok)
    return {"name": name, "pins": pins, "params": params}


def parse_model_line(joined_line: str):
    stripped = joined_line.strip()
    if not stripped.lower().startswith(".model"):
        return None
    m = MODEL_LINE_RE.match(stripped)
    if not m:
        parts = stripped.split(None, 3)
        if len(parts) < 3:
            return None
        name, mtype = parts[1], parts[2]
        body = parts[3] if len(parts) > 3 else ""
        body = body.strip()
        if body.startswith("(") and body.endswith(")"):
            body = body[1:-1]
        return {
            "name": name,
            "type": mtype.upper(),
            "prefix": PRIMITIVE_TYPES_TO_PREFIX.get(mtype.upper(), "?"),
            "body": body,
        }
    return {
        "name": m.group("name"),
        "type": m.group("type").upper(),
        "prefix": PRIMITIVE_TYPES_TO_PREFIX.get(m.group("type").upper(), "?"),
        "body": (m.group("body") or "").strip(),
    }


def find_includes(joined_lines):
    out = []
    for line_no, line in joined_lines:
        s = line.strip()
        low = s.lower()
        if low.startswith(".include") or low.startswith(".inc "):
            parts = s.split(None, 1)
            if len(parts) >= 2:
                target = parts[1].strip().strip('"').strip("'")
                out.append({"line": line_no, "directive": "include", "target": target})
        elif low.startswith(".lib"):
            parts = s.split(None, 2)
            if len(parts) >= 2:
                target = parts[1].strip().strip('"').strip("'")
                section = parts[2].strip() if len(parts) >= 3 else None
                out.append({"line": line_no, "directive": "lib",
                            "target": target, "section": section})
    return out


def find_pspice_warnings(joined_lines):
    warnings = []
    for line_no, line in joined_lines:
        for pat in PSPICE_INDICATORS:
            m = pat.search(line)
            if m:
                warnings.append({"line": line_no, "match": m.group(0),
                                 "pattern": pat.pattern,
                                 "text": line.strip()[:200]})
                break
    return warnings


# ---------- main ----------

def parse_file(path: Path, follow_includes: bool = True, _depth: int = 0):
    if _depth > 1:
        return {
            "path": str(path), "subckts": [], "models": [],
            "warnings": [{"line": 0, "match": "max include depth",
                          "pattern": "depth-limit",
                          "text": "include chain too deep"}],
        }

    if not path.exists():
        return {
            "path": str(path), "error": "file not found",
            "subckts": [], "models": [], "includes": [],
            "warnings": [], "encryption": [],
            "dialect": "unknown",
        }

    text, encoding = read_text_safely(path)

    enc = detect_encryption(text)
    if enc:
        return {
            "path": str(path), "encoding": encoding,
            "encryption": enc, "subckts": [], "models": [],
            "includes": [], "warnings": [],
            "dialect": "unknown",
        }

    lines = text.splitlines()
    joined = join_continuations(lines)

    subckts, models = [], []
    for line_no, line in joined:
        if not line.strip() or line.lstrip().startswith("*"):
            continue
        if line.lstrip().lower().startswith(".subckt"):
            sub = parse_subckt_decl(line)
            if sub:
                sub["declared_at_line"] = line_no
                subckts.append(sub)
        elif line.lstrip().lower().startswith(".model"):
            mod = parse_model_line(line)
            if mod:
                mod["declared_at_line"] = line_no
                models.append(mod)

    includes = find_includes(joined)
    pspice_warnings = find_pspice_warnings(joined)
    dialect = classify_dialect(text)

    result = {
        "path": str(path),
        "encoding": encoding,
        "dialect": dialect,
        "encryption": [],
        "subckts": subckts,
        "models": models,
        "includes": includes,
        "warnings": pspice_warnings,
        "stats": {"lines": len(lines), "joined_statements": len(joined)},
        "included_results": [],
    }

    if follow_includes and includes:
        for inc in includes:
            target = inc["target"]
            candidates = [path.parent / target]
            input_symbol = Path("INPUT/SYMBOL") / target
            if input_symbol not in candidates:
                candidates.append(input_symbol)
            found = next((c for c in candidates if c.exists()), None)
            if found is None:
                inc["status"] = "missing"
            else:
                inc["status"] = "found"
                inc["resolved_path"] = str(found)
                child = parse_file(found, follow_includes=True,
                                   _depth=_depth + 1)
                result["included_results"].append(child)

    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path")
    ap.add_argument("--no-includes", action="store_true")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    path = Path(args.path)
    result = parse_file(path, follow_includes=not args.no_includes)

    indent = 2 if args.pretty else None
    json.dump(result, sys.stdout, indent=indent, default=str)
    sys.stdout.write("\n")

    if result.get("error"):
        return 1
    if result.get("encryption"):
        return 1
    if not result.get("subckts") and not result.get("models"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
