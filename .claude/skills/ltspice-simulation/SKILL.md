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
- **Output — generated netlists:** `OUTPUT/SCH/`. Write every `.cir` here. Name the file after the source image's stem (e.g. `INPUT/SCH/preamp_v2.png` → `OUTPUT/SCH/preamp_v2.cir`). If the user gave the circuit a different name, use that — but keep it slug-safe (ASCII, no spaces, only `_` or `-` as separators).
- **Sidecar artifacts** (readback.md, simulation_notes.md) are allowed next to the `.cir` in `OUTPUT/SCH/` only if the user asks for them. By default, emit the readback inline in chat and keep `OUTPUT/SCH/` to just the `.cir` files. The goal is for the user to open that folder and see only deliverables.

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
| **4 — Not found** | `query_lib.py` exits 1 (no match) | Only now embed a custom `.model` or `.subckt` inline in the `.cir`. Comment the source of the parameters. |

> **Why this order matters:** LTspice 26 no longer ships `standard.bjt` / `standard.mos` as loadable files — only `lib.zip`. A model name that "worked in LTspice XVII" will silently fail in LTspice 26 unless either the library file is present or the model is embedded. Tier 1–3 ensures the simulation uses the vendor-validated model from lib.zip; Tier 4 is the fallback for parts Analog Devices has not included.

#### 4b — Write the netlist

Use `scripts/write_cir.py` (see Bundled assets below). If writing by hand:

- First line: title comment starting with `*`, naming the circuit and the generation date.
- Node `0` is ground. All labeled rails get a `V` source tied to `0`.
- Device letters: `R`, `C`, `L`, `D`, `Q` (BJT), `M` (MOSFET), `J` (JFET), `V`, `I`, `X` (subcircuit), `E/G/H/F` (controlled sources).
- Values in engineering notation LTspice understands: `10k`, `4.7u`, `100n`, `1Meg`, `2.2G`. Never `uF`, never `µ`, never unicode. LTspice will barf.
- For unknown ICs not in lib.zip: emit a `.subckt <name> …` stub and comment clearly that the user must drop in the vendor's SPICE model.
- End with `.end`.

Save to `OUTPUT/SCH/<circuit_name>.cir`, where `<circuit_name>` is the source image's filename stem unless the user specified otherwise. Keep the name slug-safe (ASCII, no spaces, only `_` or `-` as separators). Create `OUTPUT/SCH/` if it doesn't exist.

Then **lint the file** with `scripts/lint_cir.py`. If the linter complains (missing `.end`, unicode in values, dangling nets, undefined `.model` references), fix it before handing off.

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
- **Prefer library references over embedded models.** Run `scripts/query_lib.py` for every semiconductor before writing a `.model` card. If the part is in lib.zip, reference it by name — do not duplicate it inline. Only embed a `.model` or `.subckt` if `query_lib.py` exits 1 (not found).

## Bundled assets

- `scripts/query_lib.py` — **Run this first for every semiconductor before writing any `.model` card.** Searches the LTspice `lib.zip` for a part by name and reports: symbol path (for `.asc`), subcircuit name and call syntax (for `.cir`), and the exact `.model` line to embed if the part is absent. Exit 0 = found in library; exit 1 = not found, embed required.
- `references/ltspice_builtin_parts.md` — Summary of what's in the LTspice library, indexed by category. Reflects LTspice 26 `lib.zip` reality. The old `standard.bjt` / `standard.mos` are gone — verify with `query_lib.py` rather than assuming a part name works.
- `references/spice_syntax_cheatsheet.md` — Device card syntax, engineering notation, valid analysis directives, common mistakes. Skim this when writing a netlist by hand.
- `references/circuit_templates.md` — Canonical SPICE patterns for common topologies (op-amp inverting/non-inverting, RC/RLC filters, BJT CE amplifier, 555 astable, buck converter, diode bridge). Use as scaffolds when the vision pass clearly identifies one of these topologies — not blind copies, but starting points.
- `scripts/write_cir.py` — Helper that takes a structured Python dict describing components, nets, sources, and the analysis directive, and writes a linter-clean `.cir` file. Use this in preference to formatting strings by hand; it enforces the conventions above.
- `scripts/lint_cir.py` — Sanity-checks a `.cir` before handoff. Verifies every node appears on ≥ 2 components, no dangling pins, no unicode in values, every `.model`/`.subckt` referenced is defined, file ends with `.end`. Run this after every netlist you emit.
- `scripts/launch_ltspice.py` — Windows auto-launcher. Walks the detection order above and invokes LTspice with the netlist path as argument.

## Failure modes

| Problem | What to do |
|---|---|
| Image too blurry to read values reliably | Ask the user for a higher-resolution image or a textual component list. Don't guess. |
| LTspice not installed on a Windows machine | Link the user to https://www.analog.com/en/resources/design-tools-and-calculators/ltspice-simulator.html and provide the `.cir` file path. |
| Non-Windows OS | Skip auto-launch; deliver the `.cir` with a note on how to open it. |
| Simulation fails to converge on first run | Add `.options gmin=1e-10 abstol=1e-9`, soften source edges with `Trise`/`Tfall`, reduce `maxstep`. Comment every tweak. |
| Unrecognized IC | Emit a `.subckt` stub with pin names, comment clearly that the user must supply a vendor model. Proceed with the rest of the netlist. |
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
