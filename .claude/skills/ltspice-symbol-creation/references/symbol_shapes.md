# Symbol shapes per part type

Drawing primitives for each detected part type. All coordinates are in
LTspice grid units (the .asy uses pixel coordinates where 16 px = 1 grid
square; coordinates here are pixel-space). The origin (0,0) is the symbol
anchor — typically near the geometric centre of the body so rotation
behaves sensibly.

These are reference shapes — `gen_asy.py` implements them. If a custom
shape is needed for a new part type, follow the same pattern: define the
LINE/RECTANGLE/CIRCLE/ARC list, then place pins on the perimeter.

## Op-amp (5-pin: +IN, −IN, V+, V−, OUT)

Triangle pointing right.

```
LINE Normal -32 -32 -32 32           ; back of triangle
LINE Normal -32 -32 32 0             ; top edge
LINE Normal -32 32 32 0              ; bottom edge
LINE Normal -28 -16 -20 -16          ; "+" horizontal stroke
LINE Normal -24 -20 -24 -12          ; "+" vertical stroke
LINE Normal -28 16 -20 16            ; "−" stroke

PIN -32 -16 LEFT 8     ; +IN  (SpiceOrder per .SUBCKT)
PIN -32 16  LEFT 8     ; -IN
PIN 0  -32 TOP 8       ; V+
PIN 0  32  BOTTOM 8    ; V-
PIN 32 0   RIGHT 8     ; OUT
```

For op-amps with more than 5 pins (offset null, EN, COMP, etc.), keep the
canonical 5 in their positions and pack the extras on the back edge
(left side, below the −IN pin) at 16-px spacing.

## Op-amp (4-pin: +IN, −IN, OUT, ground assumed) — rare

Same triangle, omit the V+ pin. Use only when the .SUBCKT genuinely has
4 pins.

## Comparator

Same triangle as op-amp. Add `(C)` text label inside the triangle to make
it visually distinguishable:

```
TEXT 8 0 Center 1 "C"
```

## Diode (2-pin: anode, cathode)

Triangle + bar pointing right (anode left → cathode right).

```
LINE Normal -16 -16 16 0              ; top edge of triangle
LINE Normal -16 16  16 0              ; bottom edge
LINE Normal -16 -16 -16 16            ; back edge
LINE Normal 16 -16 16 16              ; cathode bar
PIN -32 0 LEFT 8        ; A (anode)
LINE Normal -32 0 -16 0 ; lead from anode pin to body
PIN 32 0 RIGHT 8        ; K (cathode)
LINE Normal 16 0 32 0   ; lead from cathode bar to pin
```

For Zener: add a Z at the cathode bar:
```
LINE Normal 16 -16 24 -24
LINE Normal 16 16  8 24
```

For TVS (bidirectional): mirror the diode. Typically a 2-pin TVS .SUBCKT.

## BJT NPN (3-pin: collector, base, emitter)

```
CIRCLE Normal -16 -16 16 16              ; envelope (optional)
LINE Normal -8 -16 -8 16                 ; base bar
LINE Normal -8 -8 16 -16                 ; collector lead
LINE Normal -8 8  16 16                  ; emitter lead with arrow

; arrow on emitter (NPN: arrow points away from base)
LINE Normal 8 12 12 16
LINE Normal 12 16 6 18

PIN 16 -16 RIGHT 8       ; C
PIN -16 0  LEFT 8        ; B
LINE Normal -16 0 -8 0   ; lead from base pin to base bar
PIN 16 16  RIGHT 8       ; E
```

## BJT PNP

Same as NPN but reverse the emitter arrow direction (arrow points into
the base bar).

## NMOS (4-pin: D, G, S, B — or 3-pin: D, G, S)

```
LINE Normal -8 -16 -8 16                 ; gate bar
LINE Normal -4 -16 -4 -8                 ; channel top
LINE Normal -4 8   -4 16                 ; channel bottom
LINE Normal -4 -4  -4 4                  ; channel mid
LINE Normal -4 -12 16 -16                ; drain lead
LINE Normal -4 12  16 16                 ; source lead

; arrow on body (NMOS: arrow into the gate, pointing right)

PIN 16 -16 RIGHT 8       ; D (drain)
PIN -16 0 LEFT 8         ; G (gate)
LINE Normal -16 0 -8 0   ; gate lead
PIN 16 16 RIGHT 8        ; S (source)
PIN 16 8  RIGHT 8        ; B (body, optional)
```

## PMOS

Same as NMOS but the body arrow reverses, and conventionally:

- Drain is on the **bottom** (current flows from source-top to drain-bottom).
- Source is on the **top**.

This is purely visual — the SPICE order still follows the `.SUBCKT`
declaration.

## JFET (3-pin: D, G, S)

Like the BJT envelope without the emitter arrow.

## Voltage regulator / DC-DC converter (multi-pin IC, often 5–8 pins)

Generic rectangle. Pin placement follows the heuristics:

- VIN, VCC on top.
- GND on bottom.
- EN, FB on left.
- SW, OUT, BST/BOOT on right.

Body size: 96×64 for ≤6 pins; 96×96 for 7–10.

## Optocoupler (4-pin: anode, cathode, collector, emitter)

Two halves: LED on left, transistor on right, with an arrow showing the
optical path between them.

```
; LED on left
LINE Normal -32 -16 -16 0
LINE Normal -32 16  -16 0
LINE Normal -32 -16 -32 16
LINE Normal -16 -16 -16 16
; arrow showing emission (LED → transistor)
LINE Normal -8 -8  4 -16
LINE Normal -8 8   4 16
; arrowheads
LINE Normal 4 -16 -2 -14
LINE Normal 4 -16 0 -10

; transistor on right (NPN-style)
CIRCLE Normal 16 -16 48 16
LINE Normal 24 -16 24 16
LINE Normal 24 -8 48 -16
LINE Normal 24 8  48 16

PIN -48 -16 LEFT 8       ; A (anode)
PIN -48 16  LEFT 8       ; K (cathode)
PIN 48  -16 RIGHT 8      ; C (collector)
PIN 48  16  RIGHT 8      ; E (emitter)
```

## Generic IC / unknown subcircuit

Rectangle sized per pin count (see `pin_layout_heuristics.md`). Pins
distributed per layout heuristics (power top, GND bottom, inputs left,
outputs right). If the part type is uncertain, **always fall back to
this** rather than guessing.

```
RECTANGLE Normal -48 -32 48 32
PIN ... per layout heuristics
```

Also emit, inside the rectangle, a TEXT line with the model name so the
symbol is recognizable on a busy schematic:

```
TEXT 0 0 Center 1 "<MODEL_NAME>"
```

## Connector-like subcircuit (a row of pins, no body shape)

Just a vertical bar with N pin tips:

```
LINE Normal 0 <ymin> 0 <ymax>
PIN 0 <y1> RIGHT 8   ; PIN_1
PIN 0 <y2> RIGHT 8   ; PIN_2
...
```

## When to skip a custom symbol entirely

For these primitive `.MODEL` types, report to the user that **using
LTspice's built-in symbol** is cleaner than a custom one:

- `D` (use the built-in `diode`)
- `NPN`/`PNP` (use `npn` / `pnp`)
- `NMOS`/`PMOS` (use `nmos` / `pmos`)
- `NJF`/`PJF` (use `njf` / `pjf`)

The skill still generates a custom symbol so the user has an option, but
notes in the report that they can place the built-in primitive and just
add `.model <NAME> ...` as a directive on the schematic.
