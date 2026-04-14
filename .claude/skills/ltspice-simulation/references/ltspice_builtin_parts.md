# LTspice Built-in Parts Reference

Parts that ship with a default LTspice install. Use these names in `.model` / `.subckt` references so the generated `.cir` runs without external libraries.

When the user's schematic calls for a part that is NOT on this list, do one of two things:
1. Pick the closest electrical equivalent from this list and clearly comment the substitution.
2. Emit a `.subckt <PartName> … .ends` stub with the correct pin order and tell the user to paste in the vendor-provided SPICE model.

Never silently reference a part name that isn't in this file or in a stub — LTspice will fail to start the simulation and the user will be stuck decoding an opaque error.

---

## Diodes

Standard signal / rectifier / Schottky / Zener diodes available via `.model` in the standard library (`standard.dio`):

| Part | Type | Typical use |
|---|---|---|
| 1N4148 | Small signal | Fast switching, protection |
| 1N4001 … 1N4007 | Rectifier | Low-frequency mains rectification |
| 1N5817 | Schottky | Low-Vf rectifier |
| 1N5819 | Schottky | Low-Vf rectifier, 40 V |
| MBR0520 | Schottky SMD | Switcher output |
| BAT54 | Schottky SMD | Signal/low-power |
| BZX84C5V1 | Zener 5.1 V | Reference |
| 1N4733A | Zener 5.1 V | Power |

Card example: `D1 A K 1N4148`

## BJTs

Available in `standard.bjt`:

| Part | Polarity | Typical use |
|---|---|---|
| 2N3904 | NPN | General-purpose signal |
| 2N3906 | PNP | General-purpose signal |
| 2N2222 | NPN | Small-signal switch |
| 2N2907 | PNP | Small-signal switch |
| BC547 | NPN | General-purpose |
| BC557 | PNP | General-purpose |
| MMBT3904 | NPN SMD | Signal |
| TIP31 | NPN power | Audio, low-power drive |
| TIP32 | PNP power | Audio, low-power drive |

Card example (SPICE pin order: C B E): `Q1 NC NB NE 2N3904`

## MOSFETs

Available in `standard.mos`:

| Part | Channel | Vds | Notes |
|---|---|---|---|
| IRF540 | N | 100 V | Classic power N-FET |
| IRF9540 | P | 100 V | Classic power P-FET |
| IRF3205 | N | 55 V | Low-Rds(on) power |
| BS170 | N | 60 V | Small signal |
| BS250 | P | 45 V | Small signal |
| Si4410DY | N | 30 V | Laptop-class |
| 2N7002 | N SMD | 60 V | Logic-level signal |

Card example (pin order: D G S B; B often tied to S internally): `M1 ND NG NS NS IRF540`

## JFETs

| Part | Channel | Typical use |
|---|---|---|
| 2N5457 | N | Audio, small-signal |
| 2N3819 | N | Audio, small-signal |
| J113 | N | Switch |

## Op-amps (subcircuits shipped in `cmp/standard.bjt` / `cmp/LTC/` / universal opamps)

Use `X<name>` with the correct pin order. LTspice ships universal op-amp macromodels (`UniversalOpAmp2`) plus Analog Devices / Linear Technology parts. For generic parts like LM358, LM741, TL072, TL084, the safest approach is:

**Preferred:** Use `UniversalOpAmp2` with parameters set to match the target part's GBW and slew rate. Pin order is `+, -, V+, V-, OUT`.

Example:
```
XU1 Nplus Nminus VCC VEE OUT UniversalOpAmp2 Avol=1Meg GBW=1.1Meg Slew=0.5Meg
```

**If a specific AD/LT part is called out** and is known to be in the LTspice library (LT1001, LT1028, LT1013, LT1078, AD8601, AD820, etc.), reference it by part name with pin order `+, -, V+, V-, OUT`.

**For LM358 / LM741 / TL072 / TL084 / NE5532** (not in the default lib), emit a `UniversalOpAmp2` call with parameters matching the part, and add a comment: `* LM358 modeled as UniversalOpAmp2 with GBW=1.1MHz; swap in TI model for precision work`.

## Voltage regulators

LTspice ships subcircuits for the classic linear regulators: `LM317`, `LT1086`, `LT3080`, plus many switchers from AD/LT. For `LM7805` / `LM7812` which are NOT in the default library, emit a behavioral macromodel:

```
* LM7805 behavioral model
.subckt LM7805 IN OUT GND
Vfixed OUT GND 5.0
...
.ends
```

## Timers

`NE555` is not in the base library by default in all versions. Emit a subckt stub or use a behavioral model built from comparators and an SR latch. Comment the assumption.

## Passives, sources, controlled sources

All primitive — no model required:

- `R<n> n1 n2 <value>`
- `C<n> n1 n2 <value> [ic=<V0>]`
- `L<n> n1 n2 <value> [ic=<I0>]`
- `V<n> n1 n2 DC <V>` / `V<n> n1 n2 AC 1` / `V<n> n1 n2 SINE(<offset> <amp> <freq>)` / `V<n> n1 n2 PULSE(<V1> <V2> <Td> <Tr> <Tf> <Ton> <Tper>)`
- `I<n>` same pattern as V
- `E<n>` (VCVS), `G<n>` (VCCS), `H<n>` (CCVS), `F<n>` (CCCS)

## Engineering-notation cheatsheet (LTspice-safe)

| You see in image | Write in netlist |
|---|---|
| 10 Ω | 10 |
| 4.7 kΩ | 4.7k |
| 1 MΩ | 1Meg |
| 1 mΩ | 1m |
| 1 µF | 1u |
| 100 nF | 100n |
| 1 pF | 1p |
| 1 mH | 1m |
| 1 µH | 1u |
| 1 GHz | 1G |

Never `M` for mega (that means milli in SPICE), never `µ` (use `u`), never `Ω` (omit the unit).
