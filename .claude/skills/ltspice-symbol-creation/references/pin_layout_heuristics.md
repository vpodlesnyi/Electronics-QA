# Pin layout heuristics

Rules for placing pins around the symbol body and inferring pin function
from the pin name. Used by `gen_asy.py` (placement) and `parse_spice.py`
(function inference for the readback).

## Pin-name aliases

Real-world SPICE models use wildly inconsistent pin naming. The skill
recognizes the following equivalence classes. Match is case-insensitive,
and matches against the **whole pin name** unless noted.

### Power supply (positive)

`VCC`, `VDD`, `VS`, `VSS+`, `V+`, `VP`, `VPOS`, `VPLUS`, `+VS`, `VBAT`,
`VIN+`, `VAA`, `AVCC`, `DVCC`, `VCCA`, `VCCD`, `VDDA`, `VDDD`, `+V`,
`POWER`.

Layout rule: **top side** of the symbol body.

### Power supply (negative / ground)

`GND`, `VSS`, `VEE`, `V-`, `VN`, `VNEG`, `VMINUS`, `-VS`, `0`, `COM`,
`AGND`, `DGND`, `PGND`, `EGND`, `GND_A`, `GND_D`, `RTN`, `RETURN`,
`-V`.

Layout rule: **bottom side** of the symbol body.

### Inputs

Generic: `IN`, `INPUT`, `SIG`, `SIGNAL`, `VIN`, `INA`, `INB`, `IN1`,
`IN2`.

Differential / op-amp inputs:

- **Non-inverting (+):** `IN+`, `+IN`, `INP`, `IN_P`, `NONINV`, `INNI`,
  `INA+`, `+INPUT`, `VINP`.
- **Inverting (−):** `IN-`, `-IN`, `INN`, `IN_N`, `INV`, `INA-`,
  `-INPUT`, `VINM`.

Control: `EN`, `ENABLE`, `CTRL`, `CONTROL`, `SHDN`, `~SHDN`, `~CS`, `CS`,
`SLEEP`, `STBY`, `MODE`, `SEL`, `RESET`, `~RESET`.

Feedback: `FB`, `FEEDBACK`, `FBO`, `COMP`, `COMPENSATION`.

Layout rule: **left side**.

Ordering on the left side: keep the order they appear in the `.SUBCKT`
declaration. Do not reorder, even if it would put `+IN` above `−IN` for
visual cleanliness — declaration order dominates.

### Outputs

Generic: `OUT`, `OUTPUT`, `VOUT`, `OUTA`, `OUTB`, `OUT1`, `OUT2`, `Y`, `Q`.

Power-stage outputs: `SW`, `LX`, `BST`, `BOOT`, `DRV`, `DRIVE`, `GATE`,
`HSD`, `LSD` (high-/low-side drive), `PHASE`.

Layout rule: **right side**.

### Specific device pins

Diodes: `A`/`AN`/`ANODE` (label as `A`); `K`/`CA`/`CATHODE` (label as `K`).

BJTs: `B`/`BASE`, `C`/`COLLECTOR`/`COL`, `E`/`EMITTER`/`EMIT`. Pin order in
LTspice's convention is C, B, E, but the .SUBCKT declaration may use any
order — follow the declaration.

MOSFETs: `D`/`DRAIN`, `G`/`GATE`, `S`/`SOURCE`, `B`/`BULK`/`BODY`. Layout
rule for MOSFETs: G on the left, D on the top (NMOS) / bottom (PMOS), S on
the bottom (NMOS) / top (PMOS), B on the right if present.

JFETs: `D`/`DRAIN`, `G`/`GATE`, `S`/`SOURCE`. Same layout as MOSFET.

Op-amps (5-pin): `+IN` left-top, `−IN` left-bottom, `V+` top, `V−` bottom,
`OUT` right.

Op-amps (more than 5 pins — has `EN`, `BIAS`, `OS1`/`OS2` for offset null,
etc.): keep the standard 5 in their canonical positions; pack the extras
on the side that has space.

## Geometric placement

Symbol body is a rectangle of dimensions chosen to fit the pin count:

| Pin count | Suggested body size |
|---|---|
| ≤ 4 | 64 × 64 |
| 5–6 | 96 × 64 |
| 7–10 | 96 × 96 |
| 11–16 | 128 × 128 |
| 17–24 | 160 × 160 |
| > 24 | 192 × 192 (and consider that the user may want a custom layout) |

Pin spacing: pins on the same side spaced at least 16 px apart; for 8 or
fewer pins on a side, use 32 px spacing for readability.

Pin tip coordinates are at the body perimeter. The pin's invisible
extension into the body is implicit — do not draw a line from the body
edge to the pin tip; LTspice does that visually.

## Polarity inference and confidence

When the readback reports an inferred pin function:

- **High confidence**: pin name is in the alias table, exact match. Don't
  bug the user — proceed.
- **Medium confidence**: pin name matches an alias as a substring (e.g.,
  `VCC1` matches `VCC` family). Note in the report; proceed without
  asking.
- **Low confidence**: pin name doesn't match any alias (e.g., `N1`, `A`,
  `RES_BIAS`). Note in the report and surface in the "please confirm"
  block — for op-amps and other parts where polarity matters, **ask
  before placing**.

## Special cases

### Differential pair with no `+`/`−` indicator

E.g., `.SUBCKT MYAMP A B V+ V- OUT`. The model file's comments may identify
which is non-inverting; if not, default to **A = non-inverting, B =
inverting** but flag this in the report at low confidence and ask the user.
Half the world's models follow this convention; the other half don't.

### Pins named purely numerically (1, 2, 3, …)

Common in vendor models because the pin numbers correspond to the IC's
package pinout. The skill should:

1. Keep the original numeric names as PinName so they match the datasheet
   pinout.
2. Set SpiceOrder = declaration order (which usually equals the pin number
   for vendor models, but not always — verify).
3. In the report, suggest the user cross-check against the datasheet
   pinout.

### Pins named with leading punctuation that LTspice may misread

LTspice tolerates `+IN`, `-IN`, `V+`, `V-` in PinName, but they look weird
in some places. Preserve them — never silently change `V+` to `VP`. The
user expects to wire to the same name they see in the model.

### More pins than the body has perimeter for

If the suggested body size still doesn't give enough perimeter for the pin
count at 16-px spacing, scale the body up. Don't pack pins closer than 16
px — they overlap visually.
