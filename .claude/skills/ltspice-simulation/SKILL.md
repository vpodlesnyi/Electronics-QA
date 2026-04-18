---
name: ltspice-simulation
description: Use this skill whenever the user provides a schematic image (.png, .jpg, .bmp, or screenshot) of an analog, power, mixed-signal, or small digital circuit and wants it simulated, analyzed, or verified. Trigger aggressively on phrases like "simulate this circuit", "run this in LTspice", "make a SPICE netlist from this schematic", "what does this circuit do" (with image), "verify my design", "ltspice", ".cir", "SPICE netlist", "op-amp simulation", "filter response", "transient analysis", "Bode plot", "transfer function" — and on ANY uploaded schematic image where simulation intent is implied. The skill vision-reads the schematic, produces a plain-English readback of every component and net, asks the user to confirm ambiguity BEFORE writing SPICE, then emits a runnable LTspice .cir netlist with an analysis directive (.op/.tran/.ac/.dc/.noise) inferred from topology. On Windows, auto-launches LTspice with the netlist. Do NOT use for PCB layout, BOM sourcing (use bom-qa), or pure digital/HDL simulation.
---

# ltspice-simulation

Convert a schematic image into a runnable LTspice `.cir` netlist, with an inferred analysis directive, and (on Windows) auto-launch LTspice with the circuit loaded.

## What this skill is for

The user has a picture of a circuit — a screenshot from KiCad/Altium/EasyEDA, a photo of a whiteboard or paper sketch, or an image pulled from a datasheet or textbook — and wants to simulate it. The skill bridges three gaps that normally require an experienced analog engineer:

1. **Reading components, values, and connectivity from a picture.** Vision is noisy: resistor color bands can be ambiguous, handwriting is sloppy, and symbols vary between conventions. Getting this right is the single most important thing the skill does.
2. **Writing syntactically-correct SPICE that LTspice will actually run.** Correct device letters, built-in model references, engineering-notation values (no unicode µ), valid node names, `.end` at the bottom.
3. **Choosing a reasonable first-pass analysis** so the user sees meaningful results instead of a blank plot.

## Repository I/O convention

This skill lives in the `electronics-qa` repository and uses fixed folders for input and output. Respect them; do not scatter files elsewhere.

- **Input — schematic images:** `INPUT/SCH/` (relative to the repository root). Pick up `.png`, `.jpg`, `.jpeg`, or `.bmp` files from here. If the user refers to "the schematic" or "my circuit" without naming a file, list what's in `INPUT/SCH/` and confirm which one they mean before proceeding.
- **Output — generated schematics:** `OUTPUT/SCH/`. Write every `.asc` here (`.cir` only when the user explicitly requests a plain netlist). Name the file after the source image's stem (e.g. `INPUT/SCH/preamp_v2.png` → `OUTPUT/SCH/preamp_v2.asc`). Keep names slug-safe (ASCII, no spaces, only `_` or `-` as separators).
- **Sidecar artifacts** (readback.md, simulation_notes.md) are allowed next to the `.asc` in `OUTPUT/SCH/` only if the user asks for them. By default, emit the readback inline in chat and keep `OUTPUT/SCH/` to just the deliverable files.

If either folder doesn't exist yet, create it. Never save final deliverables to the repository root or to `/tmp`.

## The non-negotiable workflow

Always follow these steps in order. Do not skip the readback. The reason this order is load-bearing: vision models hallucinate components and values, and emitting SPICE based on a hallucination wastes the user's time and erodes their trust. A two-minute readback prevents a half-hour of debugging a phantom circuit.

### Step 1 — Vision-read the schematic

Locate the image in `INPUT/SCH/`. If the user named a file, use that; otherwise list what's there and confirm the target before reading. Open the image and catalogue everything you see:

- Every component symbol with its reference designator (R1, C3, Q2, U1…). If a refdes is missing from the image, assign one (R? → R1 in the order you encounter it, top-left to bottom-right).
- Every printed value and unit. Keep the unit the user wrote (10k, 4.7uF, 1N4148, LM358).
- Every net and rail. Use the labels printed on the schematic where they exist; otherwise invent readable names (`IN`, `OUT`, `N001`, `N002`…). `GND` and `0` both mean node 0. `VCC`, `VEE`, `VDD`, `VSS` are reserved for power rails.
- Every source: DC supply, signal generator, pulse, PWL, with amplitude / frequency / offset / rise-fall times if shown.
- Any stimulus the user has described in text alongside the image.

Zoom in mentally on the hard parts: transistor pinouts (which leg is base/collector/emitter), op-amp input polarity (which pin is `+`), electrolytic polarity, diode orientation. These are the places mistakes matter most.

### Step 2 — Produce the readback and pause

Before writing any SPICE, emit this structure:

1. **One-line circuit summary.** What is this? ("Single-supply non-inverting op-amp amplifier, gain ≈ 11, AC-coupled input.")
2. **Component table.** Columns: RefDes | Type | Value / Part | Between nets.
3. **Net list.** Each net, and what connects to it.
4. **Sources and stimuli.** Everything driving the circuit.
5. **Please confirm or correct block.** Every assumption you made, every label you couldn't read cleanly, every unknown part. Ask explicitly.

Then **stop**. Do not write the `.cir` yet. Ask the user to confirm or correct. If the user is silent, ask once more rather than guessing. The reason: the user knows their circuit; you are reading pixels. Cheap to ask, expensive to invent.

### Step 3 — Infer the analysis directive

Once the readback is confirmed, pick an analysis type based on topology. Use this table as a guide, not a cage — if the user told you what they want ("I just want the operating point"), follow them:

| Topology / signal type | Directive | Why |
|---|---|---|
| Pure DC bias, no reactive elements, no signal source | `.op` | Only an operating point is meaningful. |
| Amplifier (op-amp, BJT/FET small-signal), AC source, or user mentions gain/bandwidth/frequency response | `.ac dec 100 1 10Meg` + `.op` | Bode-style sweep. |
| Oscillator, switching converter, PWM, 555 timer, pulse/PWL source, or any explicitly time-domain question | `.tran 0 <~10 periods> 0 <period/1000>` | Transient with sensible stop time and maxstep. |
| Passive filter with reactive elements and AC source | `.ac dec 100 <f_low> <f_high>` with limits from component values | Transfer function. |
| Circuit parameterized by a DC sweep (pot, load) | `.dc V1 <min> <max> <step>` | Parametric. |
| Low-noise / sensor front-end with "noise" hint | `.noise V(out) V1 dec 100 1 1Meg` | Input-referred noise. |

Also add `.save` for every labeled net so the waveform viewer shows useful probes.

### Step 4 — Emit the `.cir` netlist

#### 4a — Library-first lookup (mandatory, do this before writing any `.model` card)

For **every semiconductor or IC** in the circuit, run:

```
python scripts/query_lib.py <part_name>
```

Then follow this priority ladder — **stop at the first tier that matches:**

| Tier | Condition | Action |
|---|---|---|
| **1 — Library subcircuit** | `query_lib.py` reports the part in `lib/sub/*.sub` as a `.subckt` | Write `X<n> <pins> <subckt_name>` in the .cir. LTspice finds it from lib.zip automatically — no `.lib` directive, no embedded model. |
| **2 — Library model** | `query_lib.py` reports the part in `lib/cmp/*` as a `.model` | Write the device card (`Q`, `M`, `D`, …) referencing that model name. No embed needed. |
| **3 — Symbol only** | `query_lib.py` finds a `lib/sym/**/*.asy` with a `SpiceModel` pointing to a `.sub` | The `.sub` is also in lib.zip. Use the `Value2` subcircuit call shown by the script. Prefer using the symbol in the `.asc`; for `.cir`, use the X-call shown. |
| **4 — Internet vendor model** | `query_lib.py` exits 1 (no match in lib.zip) | Search the web for a SPICE model published by the component manufacturer (e.g. ON Semi, Vishay, Infineon, Broadcom). Preferred sources in order: (a) manufacturer's product page → "SPICE model" or "simulation model" download; (b) well-known SPICE model archives (Spice Models DB, LTspice Users Group, component distributor model libraries). Download or copy the `.model` / `.subckt` text, embed it inline in the `.cir`, and add a comment crediting the source URL and retrieval date. |
| **5 — Library alternative** | Vendor model not found on the internet, but a functionally similar part exists in lib.zip | Choose a lib.zip part with matching topology (same device type: NPN/PNP/NMOS/PMOS/diode), similar key parameters (Vce_max or Vds_max, Ic_max or Id_max, hFE or Vth), and the same package type if relevant. Reference it by its lib.zip name. Add a prominent `* SUBSTITUTE:` comment naming the original part, the substitute used, and which parameters may differ. |
| **6 — Internet alternative** | Lib.zip has no close match either | Search the web for a SPICE model of a functionally equivalent part from a different manufacturer. Apply the same substitution comment rules as Tier 5. |
| **7 — Custom model (last resort)** | All of the above have failed | Only now hand-craft a `.model` or `.subckt` from datasheet parameters. Comment every parameter and its datasheet source. This is the last resort — do not reach for it while any of Tiers 1–6 remain viable. |

> **Why this order matters:** LTspice 26 no longer ships `standard.bjt` / `standard.mos` as loadable files — only `lib.zip`. A model name that "worked in LTspice XVII" will silently fail in LTspice 26 unless the library file is present or the model is embedded. Tiers 1–3 use the vendor-validated model from lib.zip. Tiers 4–6 leverage real SPICE models from the internet or close lib.zip equivalents before resorting to a hand-crafted model, which is the least reliable path.

#### 4b — Generate the .asc schematic

Use `scripts/gen_asc.py` (see Bundled assets). The script encodes pin geometry, stub/bus rules, and SPICE directives for the circuit. When adding a new circuit, update or extend gen_asc.py following the rules in `references/asc_generation_rules.md`.

**Mandatory rules (full detail in asc_generation_rules.md):**
- Every pin has a 48 px (3-grid) stub exiting *away from* the component body. Body clearance always wins over stub clearance.
- Derive symbol origin from pin-landing math: `SX = node_x − rot(local_pin_x, local_pin_y, R)[0]`. Never hardcode.
- PMOS S-pin stubs DOWN (`sdn`), never up. Detour in x before routing up to supply rail.
- Power/GND rails use one horizontal bus wire + one flag per rail. No per-component flags.
- Isolated ground domains get separate bus wires with a gap — never connected.
- No `.options gmin` / `.options abstol` by default.

Run gen_asc.py to produce `OUTPUT/SCH/<circuit_name>.asc`. Create `OUTPUT/SCH/` if it doesn't exist.

**When the user explicitly requests a plain netlist instead**, use `scripts/write_cir.py` and produce `OUTPUT/SCH/<circuit_name>.cir`, then lint with `scripts/lint_cir.py`.

### Step 5 — Share and launch

On **Windows**, attempt to auto-launch LTspice with the netlist loaded using `scripts/launch_ltspice.py OUTPUT/SCH/<circuit_name>.cir`. The script walks this detection order:

1. `%LOCALAPPDATA%\Programs\ADI\LTspice\LTspice.exe` (modern ADI builds, 2023+)
2. `C:\Program Files\ADI\LTspice\LTspice.exe`
3. `C:\Program Files\LTC\LTspiceXVII\XVIIx64.exe`
4. `C:\Program Files (x86)\LTC\LTspiceIV\scad3.exe`
5. Whatever is registered for `.cir` via `cmd /c start "" "<path>"`

If none are found, present the `.cir` path (`OUTPUT/SCH/<circuit_name>.cir`) to the user, link them to the LTspice download page, and give a one-line command they can paste to launch manually.

On **non-Windows**, skip the launch step, present the file, and mention that LTspice runs on Windows (natively) or macOS/Linux (via Wine or LTspice for Mac).

Finish with a **simulation notes** block: which analysis was chosen, why, what nodes were labeled for probing, what to look at in the waveform viewer, and how to tweak the directive.

## Conversational contract

These rules exist because they're where this skill fails in practice. Break them and the user will end up debugging a netlist that doesn't match their circuit.

- **Always describe before generating.** The readback is not a formality. It is how you catch vision errors cheaply.
- **Always flag assumptions in a dedicated block.** Everything inferred — a partially-obscured resistor value, a guessed transistor polarity, an implied ground — goes into the "Please confirm" section. Don't bury assumptions in SPICE comments and hope the user notices.
- **Never invent part numbers.** If an IC's markings are unreadable, ask. Substituting a "plausible" chip will produce a simulation of a different circuit.
- **Never silently correct topology.** If the image shows op-amp inputs wired backwards, electrolytic reversed, or feedback missing, surface it as a question. The user may have drawn it wrong, or you may have read it wrong — let them decide.
- **Comment the netlist liberally.** Every section labeled, every assumption restated in a `*` comment, every model source credited.
- **Prefer library references over embedded models.** Run `scripts/query_lib.py` for every semiconductor before writing a `.model` card. If the part is in lib.zip, reference it by name — do not duplicate it inline. Only move to internet search, library alternatives, or hand-crafted models when `query_lib.py` exits 1 (not found) and each subsequent tier is exhausted in order.

## Generating `.asc` schematic files

When the task is to produce an LTspice `.asc` schematic (rather than a plain `.cir`
netlist), apply the rules in `references/asc_generation_rules.md` in full. Key points:

### Symbol placement
Always derive `SX, SY` from where the pin must land — never hardcode. Pattern:
```python
SX = node_x - rot(local_pin_x, local_pin_y, rotation)[0]
SY = node_y - rot(local_pin_x, local_pin_y, rotation)[1]
```
Apply horizontal scale factor `H` only to x-coordinates. Never apply it to y-coords,
pin local offsets, or stub sizes.

### Stub direction — body-clearance rule
Every pin stub must exit *away from* the component body. The direction that goes
toward the body interior is forbidden even if it would reach the target node:

- Resistor R0: A stubs UP, B stubs DOWN.
- Capacitor R0: A stubs UP, B stubs DOWN.
- NPN R0: C stubs UP, B stubs LEFT, E stubs DOWN.
- **PMOS R0: D stubs UP, G stubs LEFT, S stubs DOWN — never UP for S.**
- PMOS S going up to a supply rail: stub S downward first, detour in x, then route up.

If body clearance and stub clearance conflict, body clearance wins. Place the pin
directly at the node (zero stub) rather than route through the body.

### Bus wires over net labels
Power and GND rails use physical horizontal bus wires with a single flag per rail.
Do not place individual flags on each component pin. Net labels are acceptable only
where a direct wire would cross another wire or cross an isolation barrier.

### No speculative `.options`
Do not add `.options gmin` or `.options abstol` by default. These can break simulations
that run correctly without them. Add only when a simulation actually fails and the
user explicitly requests convergence tuning.

### Label placement — wire-priority rule

**Wires always have higher priority than text.** Every label, designator, and value
must be placed so it does not overlap any wire segment.

`gen_asc.py` implements this automatically via the wire registry and `_safe_window()`:

1. Every `wire()` call registers the segment in `_wires[]`.
2. `sym()` looks up WINDOW overrides from `_WINDOWS` for the symbol stem + rotation.
3. `_safe_window(sx, sy, dx, dy)` shifts `dy` in ±`LABEL_CLEARANCE` (16 px) steps
   until `_wire_clearance(sx+dx, sy+dy) ≥ 16`. Falls back to the original offset
   if no clear position is found within 5 steps.
4. The adjusted `WINDOW <n> dx dy Left 2` line is emitted **before** `SYMATTR` in the
   SYMBOL block — LTspice requires this ordering.

**Informational net labels** use `INFO_OFFSET = 32 px` stubs so the flag text
(~16 px tall) clears the wire by at least one full grid unit.

Per-component default WINDOW offsets (screen-space, verified against wires):

| Symbol | Rotation | WINDOW 0 (InstName) | WINDOW 3 (Value) |
|---|---|---|---|
| `res` | R0 | (36, 24) | (36, 64) |
| `res` | R270 | (56, −52) | (56, 16) |
| `cap` | R0 | (36, −8) | (36, 56) |
| `diode` | R0 | (36, −8) | (36, 56) |
| `npn`, `pmos`, `voltage`, `PC817x` | — | (use .asy defaults) | (use .asy defaults) |

See `references/asc_generation_rules.md §9` for the full specification, including
body bounding boxes, the `_wire_clearance()` algorithm, and flag-stub sizing rationale.

See `references/asc_generation_rules.md` for the full ruleset, the per-component stub
direction table, and the validation checklist.

## Bundled assets

- `scripts/gen_asc.py` — **Primary schematic generator.** Produces a `.asc` file for LTspice from hardcoded component placement and routing logic. Encodes pin geometry, stub/bus rules, and SPICE directives. Extend this script when adding new circuits; follow `references/asc_generation_rules.md` for all placement and routing decisions.
- `scripts/query_lib.py` — **Run this first for every semiconductor before writing any model reference.** Searches the LTspice `lib.zip` for a part by name and reports: symbol path (for `.asc`), subcircuit name and call syntax, and the exact `.model` line to embed if absent. Exit 0 = found; exit 1 = not found, move to Tier 4+.
- `references/asc_generation_rules.md` — Full ruleset for `.asc` generation: stub direction per component/pin/rotation, body-clearance priority, symbol placement math, bus-wire preference, PMOS S-pin detour pattern, validation checklist, and session learnings with root causes.
- `references/ltspice_builtin_parts.md` — Summary of what's in the LTspice library, indexed by category. Reflects LTspice 26 `lib.zip` reality. Verify with `query_lib.py` rather than assuming a part name works.
- `references/spice_syntax_cheatsheet.md` — Device card syntax, engineering notation, valid analysis directives, common mistakes.
- `references/circuit_templates.md` — Canonical SPICE patterns for common topologies. Use as scaffolds, not blind copies.
- `scripts/write_cir.py` — Fallback `.cir` netlist writer (used only when user explicitly requests a plain netlist).
- `scripts/lint_cir.py` — Sanity-checks a `.cir` before handoff. Run after every `.cir` emitted.
- `scripts/launch_ltspice.py` — Windows auto-launcher. Walks the detection order and invokes LTspice with the `.asc` (or `.cir`) path as argument.

## Failure modes

| Problem | What to do |
|---|---|
| Image too blurry to read values reliably | Ask the user for a higher-resolution image or a textual component list. Don't guess. |
| LTspice not installed on a Windows machine | Link the user to https://www.analog.com/en/resources/design-tools-and-calculators/ltspice-simulator.html and provide the `.cir` file path. |
| Non-Windows OS | Skip auto-launch; deliver the `.cir` with a note on how to open it. |
| Simulation fails to converge on first run | First try: soften source edges (`Trise`/`Tfall`), reduce `maxstep`. If still failing, try `reltol=0.01` before touching `gmin`/`abstol`. Only add `gmin`/`abstol` as a last resort — they can break circuits with subcircuit-based models (optocouplers, regulators) that run correctly at defaults. Comment every option added and why. |
| Unrecognized IC | Follow the Tier 4 → 5 → 6 → 7 ladder: search the internet for a vendor SPICE model first; if not found, substitute a close lib.zip alternative; if no alternative exists, search the internet for an equivalent part model; only as a last resort hand-craft a `.subckt` stub from datasheet parameters with a clear `* CUSTOM MODEL:` comment. Never just drop a stub and leave the user to fill it in while other options remain. |
| User can't answer the readback questions | Do not emit SPICE on a coin flip. Offer to proceed with explicit assumptions only if the user says so in writing. |
| LTspice warns "floating node" on a custom subcircuit | You used `Vsense N_K K 0` + `F1` (CCCS) to sense LED current. Node `N_K` has no DC path. Replace with `Rsense N_K K 1m` + `G1 C E N_K K <Gm>` (VCCS, where Gm = CTR/Rsense). See cheatsheet gotcha #7. |
| High-impedance output node undefined at `.op` or transient start | Add a dummy load to ground (`RLOAD OUT GND 1Meg`) so the node has a DC path when the driving switch is off. Note the resistor in a comment so the user knows it is not on the physical schematic. |
| `query_lib.py` misses a known BJT/MOSFET in lib.zip | LTspice 26 encodes `standard.bjt` / `standard.mos` as UTF-16-LE, which latin-1 decoding silently mangles. The script uses null-byte detection to handle this. If a known-good part still fails, re-run with `python scripts/query_lib.py <part>` and check the raw output; the encoding heuristic may need updating for unusual builds. |

## Example session (abridged)

**User:** "Simulate `INPUT/SCH/amp_sketch.jpg`."

**Skill readback:**
> This looks like a single-supply non-inverting amplifier built around an LM358.
>
> | Ref | Type | Value / Part | Between |
> |---|---|---|---|
> | U1 | Op-amp | LM358 (half) | +in: N002, −in: N003, out: OUT, V+: VCC, V−: GND |
> | R1 | Resistor | 1 kΩ | N003 – GND |
> | R2 | Resistor | 10 kΩ | N003 – OUT |
> | C1 | Capacitor | 1 µF | IN – N002 |
> | R3 | Resistor | 100 kΩ | VCC – N002 |
> | R4 | Resistor | 100 kΩ | N002 – GND |
> | V1 | DC supply | 9 V | VCC – GND |
> | V2 | AC source | 100 mVpp, 1 kHz sine | IN – GND |
>
> Expected gain ≈ 1 + R2/R1 = 11. Midpoint bias via R3/R4.
>
> **Please confirm or correct:**
> - R1 — the photo shows what could be "1k" or "7k". I've assumed 1k. Which is it?
> - Is C1 polarized (electrolytic) or non-polar (ceramic)? I've assumed non-polar.

**User:** "R1 is 1k. C1 is ceramic."

**Skill:** emits `.cir` with `.ac dec 100 1 1Meg` + `.op` + `.tran 0 5m 0 1u`, lints it, saves to `OUTPUT/SCH/amp_sketch.cir`, and launches LTspice with that path. Ends with a simulation-notes block pointing the user at the `V(OUT)/V(IN)` Bode plot.
