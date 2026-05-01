#!/usr/bin/env python3
"""
gen_asy.py — Generate an LTspice .asy symbol from a parsed model JSON.

Reads JSON from stdin (or --json-file) describing a single model
definition, and writes the resulting .asy text to stdout (or --out).

Expected input JSON shape:

    {
      "name": "LM358",
      "kind": "subckt" | "model",
      "prefix": "X" | "D" | "Q" | ...,
      "model_file": "LM358.lib",
      "pins": [
        {"name": "+IN", "function": "noninv_input"},
        {"name": "-IN", "function": "inv_input"},
        {"name": "V+",  "function": "vpos"},
        {"name": "V-",  "function": "vneg"},
        {"name": "OUT", "function": "output"}
      ],
      "part_type": "opamp",  # see PART_SHAPES below
      "description": "Dual op-amp, 32 V"
    }

The pins list is in declaration order — SpiceOrder = index + 1.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ---------- pin-name aliases ----------

# Each tuple: (regex on pin name (case-insensitive), function tag, side,
# rank-on-side). Lower rank goes first / closer to top.

PIN_PATTERNS: list[tuple[re.Pattern[str], str, str, int]] = [
    # power positive
    (re.compile(r"^(VCC|VDD|VS|VPLUS|VPOS|VP|VBAT|V\+|\+VS|VAA|AVCC|AVDD|DVCC|DVDD|VDDA|VDDD|VCCA|VCCD|\+V|POWER)\d*$",
                re.IGNORECASE), "vpos", "top", 0),
    # power negative / ground
    (re.compile(r"^(GND|VSS|VEE|V-|VN|VNEG|VMINUS|-VS|0|COM|AGND|DGND|PGND|EGND|RTN|RETURN|-V)\d*$",
                re.IGNORECASE), "vneg", "bottom", 0),
    # noninv input
    (re.compile(r"^(IN\+|\+IN|INP|IN_P|NONINV|VINP|INA\+|\+INPUT)$",
                re.IGNORECASE), "noninv_input", "left", 0),
    # inv input
    (re.compile(r"^(IN-|-IN|INN|IN_N|INV|VINM|INA-|-INPUT)$",
                re.IGNORECASE), "inv_input", "left", 1),
    # generic input
    (re.compile(r"^(IN|INPUT|SIG|SIGNAL|VIN|INA|INB|IN\d+)$",
                re.IGNORECASE), "input", "left", 5),
    # control
    (re.compile(r"^(EN|ENABLE|CTRL|CONTROL|SHDN|~SHDN|~CS|CS|SLEEP|STBY|MODE|SEL|RESET|~RESET|FB|FBO|COMP)$",
                re.IGNORECASE), "control", "left", 10),
    # outputs
    (re.compile(r"^(OUT|OUTPUT|VOUT|OUTA|OUTB|OUT\d+|Y|Q)$",
                re.IGNORECASE), "output", "right", 0),
    (re.compile(r"^(SW|LX|BST|BOOT|DRV|DRIVE|GATE|HSD|LSD|PHASE)$",
                re.IGNORECASE), "power_output", "right", 5),
    # specific device pins
    (re.compile(r"^(A|AN|ANODE)$", re.IGNORECASE), "anode", "left", 0),
    (re.compile(r"^(K|CA|CATHODE)$", re.IGNORECASE), "cathode", "right", 0),
    (re.compile(r"^(B|BASE)$", re.IGNORECASE), "base", "left", 0),
    (re.compile(r"^(C|COL|COLLECTOR)$", re.IGNORECASE), "collector", "top", 0),
    (re.compile(r"^(E|EMIT|EMITTER)$", re.IGNORECASE), "emitter", "bottom", 0),
    (re.compile(r"^(D|DRAIN)$", re.IGNORECASE), "drain", "top", 0),
    (re.compile(r"^(G|GATE)$", re.IGNORECASE), "gate", "left", 0),
    (re.compile(r"^(S|SOURCE)$", re.IGNORECASE), "source", "bottom", 0),
    (re.compile(r"^(BULK|BODY)$", re.IGNORECASE), "bulk", "right", 0),
]


def classify_pin(name: str) -> tuple[str, str, int]:
    """Return (function_tag, side, rank). Default: ('unknown', None, 99)."""
    for pat, tag, side, rank in PIN_PATTERNS:
        if pat.match(name):
            return tag, side, rank
    return "unknown", "", 99


# ---------- body geometry presets ----------

@dataclass
class BodyGeom:
    rect: tuple[int, int, int, int]  # (x1, y1, x2, y2) of body bbox
    extra_lines: list[tuple[int, int, int, int]]
    # Optional fixed-position pins keyed by function tag, value is
    # (x, y, orientation, name_offset). Pins not found here use perimeter
    # placement.
    fixed: dict[str, tuple[int, int, str, int]]


def opamp_geom() -> BodyGeom:
    return BodyGeom(
        rect=(-32, -32, 32, 32),  # logical bbox; not rendered as RECTANGLE
        extra_lines=[
            (-32, -32, -32, 32),  # back of triangle
            (-32, -32, 32, 0),    # top edge
            (-32, 32, 32, 0),     # bottom edge
            (-28, -16, -20, -16), # + horizontal stroke
            (-24, -20, -24, -12), # + vertical stroke
            (-28, 16, -20, 16),   # - stroke
        ],
        fixed={
            "noninv_input": (-32, -16, "LEFT", 8),
            "inv_input":   (-32, 16, "LEFT", 8),
            "vpos":        (0, -32, "TOP", 8),
            "vneg":        (0, 32,  "BOTTOM", 8),
            "output":      (32, 0,  "RIGHT", 8),
        },
    )


def diode_geom() -> BodyGeom:
    return BodyGeom(
        rect=(-16, -16, 16, 16),
        extra_lines=[
            (-16, -16, 16, 0),    # top edge
            (-16, 16, 16, 0),     # bottom edge
            (-16, -16, -16, 16),  # back edge
            (16, -16, 16, 16),    # cathode bar
            (-32, 0, -16, 0),     # anode lead
            (16, 0, 32, 0),       # cathode lead
        ],
        fixed={
            "anode":   (-32, 0, "LEFT", 8),
            "cathode": (32, 0,  "RIGHT", 8),
        },
    )


def npn_geom() -> BodyGeom:
    return BodyGeom(
        rect=(-16, -16, 16, 16),
        extra_lines=[
            (-8, -16, -8, 16),    # base bar
            (-8, -8, 16, -16),    # collector lead
            (-8, 8, 16, 16),      # emitter lead
            (8, 12, 12, 16),      # arrow piece
            (12, 16, 6, 18),      # arrow piece
            (-16, 0, -8, 0),      # base lead
        ],
        fixed={
            "collector": (16, -16, "RIGHT", 8),
            "base":      (-16, 0,  "LEFT", 8),
            "emitter":   (16, 16,  "RIGHT", 8),
        },
    )


def pnp_geom() -> BodyGeom:
    return BodyGeom(
        rect=(-16, -16, 16, 16),
        extra_lines=[
            (-8, -16, -8, 16),
            (-8, -8, 16, -16),
            (-8, 8, 16, 16),
            (-16, 0, -8, 0),
            # arrow toward base
            (-2, -2, -8, 4),
            (-8, 4, -4, 4),
        ],
        fixed={
            "collector": (16, -16, "RIGHT", 8),
            "base":      (-16, 0,  "LEFT", 8),
            "emitter":   (16, 16,  "RIGHT", 8),
        },
    )


def nmos_geom() -> BodyGeom:
    return BodyGeom(
        rect=(-16, -16, 16, 16),
        extra_lines=[
            (-8, -16, -8, 16),
            (-4, -16, -4, -8),
            (-4, 8, -4, 16),
            (-4, -4, -4, 4),
            (-4, -12, 16, -16),
            (-4, 12, 16, 16),
            (-16, 0, -8, 0),
        ],
        fixed={
            "drain":  (16, -16, "RIGHT", 8),
            "gate":   (-16, 0,  "LEFT", 8),
            "source": (16, 16,  "RIGHT", 8),
            "bulk":   (16, 8,   "RIGHT", 8),
        },
    )


def pmos_geom() -> BodyGeom:
    g = nmos_geom()
    # PMOS: drain at bottom, source at top (visual convention)
    g.fixed = {
        "source": (16, -16, "RIGHT", 8),
        "gate":   (-16, 0,  "LEFT", 8),
        "drain":  (16, 16,  "RIGHT", 8),
        "bulk":   (16, -8,  "RIGHT", 8),
    }
    return g


def generic_rect_geom(pin_count: int) -> BodyGeom:
    """Body sized to fit pin count with reasonable spacing."""
    if pin_count <= 4:
        w, h = 64, 64
    elif pin_count <= 6:
        w, h = 96, 64
    elif pin_count <= 10:
        w, h = 96, 96
    elif pin_count <= 16:
        w, h = 128, 128
    elif pin_count <= 24:
        w, h = 160, 160
    else:
        w, h = 192, 192
    return BodyGeom(
        rect=(-w // 2, -h // 2, w // 2, h // 2),
        extra_lines=[],
        fixed={},
    )


PART_GEOMS = {
    "opamp":     opamp_geom,
    "comparator": opamp_geom,  # same triangle; gen_asy adds 'C' label
    "diode":     diode_geom,
    "zener":     diode_geom,
    "tvs":       diode_geom,
    "npn":       npn_geom,
    "pnp":       pnp_geom,
    "nmos":      nmos_geom,
    "pmos":      pmos_geom,
    "njf":       nmos_geom,
    "pjf":       pmos_geom,
}


# ---------- pin placement on generic rectangle ----------

def place_generic_pins(pins: list[dict[str, Any]],
                       geom: BodyGeom) -> list[dict[str, Any]]:
    """For pins that don't have a fixed position, lay them out around the
    perimeter of the body rectangle by detected side."""
    x1, y1, x2, y2 = geom.rect
    placed = []
    side_buckets: dict[str, list[dict[str, Any]]] = {
        "left": [], "right": [], "top": [], "bottom": [], "": [],
    }
    for pin in pins:
        if pin.get("_x") is not None:  # already placed by fixed
            placed.append(pin)
            continue
        side = pin.get("_side") or "left"
        side_buckets.setdefault(side, []).append(pin)

    # spread on each side
    def lay(bucket: list[dict[str, Any]], side: str) -> None:
        n = len(bucket)
        if n == 0:
            return
        if side in ("left", "right"):
            x = x1 if side == "left" else x2
            orient = "LEFT" if side == "left" else "RIGHT"
            # pad endpoints so labels don't sit on corners
            span = (y2 - y1) - 32
            if n == 1:
                ys = [(y1 + y2) // 2]
            else:
                step = span // (n - 1) if n > 1 else 0
                ys = [y1 + 16 + i * step for i in range(n)]
            # snap to 16-px grid
            ys = [(y + 8) // 16 * 16 for y in ys]
            for pin, y in zip(bucket, ys):
                pin["_x"], pin["_y"] = x, y
                pin["_orient"], pin["_offset"] = orient, 8
                placed.append(pin)
        else:
            y = y1 if side == "top" else y2
            orient = "TOP" if side == "top" else "BOTTOM"
            span = (x2 - x1) - 32
            if n == 1:
                xs = [(x1 + x2) // 2]
            else:
                step = span // (n - 1) if n > 1 else 0
                xs = [x1 + 16 + i * step for i in range(n)]
            xs = [(x + 8) // 16 * 16 for x in xs]
            for pin, x in zip(bucket, xs):
                pin["_x"], pin["_y"] = x, y
                pin["_orient"], pin["_offset"] = orient, 8
                placed.append(pin)

    # Sort each bucket by detected rank, falling back to declaration order
    for side, bucket in side_buckets.items():
        bucket.sort(key=lambda p: (p.get("_rank", 99), p["_decl_index"]))
        if side == "":
            # unknown side — push to left for safety
            lay(bucket, "left")
        else:
            lay(bucket, side)

    return placed


# ---------- main asy emitter ----------

def emit_asy(model: dict[str, Any]) -> str:
    name = model["name"]
    kind = model.get("kind", "subckt")
    prefix = model.get("prefix", "X" if kind == "subckt" else "?")
    part_type = model.get("part_type", "generic").lower()
    pins_in = model.get("pins", [])
    description = model.get("description", "")
    model_file = model.get("model_file", f"{name}.lib")

    # Tag pins with classification
    pins: list[dict[str, Any]] = []
    for i, p in enumerate(pins_in):
        pname = p["name"] if isinstance(p, dict) else str(p)
        function, side, rank = classify_pin(pname)
        pins.append({
            "name": pname,
            "_decl_index": i,
            "_function": function,
            "_side": side,
            "_rank": rank,
            "_x": None, "_y": None,
            "_orient": None, "_offset": 8,
        })

    # Pick body geometry
    geom_factory = PART_GEOMS.get(part_type)
    if geom_factory is None:
        geom = generic_rect_geom(len(pins))
    else:
        geom = geom_factory()

    # Apply fixed-position assignments
    for pin in pins:
        fpos = geom.fixed.get(pin["_function"])
        if fpos is not None:
            pin["_x"], pin["_y"], pin["_orient"], pin["_offset"] = fpos

    # Place remaining pins around the body
    pins = place_generic_pins(pins, geom)

    # Sort pins by declaration index for output order (visual convention)
    pins.sort(key=lambda p: p["_decl_index"])

    # ----- emit the .asy -----
    out: list[str] = []
    out.append("Version 4")
    out.append("SymbolType CELL")

    # body shape: for generic_rect, draw a RECTANGLE; for primitives we
    # already have explicit LINEs in extra_lines.
    if part_type == "generic" or geom_factory is None:
        x1, y1, x2, y2 = geom.rect
        out.append(f"RECTANGLE Normal {x1} {y1} {x2} {y2}")
        # name label inside the rectangle
        out.append(f'TEXT 0 0 Center 1 "{name}"')
    for x1, y1, x2, y2 in geom.extra_lines:
        out.append(f"LINE Normal {x1} {y1} {x2} {y2}")

    if part_type == "comparator":
        out.append('TEXT 8 0 Center 1 "C"')

    # WINDOW overrides — place attribute text outside the body
    bx1, by1, bx2, by2 = geom.rect
    win0_dx, win0_dy = bx2 + 8, by1
    win3_dx, win3_dy = bx2 + 8, by2
    out.append(f"WINDOW 0 {win0_dx} {win0_dy} Left 2")
    out.append(f"WINDOW 3 {win3_dx} {win3_dy} Left 2")

    # SYMATTR block
    out.append(f"SYMATTR Prefix {prefix}")
    if kind == "subckt":
        out.append(f"SYMATTR SpiceModel {name}")
    else:
        out.append(f"SYMATTR Value {name}")
    out.append(f"SYMATTR ModelFile {model_file}")
    if description:
        out.append(f"SYMATTR Description {description}")

    # Pins (in declaration order; SpiceOrder = decl_index + 1)
    for pin in pins:
        x = pin["_x"] if pin["_x"] is not None else 0
        y = pin["_y"] if pin["_y"] is not None else 0
        orient = pin["_orient"] or "LEFT"
        offset = pin["_offset"] or 8
        out.append(f"PIN {x} {y} {orient} {offset}")
        out.append(f"PINATTR PinName {pin['name']}")
        out.append(f"PINATTR SpiceOrder {pin['_decl_index'] + 1}")

    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json-file", help="Path to JSON input (else stdin)")
    ap.add_argument("--out", help="Path to write .asy (else stdout)")
    args = ap.parse_args()

    if args.json_file:
        with open(args.json_file) as f:
            model = json.load(f)
    else:
        model = json.load(sys.stdin)

    asy = emit_asy(model)
    if args.out:
        Path(args.out).write_text(asy)
    else:
        sys.stdout.write(asy)
    return 0


if __name__ == "__main__":
    sys.exit(main())
