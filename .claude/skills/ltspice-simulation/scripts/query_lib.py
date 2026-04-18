#!/usr/bin/env python3
"""
query_lib.py -- Search the LTspice lib.zip for a part name.

For each part the skill needs to model, run this BEFORE deciding to embed a
custom .model or .subckt card.  The output tells you whether the part already
exists in the LTspice library and what to write in the .cir or .asc.

Usage:
    python scripts/query_lib.py <part_name>
    python scripts/query_lib.py PC817
    python scripts/query_lib.py BC547
    python scripts/query_lib.py IRF9540

Output sections:
    SYMBOLS     -- .asy files found (use SYMBOL path in .asc)
    SUBCKTS     -- .sub/.lib files containing a matching .subckt (reference by name in .cir)
    MODELS      -- .sub/.lib files containing a matching .model  (reference by name in .cir)
    MODEL_DEFS  -- the actual .model lines so you can embed them if needed

Exit codes:
    0 = at least one match found
    1 = no match (must embed custom .model or .subckt stub)
    2 = lib.zip not found / bad args
"""

from __future__ import annotations
import sys, zipfile, pathlib, re

LTSPICE_ROOTS = [
    pathlib.Path.home() / "AppData/Local/Programs/ADI/LTspice",
    pathlib.Path("C:/Program Files/ADI/LTspice"),
    pathlib.Path("C:/Program Files (x86)/ADI/LTspice"),
    pathlib.Path("/Applications/LTspice.app/Contents/Resources"),
]


def find_lib_zip() -> pathlib.Path | None:
    for root in LTSPICE_ROOTS:
        p = root / "lib.zip"
        if p.is_file():
            return p
    return None


def decode_entry(raw: bytes) -> str:
    """Decode a zip entry, handling UTF-16-LE (BJT/MOS/JFT files) and latin-1 (DIO, SUB, LIB)."""
    # UTF-16-LE detection: null bytes interleaved in first few bytes
    if len(raw) >= 4 and raw[1] == 0 and raw[3] == 0:
        return raw.decode("utf-16-le", errors="replace")
    # UTF-16 with BOM
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    return raw.decode("latin-1", errors="replace")


def search(part: str, lib_zip: pathlib.Path) -> dict:
    part_lower = part.lower()
    results: dict = {"symbols": [], "subckts": [], "models": [], "model_defs": []}

    # Component library extensions that may contain .model cards
    CMP_EXTS  = {".bjt", ".mos", ".dio", ".jft", ".sub", ".lib"}

    with zipfile.ZipFile(lib_zip) as z:
        for entry in z.namelist():
            entry_stem = pathlib.PurePosixPath(entry).stem.lower()
            ext        = pathlib.PurePosixPath(entry).suffix.lower()

            # ---- .asy symbol files: match on filename stem ----
            if ext == ".asy" and (entry_stem == part_lower or part_lower in entry_stem):
                content = z.read(entry).decode("latin-1", errors="replace")
                attrs: dict[str, str] = {}
                for line in content.splitlines():
                    m = re.match(r"SYMATTR\s+(\S+)\s+(.*)", line)
                    if m:
                        attrs[m.group(1)] = m.group(2).strip()
                sym_path = entry.replace("lib/sym/", "").replace(".asy", "")
                results["symbols"].append({
                    "zip_path"   : entry,
                    "symbol_path": sym_path,
                    "spice_model": attrs.get("SpiceModel", ""),
                    "prefix"     : attrs.get("Prefix", "X"),
                    "value"      : attrs.get("Value", ""),
                    "value2"     : attrs.get("Value2", ""),
                    "description": attrs.get("Description", ""),
                })

            # ---- component / subcircuit / model files: search by content ----
            elif ext in CMP_EXTS:
                try:
                    raw     = z.read(entry)
                    content = decode_entry(raw)
                except Exception:
                    continue

                # .subckt definitions
                for m in re.finditer(r"^\.subckt\s+(\S+)\s*(.*)",
                                     content, re.IGNORECASE | re.MULTILINE):
                    if part_lower in m.group(1).lower():
                        results["subckts"].append({
                            "zip_path": entry,
                            "name"    : m.group(1),
                            "pins"    : m.group(2).strip(),
                        })

                # .model definitions — grab the full first line only (continuation lines omitted)
                for m in re.finditer(r"^\.model\s+(\S+)\s+(\S+)\s*(\([^)]*\))?",
                                     content, re.IGNORECASE | re.MULTILINE):
                    if part_lower in m.group(1).lower():
                        # Collect the full model including continuation lines
                        start = m.start()
                        chunk = content[start:start+600]
                        lines = chunk.splitlines()
                        full  = lines[0]
                        for ln in lines[1:]:
                            if ln.startswith("+"):
                                full += "\n" + ln
                            else:
                                break
                        results["models"].append({
                            "zip_path": entry,
                            "name"    : m.group(1),
                            "type"    : m.group(2),
                        })
                        results["model_defs"].append(full)

    return results


def print_results(part: str, results: dict) -> bool:
    found = False

    if results["symbols"]:
        found = True
        print(f"\n=== SYMBOLS (use SYMBOL directive in .asc) ===")
        for s in results["symbols"]:
            print(f"  File       : {s['zip_path']}")
            print(f"  SYMBOL     : {s['symbol_path']}")
            if s["description"]:
                print(f"  Description: {s['description']}")
            if s["spice_model"]:
                print(f"  SpiceModel : {s['spice_model']}")
            if s["value2"]:
                print(f"  Value2     : {s['value2']}  (params passed to subckt)")
            print(f"  Prefix     : {s['prefix']}")
            # Synthesise the .cir X-call if it's a subcircuit symbol
            if s["prefix"] == "X" and s["value2"]:
                subckt_call = s["value2"].split()[0]
                print(f"  -> In .cir : X<inst> <pins...> {subckt_call}")
            elif s["prefix"] == "X":
                print(f"  -> In .cir : X<inst> <pins...> {s['value'] or s['symbol_path'].split('/')[-1]}")
            print()

    if results["subckts"]:
        found = True
        print(f"=== SUBCIRCUITS (reference by name in .cir) ===")
        for sc in results["subckts"]:
            print(f"  File  : {sc['zip_path']}")
            print(f"  Name  : {sc['name']}")
            print(f"  Pins  : {sc['pins']}")
            print(f"  -> In .cir : X<inst> {sc['pins']} {sc['name']}")
            print(f"  (LTspice auto-finds it from lib.zip; no .lib directive needed)")
            print()

    if results["models"]:
        found = True
        print(f"=== MODELS (reference by name in device card) ===")
        for md in results["models"]:
            print(f"  File  : {md['zip_path']}")
            print(f"  Name  : {md['name']}  ({md['type']})")
            print(f"  -> In .cir : Q/M/D <pins...> {md['name']}")
            print(f"  (LTspice auto-finds it from lib.zip; no .model embed needed)")
            print()

    if results["model_defs"]:
        print(f"=== MODEL DEFINITIONS (copy-paste if you need to embed) ===")
        for d in results["model_defs"]:
            print(f"  {d}")
        print()

    if not found:
        print(f"\n  No match for '{part}' in lib.zip.")
        print(f"  -> Embed a custom .model or .subckt stub in the .cir.")

    return found


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python query_lib.py <part_name>", file=sys.stderr)
        return 2

    part    = sys.argv[1]
    lib_zip = find_lib_zip()
    if not lib_zip:
        print("ERROR: LTspice lib.zip not found in standard locations.", file=sys.stderr)
        return 2

    print(f"LTspice lib.zip : {lib_zip}")
    print(f"Searching for   : '{part}'")

    results = search(part, lib_zip)
    found   = print_results(part, results)
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
