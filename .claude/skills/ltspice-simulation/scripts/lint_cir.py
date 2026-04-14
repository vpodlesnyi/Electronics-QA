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
import re, sys, pathlib, zipfile
from collections import defaultdict

# Fast-path set: always accept these without hitting lib.zip.
# Only contains parts that were positively confirmed in lib.zip for LTspice 26.
# Do NOT add parts here unless you have verified them with query_lib.py.
BUILTINS: set[str] = {
    # Diodes (standard.dio, latin-1)
    "1N914", "1N4148", "MMSD4148",
    "1N5817", "1N5818", "1N5819",
    "BAT54", "MBR0520L", "MBR0530L",
    # BJTs (standard.bjt, UTF-16-LE)
    "2N2222", "2N2907", "2N3904", "2N3906",
    "BC547B", "BC547C", "BC557B",
    # MOSFETs (standard.mos, UTF-16-LE)
    "BS170", "2N7002", "Si4410DY",
    # Op-amp macromodels (always available in LTspice)
    "UniversalOpAmp2", "UniversalOpAmp",
}

# Cached lib.zip lookup results (model_name -> bool)
_lib_zip_cache: dict[str, bool] = {}
_lib_zip_path: pathlib.Path | None = None

def _find_lib_zip() -> pathlib.Path | None:
    global _lib_zip_path
    if _lib_zip_path is not None:
        return _lib_zip_path
    candidates = [
        pathlib.Path.home() / "AppData/Local/Programs/ADI/LTspice/lib.zip",
        pathlib.Path("C:/Program Files/ADI/LTspice/lib.zip"),
        pathlib.Path("C:/Program Files (x86)/ADI/LTspice/lib.zip"),
    ]
    for c in candidates:
        if c.is_file():
            _lib_zip_path = c
            return c
    return None

def _decode(raw: bytes) -> str:
    if len(raw) >= 4 and raw[1] == 0 and raw[3] == 0:
        return raw.decode("utf-16-le", errors="replace")
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    return raw.decode("latin-1", errors="replace")

def _in_lib_zip(name: str) -> bool:
    """Return True if `name` is found as a .model, .subckt, or symbol in lib.zip."""
    key = name.upper()
    if key in _lib_zip_cache:
        return _lib_zip_cache[key]
    lib = _find_lib_zip()
    if lib is None:
        _lib_zip_cache[key] = False
        return False
    name_lower = name.lower()
    try:
        with zipfile.ZipFile(lib) as z:
            for entry in z.namelist():
                ext  = pathlib.PurePosixPath(entry).suffix.lower()
                stem = pathlib.PurePosixPath(entry).stem.lower()
                # Symbol file match
                if ext == ".asy" and (stem == name_lower or name_lower in stem):
                    _lib_zip_cache[key] = True
                    return True
                # Model/subcircuit content match
                if ext in {".bjt", ".mos", ".dio", ".jft", ".sub", ".lib"}:
                    try:
                        content = _decode(z.read(entry))
                        pat = re.compile(
                            r"^\.(model|subckt)\s+" + re.escape(name) + r"\b",
                            re.IGNORECASE | re.MULTILINE,
                        )
                        if pat.search(content):
                            _lib_zip_cache[key] = True
                            return True
                    except Exception:
                        pass
    except Exception:
        pass
    _lib_zip_cache[key] = False
    return False

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
        if name.upper() in {b.upper() for b in BUILTINS}:
            continue
        # Dynamic fallback: search lib.zip
        if _in_lib_zip(name):
            continue
        problems.append(
            f"Line {line_no}: reference to {name!r} but no .model or .subckt defining it, "
            "and it was not found in lib.zip. Embed the model or substitute a known part."
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
