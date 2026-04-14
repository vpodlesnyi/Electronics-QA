# LTspice Built-in Parts Reference

## How to look up a part before writing any `.model` card

**LTspice 26+ ships its entire model library inside a single `lib.zip`** at the install root
(`%LOCALAPPDATA%\Programs\ADI\LTspice\lib.zip` on Windows). The old loose files
(`standard.bjt`, `standard.mos`, etc.) no longer exist on disk — so you cannot assume a
part name "just works" anymore.

> **Encoding note:** Files inside `lib.zip` use mixed encodings — `lib/cmp/standard.bjt`
> and `lib/cmp/standard.mos` are **UTF-16-LE** (null-byte interleaved); `lib/cmp/standard.dio`
> is **latin-1**. `query_lib.py` handles this automatically. If you read these files manually,
> detect UTF-16-LE with: `if len(raw) >= 4 and raw[1] == 0 and raw[3] == 0`. Plain `latin-1`
> or `utf-8` decoding will silently fail to match any BJT or MOSFET names.

**Always run the lookup script first:**

```
python scripts/query_lib.py <part_name>
```

Then follow the priority ladder:

| Lookup result | What to write in the .cir | What to write in the .asc |
|---|---|---|
| Found in `lib/sub/*.sub` as a `.subckt` | `X<n> <pins> <subckt_name>` — LTspice auto-finds it | `SYMBOL <path>` if a matching .asy exists |
| Found in `lib/sub/*.sub` or `lib/cmp/*` as a `.model` | device card `Q/M/D <pins> <model_name>` — no embed needed | same |
| Found only as `lib/sym/**/*.asy` (symbol, SpiceModel points to a .sub) | `X<n> <pins> <subckt_call_from_Value2>` | `SYMBOL <sym_path>` |
| **Not found anywhere in lib.zip** | Embed full `.model` or `.subckt` inline in the .cir | Draw manually or use a generic symbol |

**Do not embed a custom `.model` for a part that already lives in `lib.zip`.**
LTspice will load its own version anyway, and a duplicated definition causes a parse error.

---

## Optocouplers — [Optos] library

These are available as ready-made subcircuits. **No custom model needed.**

| Symbol path | Part | CTR grade | Igain | SpiceModel | .cir call |
|---|---|---|---|---|---|
| `Optos/PC817A` | PC817A | A (80–160 %) | 1m | PC817.sub | `X<n> A K C E PC817` |
| `Optos/PC817B` | PC817B | B (130–260 %) | 1.5m | PC817.sub | `X<n> A K C E PC817` |
| `Optos/PC817C` | PC817C | C (200–400 %) | 2.3m | PC817.sub | `X<n> A K C E PC817` |
| `Optos/PC817D` | PC817D | D (300–600 %) | 3.4m | PC817.sub | `X<n> A K C E PC817` |
| `Optos/4N25`   | 4N25   | — | — | 4N25.sub | see .asy |
| `Optos/4N25A`  | 4N25A  | — | — | 4N25.sub | see .asy |
| `Optos/4N26`   | 4N26   | — | — | — | see .asy |
| `Optos/4N27`   | 4N27   | — | — | — | see .asy |
| `Optos/4N28`   | 4N28   | — | — | — | see .asy |
| `Optos/CNY17-1`| CNY17-1 | — | — | — | see .asy |
| `Optos/CNY17-2`| CNY17-2 | — | — | — | see .asy |
| `Optos/CNY17-3`| CNY17-3 | — | — | — | see .asy |
| `Optos/MOC205` | MOC205 | — | — | — | see .asy |
| `Optos/MOC206` | MOC206 | — | — | — | see .asy |
| `Optos/MOC207` | MOC207 | — | — | — | see .asy |

Substitution tip: HCPL-817-300E has minimum CTR = 300 %, matching **PC817D** (`Igain=3.4m`).

> **Critical: symbol name ≠ subcircuit name.** The `.asy` files are named `PC817A`, `PC817B`, etc., but all share a single subcircuit named `PC817` inside `PC817.sub`. The CTR grade is encoded via the `Igain` parameter. In `.cir`, always write:
> ```
> XDA1  A K C E  PC817 Igain=3.4m      ; PC817D grade (CTR 300–600%)
> ```
> Never `PC817D` as the subcircuit name — that will fail with "unknown subckt".
>
> `query_lib.py` will show `Value2 = "PC817 Igain=3.4m"` for the PC817D symbol — copy that as-is into the X-call.

---

## Diodes

**Run `query_lib.py <part>` first.** Common small-signal and rectifier diodes are typically
included in LTspice's `lib/cmp/` — if found, reference by name with no embed.

Parts known to be present in most LTspice installs (verify with query_lib.py):

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

Card syntax: `D1 anode cathode <model_name>`

---

## BJTs

> **LTspice 26 note:** `standard.bjt` no longer exists as a loadable file.
> Run `query_lib.py <part>` before assuming a BJT name auto-resolves.
> If the part is not found in lib.zip, **embed the `.model` card inline** in the .cir.

Parts commonly requested — check lib.zip first, embed if absent:

| Part | Polarity | Typical use |
|---|---|---|
| 2N3904 | NPN | General-purpose signal |
| 2N3906 | PNP | General-purpose signal |
| 2N2222 | NPN | Small-signal switch |
| 2N2907 | PNP | Small-signal switch |
| BC547B | NPN | General-purpose, Bf≈294 (in lib.zip as `BC547B`) |
| BC547C | NPN | General-purpose, Bf≈459 (in lib.zip as `BC547C`) |
| BC557B | PNP | General-purpose (in lib.zip as `BC557B`) |
| MMBT3904 | NPN SMD | Signal |
| TIP31 | NPN power | Audio, low-power drive |
| TIP32 | PNP power | Audio, low-power drive |

Card syntax (pin order: C B E): `Q1 NC NB NE <model_name>`

---

## MOSFETs

> **LTspice 26 note:** `standard.mos` no longer exists as a loadable file.
> Run `query_lib.py <part>` before assuming a MOSFET name auto-resolves.
> If the part is not found in lib.zip, **embed the `.model` card inline** in the .cir.

Parts commonly requested — check lib.zip first, embed if absent:

| Part | Channel | Vds | Notes |
|---|---|---|---|
| IRF540  | N | 100 V | Classic power N-FET |
| IRF9540 | P | 100 V | Classic power P-FET (not in LTspice 26 lib.zip — embed model) |
| IRF3205 | N | 55 V | Low-Rds(on) power |
| BS170   | N | 60 V | Small signal |
| BS250   | P | 45 V | Small signal |
| 2N7002  | N SMD | 60 V | Logic-level signal |

Card syntax (pin order: D G S B): `M1 ND NG NS NS <model_name>` (bulk usually tied to source)

---

## JFETs

| Part | Channel | Typical use |
|---|---|---|
| 2N5457 | N | Audio, small-signal |
| 2N3819 | N | Audio, small-signal |
| J113   | N | Switch |

---

## Op-amps

LTspice ships macromodels for Analog Devices / Linear Technology parts in `lib/sub/`.
Run `query_lib.py <part>` — if found, reference by name. If not found, use the universal model:

**Preferred for generic parts (LM358, LM741, TL072, NE5532):**
```
XU1 Nplus Nminus VCC VEE OUT UniversalOpAmp2 Avol=1Meg GBW=1.1Meg Slew=0.5Meg
```
Pin order: `+, -, V+, V-, OUT`.

**If a specific AD/LT part exists in lib.zip** (LT1001, LT1028, LT1013, AD8601, etc.),
reference it directly: `XU1 + - V+ V- OUT LT1028`

---

## Voltage regulators

LTspice ships: `LM317`, `LT1086`, `LT3080`, and many AD/LT switchers.
Run `query_lib.py` first. For `LM7805` / `LM7812` (not in lib), emit a behavioral model:

```spice
.subckt LM7805 IN OUT GND
Vfixed OUT GND 5.0
.ends
```

---

## Passives, sources, controlled sources

Always primitives — no model or lib lookup needed:

- `R<n> n1 n2 <value>`
- `C<n> n1 n2 <value> [ic=<V0>]`
- `L<n> n1 n2 <value> [ic=<I0>]`
- `V<n> n1 n2 DC <V>` / `SINE(…)` / `PULSE(…)` / `PWL(…)`
- `E` (VCVS), `G` (VCCS), `H` (CCVS), `F` (CCCS)

---

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

Never `M` for mega (that means milli in SPICE). Never `µ` (use `u`). Never `Ω`.
