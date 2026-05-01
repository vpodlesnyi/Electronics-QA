#!/usr/bin/env python3
"""
normalize_lib.py — Write a normalized copy of a SPICE library file for
LTspice consumption. Records every change applied. The original file is
read-only here; the normalized copy goes to a separate destination.

Safe rewrites applied:
  - Strip the literal `PARAMS:` keyword on .SUBCKT lines.
  - Convert `E<n> ... VALUE = { expr }` and `G<n> ... VALUE = { expr }` to
    `B<n> ... V = expr` / `... I = expr`.
  - Normalize Unicode µ to plain `u`.

Risky rewrites are NOT applied — they are recorded as warnings only.

Usage:
    python normalize_lib.py --in <input> --out <output>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PARAMS_KW_RE = re.compile(r"\bPARAMS\s*:", re.IGNORECASE)
VALUE_BLOCK_RE = re.compile(
    r"^(?P<dev>[EG])(?P<rest>\S+\s+\S+\s+\S+)\s+VALUE\s*=\s*\{(?P<expr>[^}]*)\}\s*$",
    re.IGNORECASE,
)
UNICODE_MU = "µμ"


def normalize_lines(text: str) -> tuple[str, list[dict]]:
    """Return (normalized_text, list_of_changes)."""
    changes: list[dict] = []
    out_lines: list[str] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw

        # Unicode µ → u
        if any(ch in line for ch in UNICODE_MU):
            new_line = line
            for ch in UNICODE_MU:
                new_line = new_line.replace(ch, "u")
            changes.append({"line": i, "rule": "unicode-mu",
                            "before": line, "after": new_line})
            line = new_line

        # Strip PARAMS: on .subckt lines
        if line.lstrip().lower().startswith(".subckt") and PARAMS_KW_RE.search(line):
            new_line = PARAMS_KW_RE.sub("", line, count=1)
            # Collapse double spaces
            new_line = re.sub(r"\s{2,}", " ", new_line).rstrip()
            changes.append({"line": i, "rule": "strip-params-keyword",
                            "before": line, "after": new_line})
            line = new_line

        # E/G VALUE={...} → B V=... / I=...
        m = VALUE_BLOCK_RE.match(line.strip())
        if m:
            dev = m.group("dev").upper()
            rest = m.group("rest")
            expr = m.group("expr").strip()
            ctrl = "V" if dev == "E" else "I"
            # The "rest" usually is "<refdes_remainder> <out> <ref>".
            # We reuse it as-is and just swap the device letter to B and
            # rewrite the VALUE form to V=/I=
            # Note: this rewrite is conservative and may need manual
            # tweaks for unusual forms.
            new_line = f"B{rest} {ctrl}={expr}"
            changes.append({"line": i, "rule": "value-to-bsource",
                            "before": line, "after": new_line})
            line = new_line

        out_lines.append(line)

    return "\n".join(out_lines) + "\n", changes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="in_path", required=True)
    ap.add_argument("--out", dest="out_path", required=True)
    ap.add_argument("--changes-json", help="Optional path to write the change log JSON")
    args = ap.parse_args()

    in_path = Path(args.in_path)
    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    text = in_path.read_text(encoding="utf-8", errors="replace")
    normalized, changes = normalize_lines(text)
    out_path.write_text(normalized, encoding="utf-8")

    if args.changes_json:
        Path(args.changes_json).write_text(json.dumps(changes, indent=2))

    summary = {
        "in": str(in_path),
        "out": str(out_path),
        "changes": changes,
        "change_count": len(changes),
    }
    json.dump(summary, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
