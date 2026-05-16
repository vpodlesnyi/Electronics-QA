# LTspice .asy file format reference

This is a working reference for the `.asy` file format. Read it before
hand-editing or extending `gen_asy.py`. Numbers are in LTspice's native
schematic grid (1 grid square = 16 px). All coordinates are integers.

## Top-level structure

```
Version 4
SymbolType <CELL | BLOCK>
LINE Normal x1 y1 x2 y2
RECTANGLE Normal x1 y1 x2 y2
CIRCLE Normal x1 y1 x2 y2
ARC Normal x1 y1 x2 y2 ax1 ay1 ax2 ay2
TEXT x y Left|Center|Right size "string"
WINDOW <id> dx dy Left|Center|Right size
SYMATTR <key> <value>
PIN x y NONE 8
PINATTR PinName <name>
PINATTR SpiceOrder <n>
```

The file is plain ASCII (LTspice on Windows reads CRLF or LF).

## Section ordering

LTspice is strict about ordering. The skill emits sections in this order:

1. `Version 4`
2. `SymbolType CELL` (for subcircuits and primitives — almost always `CELL`).
3. **Body geometry** — every `LINE`, `RECTANGLE`, `CIRCLE`, `ARC` for the
   visible shape. Order within this block doesn't matter, but keeping it
   consistent helps diffs.
4. **WINDOW overrides** — relocate the default attribute text positions if
   the defaults overlap the body. One `WINDOW` line per attribute the user
   wants moved. WINDOW IDs: `0` = InstName, `3` = Value, `38` = SpiceModel,
   `39` = SpiceLine, `123` = SpiceLine2.
5. **SYMATTR block** — `Prefix`, `SpiceModel`, `Value`, `Value2`,
   `ModelFile`, `Description`, `SpiceLine`, `SpiceLine2`. Order is
   conventional but LTspice tolerates any order in this block.
6. **PIN blocks** — for each pin: a `PIN` line followed immediately by
   `PINATTR PinName ...` then `PINATTR SpiceOrder ...`. **The order of PIN
   blocks in the file does not affect SpiceOrder** — SpiceOrder comes from
   the PINATTR line. But for sanity, emit PINs in the same order as the
   `.SUBCKT` declaration.

## SymbolType

- `CELL` — drop-in symbol that places one instance of a model. Use for
  `.SUBCKT`s and for primitive `.MODEL`s with custom shapes.
- `BLOCK` — hierarchical block; the user double-clicks to open another
  schematic. **Not used by this skill.**

## Body geometry

Coordinates are LTspice's grid units (16 px per grid square). The origin is
the symbol's anchor point — usually placed roughly at the geometric centre
of the body so rotation behaves sensibly.

### LINE

```
LINE Normal x1 y1 x2 y2
```

Draws a straight line. The second token (`Normal`) is the line style and is
almost always `Normal`. Other values exist (`Dot`, `Dash`) but they are
rarely useful for symbols.

### RECTANGLE

```
RECTANGLE Normal x1 y1 x2 y2
```

Axis-aligned rectangle with corners `(x1,y1)` and `(x2,y2)`. LTspice
normalizes the corners — order doesn't matter.

### CIRCLE

```
CIRCLE Normal x1 y1 x2 y2
```

Bounding-box ellipse. `(x1,y1)` and `(x2,y2)` are the corners of the
bounding box; LTspice draws the inscribed ellipse.

### ARC

```
ARC Normal x1 y1 x2 y2 ax1 ay1 ax2 ay2
```

Bounding-box arc, with two extra points defining the start and end
positions (in the same coordinate space as the bounding box).

### TEXT

```
TEXT x y Left|Center|Right 2 "literal string"
```

Static text drawn on the symbol body (not an attribute — see WINDOW for
attribute placement). The size token (`2` is the conventional default) maps
to LTspice font sizes 0..7.

## WINDOW

```
WINDOW <id> dx dy <Left|Center|Right> <size>
```

Relocates the default position of an attribute display. `id` selects which
attribute:

| ID | Attribute |
|---|---|
| 0 | InstName (e.g., `U1`, `Q3`) |
| 3 | Value (the user-editable value) |
| 38 | SpiceModel |
| 39 | SpiceLine |
| 123 | SpiceLine2 |

`dx`/`dy` are offsets from the symbol's anchor (origin), in pixels (not
grid units). `Left`/`Center`/`Right` is text alignment. `size` is the font
size token (typically `2`).

If you don't emit a WINDOW line for an attribute, LTspice uses its built-in
default, which often overlaps the symbol body for non-standard shapes —
that's why this skill emits WINDOW lines explicitly.

## SYMATTR

```
SYMATTR <key> <value>
```

Symbol-level attributes. Keys this skill emits:

| Key | Meaning | Example |
|---|---|---|
| `Prefix` | SPICE device letter (`X`, `D`, `Q`, `M`, `J`, …). Determines what kind of SPICE card LTspice writes when the symbol is placed. | `X` |
| `SpiceModel` | Name of the model/subcircuit to instantiate. Must exactly match the `.SUBCKT` name (case-sensitive on Linux LTspice). | `LM358` |
| `Value` | Used for primitive `.MODEL` symbols (`D`, `Q`, etc.) — names the model to use. | `1N4148` |
| `Value2` | Secondary value. For some symbols this is the subcircuit call. | `MY_OPAMP` |
| `ModelFile` | Filename of the library to auto-include when the symbol is placed. **Use a bare filename; never an absolute path.** LTspice searches the schematic directory and the symbol's own directory. | `LM358.lib` |
| `Description` | One-line human description shown in the placement dialog. | `Dual op-amp, 32 V, 700 kHz GBW` |
| `SpiceLine` | Free-form text appended to the SPICE device card. Useful for default parameters. | `Avol=1Meg GBW=700k` |

## PIN and PINATTR

```
PIN x y <orientation> <name-offset>
PINATTR PinName <name>
PINATTR SpiceOrder <n>
```

A pin block is exactly one `PIN` line followed by one or two `PINATTR`
lines (PinName is required; SpiceOrder is required for `CELL` symbols).

- `x`, `y` — pin tip coordinates in LTspice grid units. The pin name label
  is drawn relative to this point.
- `<orientation>` — the side that the pin name label sits on. Options:
  - `NONE` — name not displayed (rarely used; useful for invisible test
    points).
  - `LEFT` — label drawn to the left of the tip (pin enters from the right).
  - `RIGHT`, `TOP`, `BOTTOM` — same idea.
- `<name-offset>` — distance in pixels between the pin tip and the start
  of the label. Default `8`.

### SpiceOrder

`PINATTR SpiceOrder N` is the **node position** that this pin maps to in
the SPICE call. For a `.SUBCKT NAME a b c d`, you must have:

| Pin name | SpiceOrder |
|---|---|
| `a` | 1 |
| `b` | 2 |
| `c` | 3 |
| `d` | 4 |

This mapping is the entire reason this skill exists. **A wrong SpiceOrder
will not produce an LTspice error** — the symbol places fine and simulation
runs — but the model is wired internally to the wrong nodes. The user sees
a circuit that compiles and behaves nothing like the part they expected.

This is why `validate.py` checks SpiceOrder uniqueness, completeness, and
declaration-order match before stamping a package `READY`.

## Minimal example — generic 5-pin op-amp

```
Version 4
SymbolType CELL
LINE Normal -32 -32 -32 32
LINE Normal -32 -32 32 0
LINE Normal -32 32 32 0
LINE Normal -28 -16 -20 -16
LINE Normal -24 -20 -24 -12
LINE Normal -28 16 -20 16
WINDOW 0 16 -32 Left 2
WINDOW 3 16 32 Left 2
SYMATTR Prefix X
SYMATTR SpiceModel LM358
SYMATTR ModelFile LM358.lib
SYMATTR Description Dual op-amp, 32 V, 700 kHz GBW
PIN -32 -16 LEFT 8
PINATTR PinName +IN
PINATTR SpiceOrder 1
PIN -32 16 LEFT 8
PINATTR PinName -IN
PINATTR SpiceOrder 2
PIN 0 -32 TOP 8
PINATTR PinName V+
PINATTR SpiceOrder 3
PIN 0 32 BOTTOM 8
PINATTR PinName V-
PINATTR SpiceOrder 4
PIN 32 0 RIGHT 8
PINATTR PinName OUT
PINATTR SpiceOrder 5
```

## Common mistakes

- **Hardcoded paths in `ModelFile`**: `C:\Users\foo\Downloads\LM358.lib`.
  Use a bare filename. LTspice searches the schematic dir and the `.asy`
  dir.
- **Mismatched case**: `SpiceModel lm358` paired with `.SUBCKT LM358`.
  Linux LTspice cares; Windows LTspice tolerates.
- **Pins on the body interior**: pin tips must be on the body perimeter or
  outside. A pin tip inside a `RECTANGLE` is hard to wire to.
- **Body too small for the pin count**: 8 pins on a 32×32 rectangle leaves
  no space between pin labels.
- **Using `WINDOW` IDs for attributes you didn't define**: a `WINDOW 38 ...`
  line with no `SpiceModel` attribute does nothing.
