---
name: ltspice-symbol-creation
description: >
  Use this skill whenever the user wants to turn a downloaded SPICE model
  (.lib, .sub, .cir, .ckt, .mod, .mdl, .sp, .spi, .spice, .net, .inc, .txt,
  .asy, or a .zip vendor package) into a ready-to-use LTspice symbol package.
  Reads model files from INPUT/SYMBOL/ and writes exactly two files to
  OUTPUT/SYMBOL/ — the .asy symbol and the normalized .lib model file.
  All warnings, compatibility notes, and manual steps are communicated in
  chat only; no report or auxiliary files are written. Trigger aggressively on phrases like "create an LTspice symbol",
  "make an .asy for this", "wrap this SPICE model", "I downloaded a model and
  need a symbol", "convert this PSpice model to LTspice", "generate a symbol
  from this .subckt", "build me a symbol package", or any mention of SPICE
  model files alongside symbol/.asy/LTspice. Handles .SUBCKT-based and
  .MODEL-based parts, detects PSpice vs LTspice dialect, flags encrypted or
  unsupported syntax, follows .INCLUDE/.LIB chains, and assigns SpiceOrder to
  match the .SUBCKT pin declaration exactly. Do NOT use for: simulating an
  existing schematic image (use ltspice-simulation), BOM auditing (use
  bom-qa), part substitution (use bom-alternatives), or PCB layout.
---

# ltspice-symbol-creation

Turn a downloaded SPICE model file into a complete, ready-to-test LTspice
symbol package. Not just an `.asy` — every artifact a user needs to drop the
part into a schematic and simulate it without manual editing.

## What this skill is for

The user has downloaded a SPICE model from a vendor (TI, ADI, Vishay,
Infineon, ON Semi, …) and wants to use it in LTspice. Doing this correctly
requires several engineering decisions that are tedious to do by hand:

- finding the actual model text inside whatever the vendor shipped
  (sometimes a `.zip`, sometimes a `.txt`, sometimes a `.lib` with multiple
  models inside);
- deciding whether it is a `.SUBCKT` (needs `X` prefix) or a primitive
  `.MODEL` (needs `D`/`Q`/`M`/`J`);
- detecting PSpice-only syntax that LTspice will refuse, and either
  rewriting it or warning honestly;
- assigning **SpiceOrder** for every pin so the order matches the `.SUBCKT`
  node declaration — the single most common bug in hand-made symbols;
- packaging everything (symbol, model, usage notes, optional test rig) so
  the user can copy it into LTspice and hit Run.

The skill produces an **electrically-correct first, visually-pretty second**
symbol. A plain rectangle with the right pin order beats a beautiful symbol
with one swapped pin.

## Repository I/O convention

This skill lives in the `electronics-qa` repository and uses fixed folders.
Respect them — do not scatter files elsewhere.

- **Input — SPICE model files:** `INPUT/SYMBOL/` (relative to the repo
  root). Pick up any of: `.lib`, `.sub`, `.cir`, `.ckt`, `.mod`, `.mdl`,
  `.sp`, `.spi`, `.spice`, `.net`, `.inc`, `.txt`, `.asy`, `.zip`. If a
  `.zip` is present, extract it to a temporary working directory and inspect
  the contents — never extract on top of `INPUT/SYMBOL/`. Ignore datasheets,
  PDFs, images, and `README` files unless they are needed for context.
- **Output — generated symbol packages:** `OUTPUT/SYMBOL/<MODEL_NAME>/`.
  One folder per generated symbol. The folder name must equal the SPICE
  model name (slug-safe — replace anything that isn't `[A-Za-z0-9_-]` with
  `_`).
- **Original input is never destructively edited.** If a model needs to be
  rewritten for LTspice compatibility, write the rewritten copy to the
  output folder as `<MODEL_NAME>.lib` and reference the original by
  filename in the report.

If `INPUT/SYMBOL/` or `OUTPUT/SYMBOL/` don't exist, create them.

## Per-model output package

The skill writes exactly two files. For a single model they go flat into
`OUTPUT/SYMBOL/`; for multiple models each pair goes into its own subfolder:

**Single model:**
```
OUTPUT/SYMBOL/
├── <MODEL_NAME>.asy    # LTspice symbol
└── <MODEL_NAME>.lib    # Normalized model
```

**Multiple models (--all):**
```
OUTPUT/SYMBOL/
├── <MODEL_NAME_1>/
│   ├── <MODEL_NAME_1>.asy
│   └── <MODEL_NAME_1>.lib
└── <MODEL_NAME_2>/
    ├── <MODEL_NAME_2>.asy
    └── <MODEL_NAME_2>.lib
```

No additional files are written. Warnings, compatibility notes, and manual
steps are communicated in the chat response only.

## The non-negotiable workflow

These steps in this order. The reason it is load-bearing: the skill's failure
modes are silent (wrong SpiceOrder, wrong prefix, hidden PSpice syntax) — the
generated symbol *will* place onto a schematic, but the simulation will fail
or, worse, return wrong numbers. A few seconds of disciplined parsing prevents
hours of "why does my LM358 oscillate at 50 GHz" debugging.

### Step 1 — Scan and classify

Run `scripts/process_input.py --scan` to inventory `INPUT/SYMBOL/`. The script
returns a JSON list of detected model files, with for each one:

- absolute path,
- detected dialect (`ltspice` | `pspice` | `hspice` | `unknown`),
- list of `.SUBCKT` definitions (name + pin list),
- list of `.MODEL` definitions (name + primitive type),
- list of `.INCLUDE` / `.LIB` references,
- encryption flags (`*#FUNC`, `ENCRYPTED`, `*#ENC`, etc.),
- suspect-syntax flags (PSpice-only constructs).

Read the JSON. If the user named a specific file or model, use that. If the
file contains exactly one obvious main model, proceed. Otherwise list the
candidates and ask the user which one(s) to generate. **Never silently pick
one when more than one plausible candidate exists.** See
`references/spice_parsing_rules.md` for what the parser looks for and how it
decides.

### Step 2 — Vision-read the SPICE model and produce a readback

Before generating any files, emit this structure:

1. **What was found** — file path, detected dialect, model name, model type
   (`.SUBCKT` or `.MODEL`), primitive type if applicable.
2. **Pin table** — for `.SUBCKT` models, the exact pin order from the
   declaration line, with any inferred polarity / function in a separate
   column. Number them 1..N in declaration order. **This is the SpiceOrder**
   and must not be reordered.
3. **Compatibility flags** — every PSpice / HSpice / suspect construct
   detected, with `references/pspice_compatibility.md` referenced for what
   needs manual review.
4. **Inferred part type** — diode / Zener / TVS / NPN / PNP / NMOS / PMOS /
   JFET / op-amp / comparator / regulator / driver / opto / generic IC.
   Confidence: high / medium / low. Where the inference came from (model
   keyword, pin names, comments, file name).
5. **Please confirm or correct** — every assumption: ambiguous part-type
   guess, polarity inference, pin-function inference, dialect conversion
   choices.

For unambiguous cases (e.g., a clean `.SUBCKT LM358 1 2 3 4 5` with five
clearly-named pins), the readback can be very brief and you can proceed
without explicit confirmation. For everything else (ambiguous part type,
PSpice constructs, polarity guesses on op-amp inputs), **stop and ask**. The
user knows their model; you are reading text. Cheap to ask, expensive to
generate the wrong symbol.

### Step 3 — Generate the package

Once the readback is confirmed (or the case is unambiguous enough to skip
confirmation), run:

```
python scripts/process_input.py --generate <input_path> --model <MODEL_NAME>
```

Under the hood this orchestrates:

1. `parse_spice.py` — parses the model file and emits a structured JSON
   description (model name, type, pin list with declaration order, dialect,
   warnings, includes).
2. `normalize_lib.py` — copies the model text into the output folder as
   `<MODEL_NAME>.lib`, applying safe rewrites (e.g., stripping `PARAMS:`
   keyword, auto-commenting bare header lines). **Original file is never
   touched.** Any unsafe transforms are surfaced as warnings in chat.
3. `gen_asy.py` — writes the `.asy` from the parsed pin list. Pin geometry
   uses the heuristics in `references/pin_layout_heuristics.md`. Symbol
   shape is picked from `references/symbol_shapes.md` based on detected
   part type. SpiceOrder is taken **directly** from the pin declaration
   order — never reordered, never alphabetized.
4. `validate.py` — runs the validation checklist below. Failure here means
   the package gets `FAILED` or `NEEDS_MANUAL_REVIEW` status.

No additional files (test schematics, usage notes, reports) are written to
disk. All warnings and manual actions are reported in chat.

### Step 4 — Validate

`validate.py` checks every generated package against:

- every pin in the `.SUBCKT` declaration has exactly one matching `PIN` in
  the `.asy`;
- every `PIN` has a `PINATTR PinName` and `PINATTR SpiceOrder`;
- the `SpiceOrder` values are `1..N` with no duplicates and no gaps;
- the `SpiceOrder` order matches the `.SUBCKT` declaration order exactly
  (this is the test that catches the most bugs);
- the symbol `Prefix` is correct for the model type (`X` for subcircuits;
  `D`/`Q`/`M`/`J` etc. for primitives);
- the `SpiceModel` (or `Value` / `Value2`) attribute names a model that
  actually exists in the `.lib` file;
- the `.asy` contains no absolute filesystem paths (`C:\`, `/home/`,
  `/Users/`, `Downloads`, `~/`);
- the `ModelFile` attribute is a bare filename with no path separators.

Any failure flips the status to at most `READY_WITH_WARNINGS` (recoverable)
or `NEEDS_MANUAL_REVIEW` (cannot vouch for the package). Communicate what
failed in the chat response.

### Step 5 — Present results in chat

No report file is written. In chat, summarize:

- model name, type (`.SUBCKT` / `.MODEL`), pin count, inferred part type
- status: `READY` / `READY_WITH_WARNINGS` / `NEEDS_MANUAL_REVIEW` / `FAILED`
- paths to the two output files (`.asy` and `.lib`)
- any warnings, compatibility rewrites, or manual actions required

Keep it concise. Provide a pin table (declaration order = SpiceOrder) so
the user can verify the mapping without opening the files.

## Status definitions

| Status | Meaning |
|---|---|
| `READY` | Symbol + model parse cleanly, validation passes, no PSpice syntax detected, model can almost certainly be simulated as-is. |
| `READY_WITH_WARNINGS` | Symbol generated, validation passes, but the model has minor issues a user might want to know about (e.g., one suspect construct that LTspice probably handles, a missing optional include). |
| `NEEDS_MANUAL_REVIEW` | Symbol generated because pin mapping was clear, but the model contains PSpice-only constructs, references missing dependencies, or otherwise can't be vouched for. |
| `FAILED` | No valid `.SUBCKT` or `.MODEL` definition found, or the model is encrypted, or pin count cannot be determined. No `.asy` is written. |

## Conversational contract

- **Always describe before generating, except for trivially-unambiguous
  cases.** The readback is how you catch parser bugs and PSpice surprises
  cheaply.
- **Always preserve the original input file.** Never rewrite files in
  `INPUT/SYMBOL/`. Normalized output lives in `OUTPUT/SYMBOL/<MODEL_NAME>/`.
- **Never silently pick a model when more than one is plausible.** Ask the
  user which to generate, or generate them all and say so.
- **SpiceOrder follows the `.SUBCKT` line, period.** Never re-sort pins
  alphabetically or "for prettiness". A wrong SpiceOrder produces a symbol
  that places fine but simulates as a different circuit.
- **Be honest about uncertainty.** If you guessed which pin is the
  non-inverting input on an op-amp, say so and put the assumption in the
  report. Don't pretend.
- **No hardcoded absolute paths.** `<MODEL_NAME>.lib` lives next to
  `<MODEL_NAME>.asy` — reference it by filename, not by a Windows path.
- **No fake symbols.** If no `.SUBCKT` or `.MODEL` is found, status is
  `FAILED` and no `.asy` is written. Don't draw a placeholder.

## Per-model-type generation rules

### `.SUBCKT`-based models

- Symbol attributes: `SymbolType CELL`, `Prefix X`, `SpiceModel
  <subckt_name>`, `ModelFile <MODEL_NAME>.lib`.
- One `PIN` per node in the `.SUBCKT` declaration. `PINATTR PinName <name>`
  uses the original casing from the declaration. `PINATTR SpiceOrder <n>`
  is the 1-indexed declaration position.
- Body shape from `references/symbol_shapes.md`. If part type is unknown,
  use a generic rectangle large enough for all pins on its perimeter.

### `.MODEL`-based primitive models

- Identify the primitive from the keyword on the `.MODEL` line: `D`,
  `NPN`/`PNP`, `NMOS`/`PMOS`, `NJF`/`PJF`, etc.
- Map to the right symbol prefix: `D`, `Q`, `M`, `J`, …
- For widely-used types (`D`, `NPN`, `PNP`, `NMOS`, `PMOS`, `NJF`, `PJF`),
  the report should also tell the user that the cleanest path is **using
  LTspice's built-in primitive symbol** and just adding a `.model` line —
  not creating a new symbol. Generate the custom symbol anyway (so the
  user has an option), but note the alternative clearly.

See `references/symbol_shapes.md` for shape definitions and pin counts per
primitive.

## Bundled assets

- `scripts/process_input.py` — **Entry point.** Orchestrates the whole
  pipeline. `--scan` reports what's in `INPUT/SYMBOL/` as JSON. `--generate
  <path> --model <name>` runs the full per-model pipeline and writes flat
  to `OUTPUT/SYMBOL/`. `--all` runs every detected unambiguous model and
  writes each to its own subfolder.
- `scripts/parse_spice.py` — SPICE file parser. Reads a model file and
  emits a structured JSON description (model name, type, pins in
  declaration order, dialect, warnings, includes, encryption flags). Pure
  text parsing, no SPICE simulator dependency.
- `scripts/gen_asy.py` — Writes the `.asy` symbol from a parsed model JSON.
  Encodes pin geometry, shape selection, and SpiceOrder assignment.
- `scripts/normalize_lib.py` — Writes a normalized copy of the model file
  into the output folder. Applies safe rewrites (strip `PARAMS:`,
  auto-comment bare header lines, convert `VALUE={}` to B-source); lists
  every change applied in its JSON output.
- `scripts/validate.py` — Runs the full validation checklist (Step 4).
  Returns JSON.
- `references/asy_format_spec.md` — LTspice `.asy` file format reference:
  `Version`, `SymbolType`, `LINE`, `RECTANGLE`, `CIRCLE`, `PIN`, `PINATTR`,
  `WINDOW`, `SYMATTR`. Read this before hand-editing any `.asy`.
- `references/spice_parsing_rules.md` — How to recognize `.SUBCKT` vs
  `.MODEL`, dialect detection (LTspice vs PSpice vs HSpice), include-chain
  following, encryption detection.
- `references/pin_layout_heuristics.md` — Pin-name aliases (V+ / VCC / VDD;
  IN+ / +IN / NONINV; etc.), polarity inference, geometric layout (power
  top, GND bottom, inputs left, outputs right).
- `references/pspice_compatibility.md` — Catalog of PSpice constructs and
  what to do with each: `PARAMS:`, `VALUE={}`, `TABLE()`, `IF()`,
  `LIMIT()`, `ABM`, `.FUNC`, vendor macros. For each: safe to keep, safe
  to rewrite, requires manual review, or refuse.
- `references/symbol_shapes.md` — Drawing primitives per part type:
  op-amp triangle, diode arrow+bar, MOSFET body, BJT body, generic
  rectangle. Coordinates are in LTspice's native 16-px schematic grid.

## Failure modes

| Problem | What to do |
|---|---|
| `INPUT/SYMBOL/` is empty | Tell the user the folder is empty, list the supported file types, do not invent a model. |
| `.zip` archive | Extract to a temp dir, inspect contents, process any `.lib`/`.sub`/`.txt` found inside. Copy non-extraneous text files into the output folder if they look like supporting models. Skip PDFs and images. |
| File contains no `.SUBCKT` or `.MODEL` | Status `FAILED`. Explain in chat: "No model definition detected." Check whether the file is actually a netlist (`.cir` with instance lines but no top-level `.SUBCKT`) — those need a wrapper; say so in chat. |
| File contains multiple `.SUBCKT` definitions | List them in chat. If one obviously matches the file name, propose it as the main and ask. Otherwise generate a symbol per definition, each in its own subfolder. |
| Model is encrypted (`*#FUNC`, `ENCRYPTED`, `*#ENC` markers, or content is base64/binary garbage) | Status `FAILED`. Explain in chat: "Model appears encrypted; vendor support required." Do not try to decode. |
| PSpice-only construct detected (`PARAMS:`, `VALUE={}`, etc.) | Apply the rewrite rules in `references/pspice_compatibility.md`. If a rewrite is safe, apply it and note it in chat. If not, leave the construct alone, status `NEEDS_MANUAL_REVIEW`, explain in chat exactly which line needs attention. |
| `.INCLUDE` references a file that doesn't exist in `INPUT/SYMBOL/` | Note the missing dependency in chat. Status `NEEDS_MANUAL_REVIEW`. Do not invent the missing file. |
| `.INCLUDE` references a file that does exist | Copy that file into the output folder alongside the main `.lib`, and add a `.include` line to the normalized model. |
| Pin count clearly inconsistent (declaration says 5, body uses 6 named nodes) | Status `FAILED`. Explain in chat. Common cause: parameter passed in `.SUBCKT NAME 1 2 3 PARAMS: x=1` was misread as a pin. |
| `.asy` file is supplied alongside the model | Read it, extract its pin list, cross-check against the `.SUBCKT` declaration. If they agree, copy the supplied `.asy` into the output folder and say so in chat. If they disagree, regenerate the symbol and explain in chat. |
| User passes a single MPN with no file | Out of scope — this skill does not search the internet for models. Tell the user to download the model first. |

## Example session (abridged)

**User:** "I dropped LM358.lib in INPUT/SYMBOL/ — make me a symbol."

**Skill — readback:**
> Found `INPUT/SYMBOL/LM358.lib`. One `.SUBCKT` named `LM358`, dialect
> looks like PSpice (`PARAMS:` keyword on line 12, `VALUE={...}` on line
> 34). Pin order from the declaration:
>
> | # | Pin name | Inferred function |
> |---|---|---|
> | 1 | `+IN` | non-inv input |
> | 2 | `-IN` | inv input |
> | 3 | `V+` | positive supply |
> | 4 | `V-` | negative supply / GND |
> | 5 | `OUT` | output |
>
> Inferred part type: **op-amp** (high confidence — pin names match the
> classic op-amp pattern). I'll use the triangle symbol.
>
> Two PSpice constructs to flag:
> - `PARAMS:` on line 12 — safe to strip in LTspice (rewriting).
> - `VALUE={V(N1,N2)*GAIN}` on line 34 — safe in LTspice as `V=...`. I'll
>   convert.
>
> Generating now.

**Skill — after generation:**
> Wrote `OUTPUT/SYMBOL/`:
> - `LM358.asy` — op-amp triangle, 5 pins, SpiceOrder 1..5 in declaration order.
> - `LM358.lib` — normalized (PARAMS: stripped, VALUE={} → B-source).
>
> **Pin map:**
> | # | Pin | Function |
> |---|-----|----------|
> | 1 | `+IN` | non-inv input |
> | 2 | `-IN` | inv input |
> | 3 | `V+` | positive supply |
> | 4 | `V-` | negative supply |
> | 5 | `OUT` | output |
>
> **Status: READY_WITH_WARNINGS** — PSpice constructs rewritten; spot-check
> the simulation matches expected behavior.
>
> **Usage:** copy both files next to your schematic, add `.include LM358.lib`
> as a SPICE directive, press F2 to place the symbol.
