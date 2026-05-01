# Report template — `<MODEL_NAME>_symbol_report.md`

The skill generates a Markdown audit report next to every package. Use this
template as the canonical structure. Fill in every section; if a section
doesn't apply, write "none" or "n/a" rather than omitting the section —
consistency makes the reports easy to skim across many parts.

---

```markdown
# Symbol generation report — <MODEL_NAME>

**Generated:** <YYYY-MM-DD HH:MM>
**Source file:** `INPUT/SYMBOL/<original_filename>` (preserved unchanged)
**Output folder:** `OUTPUT/SYMBOL/<MODEL_NAME>/`
**Status:** `READY` | `READY_WITH_WARNINGS` | `NEEDS_MANUAL_REVIEW` | `FAILED`

## 1. Input scan

- Files inspected: <list with paths>
- Selected source: `<file>`
- Detected dialect: `ltspice` | `pspice` | `hspice` | `unknown`
- Encryption flags: <none, or list>

## 2. Detected model

- Model name: `<NAME>`
- Model type: `.SUBCKT` | `.MODEL`
- Primitive (if .MODEL): `D` | `NPN` | `PNP` | `NMOS` | `PMOS` | …
- Inferred part type: `op-amp` | `diode` | `BJT NPN` | `MOSFET NMOS` | …
- Confidence: high | medium | low (with one-line reason)

## 3. Pin map

Order matches the `.SUBCKT` declaration. SpiceOrder = position in this
table.

| # | Pin name | Side | Function (inferred) | Confidence |
|---|---|---|---|---|
| 1 | <name> | left | non-inv input | high |
| 2 | <name> | left | inv input | high |
| 3 | <name> | top | V+ supply | high |
| 4 | <name> | bottom | V− supply | high |
| 5 | <name> | right | output | high |

## 4. Output files

| File | Purpose |
|---|---|
| `<MODEL_NAME>.asy` | LTspice symbol |
| `<MODEL_NAME>.lib` | Normalized model file |
| `<MODEL_NAME>_test.asc` | Minimal test schematic |
| `<MODEL_NAME>_usage_example.txt` | Plain-text usage notes |
| `<MODEL_NAME>_symbol_report.md` | This file |

## 5. LTspice attributes used

- `SymbolType`: CELL
- `Prefix`: `X` | `D` | `Q` | `M` | `J` | …
- `SpiceModel`: `<NAME>`
- `ModelFile`: `<MODEL_NAME>.lib`
- `Description`: <one-line description>

## 6. Compatibility notes

What was rewritten, what was kept, what is in question. One bullet per
issue.

- Stripped `PARAMS:` keyword on line 12 (cross-version compatibility).
- Converted `EOUT VALUE = {…}` to `BOUT V = …` on line 34 (LTspice
  prefers `B`-source form).
- Kept `LIMIT()` calls — LTspice supports them natively.

## 7. PSpice / dialect warnings

Constructs that may need manual review. List each line number and what to
look at.

- Line 47: `TABLE(…)` function — left as-is. LTspice equivalent is
  `pwl()`. Verify the simulation matches expectations on this output.

## 8. Dependencies

- `.INCLUDE`/`.LIB` references found: <list, with status — copied | missing>
- Missing dependencies: <list, or "none">

## 9. Validation checklist

- [x] Every `.SUBCKT` pin has a matching `PIN` in the .asy
- [x] SpiceOrder values are 1..N, unique, contiguous
- [x] SpiceOrder order matches declaration order
- [x] Symbol Prefix matches model type
- [x] SpiceModel attribute names a model that exists in the .lib
- [x] No hardcoded absolute paths in the .asy
- [x] Report contains a Status field
- [x] Usage example exists and names the .lib file

## 10. Usage instructions

1. Copy `<MODEL_NAME>.asy` and `<MODEL_NAME>.lib` into the same folder as
   your schematic, **or** into your LTspice user library folder
   (`Documents\LTspiceXVII\lib\sym\` and `…\sub\` respectively).
2. In LTspice, press F2 → "Top Directory" → navigate to the folder where
   you placed `<MODEL_NAME>.asy` → select it.
3. Place the symbol on your schematic.
4. If the symbol does not auto-load the model, add a directive to your
   schematic: `.lib <MODEL_NAME>.lib` (or `.include <MODEL_NAME>.lib`).
5. Wire pins per the pin map in section 3.
6. Run.

## 11. Manual actions required

- <list, or "none">

## 12. Final status

`READY` | `READY_WITH_WARNINGS` | `NEEDS_MANUAL_REVIEW` | `FAILED`

<one-line summary of why>
```
