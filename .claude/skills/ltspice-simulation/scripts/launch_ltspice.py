#!/usr/bin/env python3
"""
launch_ltspice.py — Attempt to open a .cir file in LTspice on Windows.

Walks the canonical install paths for modern ADI builds, legacy XVII, and
legacy IV; falls back to the shell association for the .cir extension.

Usage:
    python launch_ltspice.py path/to/netlist.cir

Exits 0 on successful launch, 1 if no LTspice install was found, 2 on bad args.
On non-Windows, exits 3 and prints a note.
"""

from __future__ import annotations
import os, sys, shutil, subprocess, platform, pathlib


CANDIDATE_PATHS_WINDOWS = [
    # Modern ADI (2023+)
    r"{LOCALAPPDATA}\Programs\ADI\LTspice\LTspice.exe",
    r"C:\Program Files\ADI\LTspice\LTspice.exe",
    r"C:\Program Files (x86)\ADI\LTspice\LTspice.exe",
    # Legacy LTC XVII
    r"C:\Program Files\LTC\LTspiceXVII\XVIIx64.exe",
    r"C:\Program Files (x86)\LTC\LTspiceXVII\XVIIx64.exe",
    r"C:\Program Files\LTC\LTspiceXVII\XVIIx86.exe",
    # Legacy LTC IV
    r"C:\Program Files (x86)\LTC\LTspiceIV\scad3.exe",
    r"C:\Program Files\LTC\LTspiceIV\scad3.exe",
]


def find_ltspice_windows() -> str | None:
    local = os.environ.get("LOCALAPPDATA", "")
    for template in CANDIDATE_PATHS_WINDOWS:
        p = template.replace("{LOCALAPPDATA}", local)
        if os.path.isfile(p):
            return p
    # PATH fallback
    for exe in ("LTspice.exe", "XVIIx64.exe", "scad3.exe"):
        found = shutil.which(exe)
        if found:
            return found
    return None


def launch(cir_path: str) -> int:
    cir = pathlib.Path(cir_path).resolve()
    if not cir.exists():
        print(f"ERROR: file not found: {cir}", file=sys.stderr)
        return 2

    osname = platform.system()

    if osname == "Windows":
        exe = find_ltspice_windows()
        if exe:
            print(f"Launching LTspice: {exe}")
            print(f"With netlist: {cir}")
            subprocess.Popen([exe, str(cir)])
            return 0
        # Shell association fallback: 'start' via cmd
        print("LTspice not found in standard locations; trying shell association...")
        rc = subprocess.call(["cmd", "/c", "start", "", str(cir)], shell=False)
        return 0 if rc == 0 else 1

    if osname == "Darwin":
        # macOS: LTspice app lives at /Applications/LTspice.app
        ltspice_app = "/Applications/LTspice.app"
        if os.path.isdir(ltspice_app):
            subprocess.Popen(["open", "-a", "LTspice", str(cir)])
            return 0
        print(f"LTspice.app not found in /Applications. Netlist ready at: {cir}", file=sys.stderr)
        return 1

    if osname == "Linux":
        # Try Wine
        wine = shutil.which("wine")
        wine_prefix = os.environ.get("WINEPREFIX", os.path.expanduser("~/.wine"))
        for rel in [
            "drive_c/Program Files/ADI/LTspice/LTspice.exe",
            "drive_c/Program Files/LTC/LTspiceXVII/XVIIx64.exe",
        ]:
            full = os.path.join(wine_prefix, rel)
            if wine and os.path.isfile(full):
                subprocess.Popen([wine, full, str(cir)])
                return 0
        print(f"LTspice not found under Wine. Netlist ready at: {cir}", file=sys.stderr)
        return 1

    print(f"Unsupported OS: {osname}. Netlist ready at: {cir}", file=sys.stderr)
    return 3


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python launch_ltspice.py path/to/netlist.cir", file=sys.stderr)
        sys.exit(2)
    sys.exit(launch(sys.argv[1]))
