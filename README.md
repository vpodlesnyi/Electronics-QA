# Electronics QA

**Electronics QA** is an open-source AI-powered quality assurance tool for electronics design.

It is built to help engineers catch issues early during design review and act as a first-pass QA assistant for electronics projects. The tool uses Claude Code — an AI assistant you run from your terminal — to analyze your files and produce detailed reports.

The goal is not to replace engineering judgment, but to help engineers identify issues faster and more systematically.

---

## Current status

🚧 Early development

| Module | Status |
|---|---|
| BOM QA | ✅ Available |
| LTspice Simulation | ✅ Available |
| LTspice Symbol Creation | ✅ Available |
| CLI (`eqa`) | 🔧 In development |
| Schematic review | 📋 Planned |

---

## How it works

Electronics QA is built as a set of **skills** — separate modules, each focused on one type of QA check. You run them from your terminal using Claude Code by typing a plain-language command. Claude reads your files, performs the analysis, and saves a report.

You do not need to write any code to use it.

---

## Requirements

- [Node.js](https://nodejs.org/) (v18 or later)
- [Python](https://www.python.org/downloads/) (v3.8 or later) — used to read Excel BOM files and generate Excel reports
- A [Claude subscription](https://claude.ai) (Pro or above — used to log in to Claude Code)
- A terminal (macOS Terminal, Windows PowerShell, Linux shell)

> **Note:** Claude Code can be authenticated with your Claude subscription — no API key needed. Avoid setting up an API key unless you have a specific reason; the subscription login is simpler and recommended for most users.

---

## Setup (first time only)

### macOS / Linux

**Step 1 — Install Claude Code:**
```bash
npm install -g @anthropic-ai/claude-code
```

**Step 2 — Log in with your Claude subscription:**
```bash
claude login
```
This opens a browser window. Sign in with your claude.ai account and authorize Claude Code.

**Step 3 — Clone this repo and start Claude Code:**
```bash
git clone <your-repo-url>
cd <your-repo>
claude
```

**Step 4 — Verify the model:**

Inside Claude Code, run:
```
/model
```
It should show `claude-sonnet-*`. Sonnet is the recommended model for this project — it handles multi-step lookups and conflict detection reliably.

---

### Windows (PowerShell)

**Step 1 — Install [Node.js](https://nodejs.org/) and [Git](https://git-scm.com/download/win)** using the standard Windows installers.

**Step 2 — Allow PowerShell to run scripts** (required once, safe to do):
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
> By default, Windows blocks PowerShell scripts. This one-time command allows Node.js tools like `npm` to run normally. Type `Y` when prompted.

**Step 3 — Install Claude Code:**
```powershell
npm install -g @anthropic-ai/claude-code
```

**Step 4 — Log in with your Claude subscription:**
```powershell
claude login
```
This opens a browser window. Sign in with your claude.ai account and authorize Claude Code.

**Step 5 — Clone this repo and start Claude Code:**
```powershell
git clone <your-repo-url>
cd <your-repo>
claude
```

**Step 6 — Verify the model:**

Inside Claude Code, run:
```
/model
```
It should show `claude-sonnet-*`. Sonnet is the recommended model for this project — it handles multi-step lookups and conflict detection reliably.

That's it. The skills and MCP plugin are loaded automatically — no extra configuration needed.

---

## Module: BOM QA

Validates a Bill of Materials against common production readiness criteria.

### How it works

When you trigger the skill, Claude runs a structured five-phase process:

1. **Intake** — Reads your BOM file (Excel or CSV) and extracts every MPN, manufacturer, and reference designator. Asks you to confirm the compliance criteria to apply.
2. **Permission setup** — Pre-approves all required tool permissions in one go at the start of the session, so there are no repeated approval prompts during research.
3. **Component research** — For each unique MPN, queries the pcbparts MCP plugin (LCSC/JLCPCB, Mouser, DigiKey) in parallel, then cross-checks against the manufacturer's product page and datasheet PDF. Every data field (lifecycle, temperature range, RoHS) is collected from multiple independent sources.
4. **Conflict detection** — Compares values across sources. If any two sources disagree on a field, the row is flagged 🔴 and the discrepancy is logged with the exact value each source reported.
5. **Report generation** — Evaluates every part against your criteria and saves a timestamped report (Markdown or Excel) to `OUTPUT/BOM/`. The report includes a summary, a full component table with per-source data, a dedicated conflict section, and an action list for all failed or unverified parts.

### What it checks

- **Lifecycle status** — flags obsolete, NRND (Not Recommended for New Designs), EOL, or discontinued parts
- **RoHS compliance** — verifies compliance using distributor data and manufacturer datasheets
- **Operating temperature range** — checks that parts meet your required range (e.g. –40 to +85°C for industrial)
- **Stock availability** — checks current stock at DigiKey, Mouser, and LCSC
- **Data conflicts** — flags 🔴 when different sources (distributor vs. datasheet vs. manufacturer website) disagree on the same field

### How to run

**Step 1 — Place your BOM file in the input folder:**
```
INPUT/BOM/your-bom.xlsx
```
Supported formats: `.xlsx`, `.xls`, `.csv`, `.tsv`

Your BOM must have at minimum an **MPN** (Manufacturer Part Number) column. A **Reference Designator** column (e.g. C1, R3, U7) is recommended for traceability.

**Step 2 — Start Claude Code (if not already running):**
```bash
claude
```

**Step 3 — Trigger the BOM QA skill** by typing any of these:
```
run bom qa
```
```
check the bom
```
```
audit my parts list
```

**Step 4 — Answer the criteria questions.** Claude will ask:
- Should all parts be Active lifecycle only?
- Is RoHS compliance required?
- What is the required operating temperature range?
- What is the minimum stock quantity needed?

If unsure, just press Enter to use the industrial defaults (Active, RoHS, –40 to +85°C, ≥500 pcs).

**Step 5 — Get your report.** When analysis is complete, the report is saved to:
```
OUTPUT/BOM/your-bom_report_YYYY-MM-DD.md
```

Each run creates a new timestamped file — previous reports are never overwritten.

---

## Module: LTspice Simulation

Converts a schematic image into a runnable LTspice simulation — reading components and connectivity from the picture, choosing appropriate models from the LTspice library, generating a `.asc` schematic file, and launching LTspice automatically on Windows.

### How it works

When you trigger the skill, Claude runs a structured five-step process:

1. **Vision read** — Opens the schematic image and catalogues every component (reference designator, value, part number), every net, and every source. Transistor pinouts, op-amp polarities, diode orientations, and electrolytic polarity markings are all resolved at this stage.
2. **Readback and confirmation** — Before writing any SPICE, Claude presents a complete component table and net list derived from the image, flags every assumption it made, and asks you to confirm or correct. This is the most important step: vision models can misread values or connections, and a two-minute confirmation prevents a half-hour of debugging a phantom circuit.
3. **Library lookup** — For every semiconductor and IC, Claude searches the LTspice `lib.zip` for a matching model. It follows a strict priority ladder: exact library subcircuit → exact library model → library symbol with embedded subcircuit → internet vendor model → library substitute → internet substitute → hand-crafted model as a last resort. The goal is always to use a validated model rather than a hand-written approximation.
4. **Schematic generation** — Claude writes a `gen_asc_<circuit>.py` script and runs it to produce a properly-routed `.asc` schematic file. Every pin gets a 48 px stub, power rails use physical bus wires with a single flag per rail, labels are placed to avoid overlapping wires, and SPICE directives (`.tran`, `.ac`, `.op`, etc.) are chosen to match the circuit topology.
5. **Launch** — On Windows, LTspice is launched automatically with the generated schematic loaded and ready to run.

### What analysis it selects

Claude infers the best analysis directive from the circuit topology:

| Topology | Directive chosen |
|---|---|
| Pure DC bias, no reactive elements | `.op` |
| Amplifier with AC source, gain/bandwidth question | `.ac dec 100 1 10Meg` + `.op` |
| Oscillator, switching converter, pulse/PWM circuit | `.tran` — stop time scaled to ~10 periods |
| Passive filter | `.ac` with limits derived from component values |
| Digital input/output circuit with pulse source | `.tran` — stop time shows several switch cycles |

### Requirements

- [LTspice](https://www.analog.com/en/resources/design-tools-and-calculators/ltspice-simulator.html) installed on Windows (the modern ADI build, 2023 or later, is recommended)
- Python 3.8 or later (used by the schematic generation scripts)

LTspice is free. The skill auto-detects the standard installation paths; no manual configuration is needed.

### How to run

**Step 1 — Place your schematic image in the input folder:**
```
INPUT/SCH/your-schematic.png
```
Supported formats: `.png`, `.jpg`, `.jpeg`, `.bmp`

The image can be a screenshot from KiCad, Altium, or EasyEDA; a photo of a hand-drawn sketch; or an image pulled from a datasheet. Higher resolution gives better results — if component values are hard to read, use a zoomed-in export.

**Step 2 — Start Claude Code (if not already running):**
```bash
claude
```

**Step 3 — Trigger the skill** by typing any of these:
```
simulate this circuit
```
```
run ltspice simulation
```
```
make a spice netlist from this schematic
```

Or simply drop an image in the chat and describe what you want to learn from the simulation.

**Step 4 — Confirm the readback.** Claude will describe everything it sees in the image — components, values, net connections, sources — and list every assumption it made. Read through the list and correct anything that is wrong before saying "yes" or "confirmed". Common things to check:

- Resistor values (especially when reading from color bands or small text)
- Transistor pinout (which leg is collector vs. emitter in a BJT)
- Diode orientation (anode vs. cathode)
- Capacitor polarity for electrolytics
- Which op-amp input is `+` vs. `−`

**Step 5 — Get your schematic and simulation.** When the readback is confirmed, Claude generates:

```
OUTPUT/SCH/your-schematic.asc   ← LTspice schematic, opens directly in LTspice
scripts/gen_asc_<circuit>.py    ← reproducible script that regenerates the .asc
```

On Windows, LTspice opens automatically with the schematic loaded. Press **F9** (or click Run) to start the simulation. Probe the labeled nodes — Claude will tell you which nodes to watch and what the waveforms should look like.

### Model substitution policy

Claude always searches the LTspice library before writing any model from scratch. When an exact match is not found, it substitutes the closest available model and leaves a clearly labeled comment in the schematic:

```
; BC548 -> BC547B  (Tier 2 standard.bjt, same family, 45V/100mA)
; HCPL-817-300E -> PC817D  (Tier 1 lib/sub/PC817.sub, CTR grade via Igain=3.4m)
```

Substitutions are always flagged — you will never get a silently wrong model.

### Dummy load note

Some circuit topologies (high-side switches, open-collector outputs) leave a node floating when the driving device is off. Claude adds a 1 MΩ dummy load resistor to these nodes so LTspice has a DC path and does not produce a convergence error. These resistors are clearly commented as not being on the physical schematic.

---

## Module: LTspice Symbol Creation

Converts a downloaded vendor SPICE model into a ready-to-use LTspice symbol package — a correctly-ordered `.asy` symbol file and a normalized `.lib` model file — without any manual editing.

### How it works

When you trigger the skill, Claude runs a structured five-step process:

1. **Scan and classify** — Inventories `INPUT/SYMBOL/` and detects every SPICE model file present, identifying the dialect (LTspice, PSpice, HSpice), model names, pin lists, and any compatibility issues. If multiple candidates are found, Claude lists them and asks which to generate.
2. **Readback and confirmation** — Before generating any files, Claude presents the detected model name, model type (`.SUBCKT` or `.MODEL`), the exact pin order from the declaration, the inferred part type (op-amp, MOSFET, diode, etc.), and every compatibility flag. For ambiguous cases it asks for confirmation before proceeding.
3. **Model normalization** — Copies the model into the output folder as `<MODEL_NAME>.lib`, applying safe LTspice-compatibility rewrites (e.g., stripping the PSpice `PARAMS:` keyword, converting `VALUE={}` to B-source syntax). The original input file is never modified.
4. **Symbol generation** — Writes the `.asy` symbol using the detected pin list. Pin order follows the `.SUBCKT` declaration exactly — `SpiceOrder` is never re-sorted alphabetically or for aesthetics, since a wrong pin order produces a symbol that places onto a schematic but simulates as a different circuit.
5. **Validation** — Checks that every pin in the `.SUBCKT` declaration has a matching `PIN` entry with a correct `SpiceOrder`, that the `Prefix` is right for the model type (`X` for subcircuits, `D`/`Q`/`M`/`J` for primitives), and that no absolute filesystem paths are embedded in the symbol. Any failure is reported in chat with the exact issue.

### What model types it supports

- `.SUBCKT`-based models (op-amps, regulators, drivers, optocouplers, ICs of any kind)
- `.MODEL`-based primitives (diodes, BJTs, MOSFETs, JFETs)
- PSpice and HSpice dialect detection with safe automatic rewrites where possible
- `.zip` vendor packages — extracted to a temporary directory, contents inspected automatically
- `.INCLUDE` / `.LIB` chains — followed and resolved; missing dependencies are flagged in chat

### What it cannot do

- Decode encrypted models (`*#FUNC`, `ENCRYPTED`, `*#ENC` — no `.asy` is written; vendor support is required)
- Search the internet for a model given only an MPN — download the model file first and place it in `INPUT/SYMBOL/`
- Simulate the circuit (use the LTspice Simulation module for that)

### Output status labels

| Status | Meaning |
|---|---|
| `READY` | Validation passes, no PSpice syntax, safe to simulate as-is. |
| `READY_WITH_WARNINGS` | Validation passes but minor issues were detected (e.g., one suspect construct LTspice likely handles, a rewritten PSpice expression). |
| `NEEDS_MANUAL_REVIEW` | Symbol generated but the model contains PSpice-only constructs, references a missing dependency, or has another issue that can't be vouched for. |
| `FAILED` | No valid `.SUBCKT` or `.MODEL` found, or the model is encrypted. No `.asy` is written. |

### How to run

**Step 1 — Place your SPICE model file in the input folder:**
```
INPUT/SYMBOL/YourModel.lib
```
Supported formats: `.lib`, `.sub`, `.cir`, `.ckt`, `.mod`, `.mdl`, `.sp`, `.spi`, `.spice`, `.net`, `.inc`, `.txt`, `.asy`, or a `.zip` vendor package.

**Step 2 — Start Claude Code (if not already running):**
```bash
claude
```

**Step 3 — Trigger the skill** by typing any of these:
```
create an LTspice symbol
```
```
make an .asy for this model
```
```
wrap this SPICE model
```
```
I downloaded a model and need a symbol
```

**Step 4 — Confirm the readback.** Claude will show you the detected model name, pin table (in declaration order), inferred part type, and any PSpice compatibility flags. Check that the pin order matches your datasheet before confirming — this is what prevents a silently-wrong simulation.

**Step 5 — Get your symbol package.** When generation is complete, two files are written:

```
OUTPUT/SYMBOL/YourModel.asy    ← LTspice symbol, ready to place
OUTPUT/SYMBOL/YourModel.lib    ← Normalized model file
```

Copy both files into a folder next to your schematic (or into the LTspice `lib/` directory). Add `.include YourModel.lib` as a SPICE directive, then press **F2** in LTspice to place the symbol.

---

## Folder structure

```
.
├── .claude/
│   └── skills/
│       ├── bom-qa/
│       │   └── SKILL.md            ← BOM QA skill definition
│       ├── ltspice-simulation/
│       │   ├── SKILL.md            ← LTspice simulation skill definition
│       │   └── references/         ← SPICE syntax, ASC rules, circuit templates
│       └── ltspice-symbol-creation/
│           ├── SKILL.md            ← LTspice symbol creation skill definition
│           ├── scripts/            ← Python pipeline (parse, normalize, gen_asy, validate)
│           └── references/         ← .asy format spec, pin layout heuristics, PSpice compat
├── INPUT/
│   ├── BOM/                        ← place your BOM files here before running
│   ├── SCH/                        ← place your schematic images here before simulating
│   └── SYMBOL/                     ← place your SPICE model files here before symbol creation
├── OUTPUT/
│   ├── BOM/                        ← BOM reports saved here automatically (git-ignored)
│   ├── SCH/                        ← generated .asc schematics saved here (git-ignored)
│   └── SYMBOL/                     ← generated .asy symbol packages saved here (git-ignored)
├── scripts/
│   └── gen_asc_<circuit>.py        ← reproducible script for each generated schematic
├── .mcp.json                       ← MCP plugin configuration (loaded automatically by Claude Code)
├── .gitignore
└── README.md
```

As new modules are added, they will follow the same pattern: a new skill in `.claude/skills/`, a new subfolder in `INPUT/`, and a new subfolder in `OUTPUT/`.

## MCP plugin

The repo includes `.mcp.json` which configures the **pcbparts** MCP server ([pcbparts.dev](https://pcbparts.dev)). Claude Code loads it automatically when you open the project — no manual setup needed.

The pcbparts plugin gives Claude access to:
- **JLC / LCSC** — part lookup, stock check, pinout, search
- **Mouser** — part lookup with full attributes
- **DigiKey** — part lookup with full attributes
- **PCB design rules** and KiCad footprint data

This is what powers the live component lookups in the BOM QA module.

### Setting up on a new machine

**Server registration — no manual step needed.**
The repo includes `.mcp.json` which defines the pcbparts server at the project level, and `.claude/settings.local.json` includes `"enableAllProjectMcpServers": true`. Together these cause Claude Code to load pcbparts automatically when you open the project — no `claude mcp add` command is required.

**Tool permissions — handled automatically on first run.**
Each pcbparts tool call requires an entry in `permissions.allow` to run without an approval prompt. These are stored in your user-level `~/.claude/settings.json`, which is not part of this repo. On the first run of `/bom-qa` on a new machine, Phase 0 of the skill detects missing entries and adds them automatically. If you prefer to set this up manually before running the skill, create `~/.claude/settings.json` with:

```json
{
  "permissions": {
    "allow": [
      "mcp__pcbparts__jlc_search",
      "mcp__pcbparts__jlc_search_help",
      "mcp__pcbparts__jlc_stock_check",
      "mcp__pcbparts__jlc_get_part",
      "mcp__pcbparts__jlc_find_alternatives",
      "mcp__pcbparts__jlc_get_pinout",
      "mcp__pcbparts__mouser_get_part",
      "mcp__pcbparts__digikey_get_part",
      "mcp__pcbparts__cse_search",
      "mcp__pcbparts__cse_get_kicad",
      "mcp__pcbparts__sensor_recommend",
      "mcp__pcbparts__board_search",
      "mcp__pcbparts__board_get",
      "mcp__pcbparts__get_design_rules"
    ]
  }
}
```

If the file already exists, add only the missing entries — do not replace the whole file.

**Summary of what each config layer does:**

| File | Location | What it does |
|---|---|---|
| `.mcp.json` | repo root (tracked) | Defines the pcbparts HTTP server endpoint |
| `.claude/settings.local.json` | repo (tracked) | Auto-enables the server; pre-approves `jlc_search_help` |
| `~/.claude/settings.json` | user home (not in repo) | Pre-approves the remaining 13 pcbparts tools |
| `~/.claude.json` | user home (not in repo) | Written by `claude mcp add`; **not needed here** |

On a fresh machine, the only file that must exist before running the skill without any approval prompts is `~/.claude/settings.json` with the entries above. The skill will create it for you if it is missing.

---

## Notes

- Reports in `OUTPUT/BOM/` are git-ignored — only the folder structure is tracked in git
- The BOM QA skill does **not** suggest replacement parts — that is out of scope and will be a separate module
- Data lookups are live (DigiKey, Mouser, LCSC APIs + manufacturer websites) — stock numbers reflect the moment the check was run
