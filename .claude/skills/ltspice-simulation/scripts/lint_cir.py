#!/usr/bin/env python3
"""
lint_cir.py — Sanity-check an LTspice .cir file before handoff.

Checks:
  1. File ends with .end
  2. No unicode (µ, Ω) in component values
  3. Every node appears on >= 2 element cards (no dangling nets)
  4. Every .model / .subckt reference has a definition (either local or a
     known LTspice built-in we accept silently)
  5. First non-blank line is a comment (title line)
  6. No bare 'M' used as a multiplier where 'Meg' was probably meant
     (heuristic: flags values like '10M' on an AC analysis where that's
      usually 10 MHz)

Exits 0 on clean file, 1 on problems. Prints a human-readable report.

CLI:
    python lint_cir.py path/to/file.cir
"""

from __future__ import annotations
import re, sys, pathlib
from collections import defaultdict

# Built-in LTspice parts we accept without a local .model definition.
# Keep this in sync with references/ltspice_builtin_parts.md.
BUILTINS = {
    # Diodes
    "1N4148", "1N4001", "1N4002", "1N4003", "1N4004", "1N4005", "1N4006",
    "1N4007", "1N5817", "1N5818", "1N5819", "1N5820", "1N5821", "1N5822",
    "MBR0520", "BAT54", "BZX84C5V1", "1N4733A", "1N914",
    # BJTs
    "2N3904", "2N3906", "2N2222", "2N2907", "BC547", "BC557", "MMBT3904",
    "TIP31", "TIP32", "2N5088", "2N5089",
    # MOSFETs
    "IRF540", "IRF9540", "IRF3205", "BS170", "BS250", "Si4410DY", "2N7002",
    "IRF510", "IRF520", "IRF530", "IRFZ44",
    # JFETs
    "2N5457", "2N3819", "J113",
    # Op-amps / subckts
    "UniversalOpAmp2", "UniversalOpAmp", "LT1001", "LT1013", "LT1028",
    "LT1078", "LT1086", "LT3080", "LM317", "AD8601", "AD820", "NE555",
}

UNICODE_BAD = ["µ", "Ω", "\u03BC", "\u03A9"]

# Device letters that take 2 nodes + value/model
TWO_NODE = set("RCLVI")
# Device letters that take 3 nodes + model
THREE_NODE = set("QJ")
# Device letters that take 4 nodes + model
FOUR_NODE = set("M")
# Diode: 2 nodes + model
DIODE = set("D")
# Subcircuit call: variable pins
SUBCKT = set("X")


def lint(path: str):
    p = pathlib.Path(path)
    if not p.exists():
        return [f"FAIL: file not found: {path}"], []

    lines = p.read_text(encoding="ascii", errors="replace").splitlines()
    problems = []
    warnings = []

    # --- 1. First line a comment ---
    first_real = next((ln for ln in lines if ln.strip()), "")
    if not first_real.lstrip().startswith("*") and not first_real.lstrip().lower().startswith(".title"):
        problems.append(
            "First non-blank line must be a comment (starting with '*') or a .title card. "
            "LTspice treats the first line as the title and will parse a component card there as garbage."
        )

    # --- 2. Ends with .end ---
    nonblank = [ln.strip() for ln in lines if ln.strip()]
    if not nonblank or not nonblank[-1].lower().startswith(".end"):
        problems.append("File must end with a '.end' directive on its own line.")

    # --- 3. Unicode scan ---
    for i, ln in enumerate(lines, 1):
        for bad in UNICODE_BAD:
            if bad in ln:
                problems.append(f"Line {i}: unicode char {bad!r} — LTspice may not parse. Use ASCII.")

    # --- 4. Node usage + model references ---
    node_uses = defaultdict(int)   # node -> how many element cards touch it
    model_refs = []                # (line_no, model_name)
    defined_models = set()
    defined_subckts = set()

    for i, raw in enumerate(lines, 1):
        ln = raw.strip()
        if not ln or ln.startswith("*") or ln.startswith(";"):
            continue
        if ln.startswith("+"):
            continue
        toks = ln.split()
        if not toks:
            continue
        head = toks[0]
        low = ln.lower()

        # Directives
        if head.startswith("."):
            if low.startswith(".model"):
                if len(toks) >= 2:
                    defined_models.add(toks[1])
            elif low.startswith(".subckt"):
                if len(toks) >= 2:
                    defined_subckts.add(toks[1])
            continue

        letter = head[0].upper()

        # Figure out the node range and model position based on letter
        if letter in TWO_NODE:
            if len(toks) < 4:
                warnings.append(f"Line {i}: {head} looks malformed: {ln!r}")
                continue
            nodes = toks[1:3]
            # V/I sources don't have a model; R/C/L value is in toks[3]
        elif letter in DIODE:
            if len(toks) < 4:
                warnings.append(f"Line {i}: diode {head} malformed: {ln!r}")
                continue
            nodes = toks[1:3]
            model_refs.append((i, toks[3]))
        elif letter in THREE_NODE:
            if len(toks) < 5:
                warnings.append(f"Line {i}: {head} malformed: {ln!r}")
                continue
            nodes = toks[1:4]
            model_refs.append((i, toks[4]))
        elif letter in FOUR_NODE:
            if len(toks) < 6:
                warnings.append(f"Line {i}: {head} malformed: {ln!r}")
                continue
            nodes = toks[1:5]
            model_refs.append((i, toks[5]))
        elif letter in SUBCKT:
            # X<name> n1 n2 ... nN SUBCKTNAME [params]
            # We don't know how many nodes; last non-param token is the subckt name.
            # Scan from the right skipping tokens that look like "key=value"
            j = len(toks) - 1
            while j >= 2 and "=" in toks[j]:
                j -= 1
            if j < 2:
                warnings.append(f"Line {i}: subckt call {head} malformed: {ln!r}")
                continue
            subckt_name = toks[j]
            nodes = toks[1:j]
            model_refs.append((i, subckt_name))
        elif letter in {"E", "G", "H", "F", "B"}:
            # Controlled sources / behavioral — accept without deep validation
            if len(toks) < 4:
                warnings.append(f"Line {i}: controlled source {head} malformed: {ln!r}")
                continue
            # Use nplus/nminus at least
            nodes = toks[1:3]
        else:
            warnings.append(f"Line {i}: unknown device letter {letter!r} in {ln!r}")
            continue

        for n in nodes:
            node_uses[n] += 1

    # --- Dangling nets ---
    for node, count in node_uses.items():
        if node in ("0", "GND", "gnd"):
            continue
        if count < 2:
            problems.append(
                f"Node {node!r} appears on only {count} component(s). "
                "Every non-ground net should connect at least two devices."
            )

    # --- Model references ---
    for line_no, name in model_refs:
        if name in defined_models or name in defined_subckts:
            continue
        if name in BUILTINS:
            continue
        problems.append(
            f"Line {line_no}: reference to {name!r} but no .model or .subckt defining it, "
            "and it is not on the built-in list. Embed the model or substitute a builtin."
        )

    # --- 'M' vs 'Meg' heuristic ---
    for i, raw in enumerate(lines, 1):
        ln = raw.strip()
        if not ln or ln.startswith("*") or ln.startswith(";") or ln.startswith("."):
            continue
        # look for tokens ending in bare 'M' followed by whitespace/EOL, that are numeric-prefixed
        for m in re.finditer(r"\b(\d+(?:\.\d+)?)M\b(?!eg)", ln):
            warnings.append(
                f"Line {i}: value {m.group(0)!r} uses bare 'M' (milli in SPICE). "
                "If you meant 1 million, use 'Meg'."
            )

    return problems, warnings


def main():
    if len(sys.argv) != 2:
        print("usage: python lint_cir.py path/to/file.cir", file=sys.stderr)
        sys.exit(2)
    problems, warnings = lint(sys.argv[1])
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print(f"  - {p}")
    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(f"  - {w}")
    if not problems and not warnings:
        print("OK: lint clean.")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
