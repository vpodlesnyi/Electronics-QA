# SPICE parsing rules

How to read a SPICE model file the way `parse_spice.py` does, and the
reasoning behind each decision. Read this when extending the parser or when
manually inspecting a tricky model.

## SPICE statement basics

- Statements begin in column 1.
- A line starting with `*` is a **comment** — ignore in parsing but **keep
  in normalization** (comments often credit the model author and date).
- A line starting with `+` is a **continuation** of the previous statement.
  Logically join `+`-continuations with the previous line before parsing.
- Whitespace is whitespace; multiple spaces collapse.
- Case-insensitive on keywords (`.SUBCKT` == `.subckt`); case-preserving on
  identifiers (subckt names, pin names, model names) — but at evaluation
  time LTspice is case-insensitive on Windows and case-sensitive on Linux.
  Preserve original casing throughout.

## Recognizing definitions

### `.SUBCKT` definitions

```
.SUBCKT <name> <pin1> <pin2> ... <pinN> [PARAMS: param=val ...]
... body ...
.ENDS [<name>]
```

- The first token after `.SUBCKT` is the model name.
- Every subsequent token is a pin **until** one of:
  - `PARAMS:` (case-insensitive) — everything after is parameters, not
    pins;
  - a token containing `=` — anonymous parameter declaration; everything
    from that token on is parameters;
  - end of the (continuation-joined) line.
- `.ENDS` ends the subcircuit. The trailing name is optional — match it if
  present.

The skill must be careful with PSpice files that use inline parameters
without `PARAMS:`:

```
.SUBCKT MYREG VIN VOUT GND R=10k C=1u
```

Here `R=10k` and `C=1u` are NOT pins — but a naive split would treat them
as such. The `=` test catches this.

### `.MODEL` definitions

```
.MODEL <name> <type>(<param>=<value> <param>=<value> ...)
.MODEL D1N4148 D(IS=2.52n N=1.752 ...)
.MODEL Q2N2222 NPN(IS=...)
```

- First token after `.MODEL` is the model name.
- Second token is the **type** — one of:
  - `D` (diode)
  - `NPN`, `PNP` (BJT)
  - `NMOS`, `PMOS` (MOSFET)
  - `NJF`, `PJF` (JFET)
  - `R`, `C`, `L` (passive primitive)
  - `SW`, `CSW` (switches)
  - `URC`, `LTRA`, `K` (transmission lines, mutual inductance)

The type determines the SPICE prefix the symbol must use:

| `.MODEL` type | Symbol prefix |
|---|---|
| `D` | `D` |
| `NPN`, `PNP` | `Q` |
| `NMOS`, `PMOS` | `M` |
| `NJF`, `PJF` | `J` |
| `R` | `R` |
| `C` | `C` |
| `L` | `L` |
| `SW`, `CSW` | `S`, `W` |

## Dialect detection

A best-effort classifier. Score each indicator; if any single PSpice or
HSpice indicator is found, mark the file as that dialect (PSpice and HSpice
have higher specificity than LTspice-isms).

### LTspice indicators (weak — these all also appear in vanilla SPICE)

- File comment mentions LTspice (`* LTspice`).
- Uses `.func` (lowercase) — both LTspice and PSpice support this.
- Uses `.lib`, `.include` — universal.

### PSpice indicators (strong)

- `PARAMS:` keyword on a `.SUBCKT` line.
- `VALUE = { ... }` on a behavioral source — PSpice syntax. LTspice writes
  this as `V=...` or `I=...` directly.
- `TABLE( ... )` function call (rare in LTspice; common in PSpice ABM).
- `LIMIT( a, lo, hi )` function call.
- `IF( cond, a, b )` function call (LTspice prefers ternary `cond ? a : b`).
- File header mentions PSpice / OrCAD / Cadence.
- `.STIMULUS` directive (PSpice-only).
- `*$` or `*#` lines — PSpice-encoded metadata.

### HSpice indicators

- `.OPTION` (with that exact spelling).
- `.MEAS` with HSpice-specific syntax.
- `'expr'` (single-quoted expressions) — HSpice-only.
- File header mentions HSpice / Synopsys.

## Encryption detection

Any of these in the file → mark as **encrypted** and refuse:

- A line literally containing `ENCRYPTED` (case-insensitive) outside a
  comment.
- A `*#FUNC` or `*#ENC` block.
- More than 50% of the file consists of lines longer than 200 characters
  with no whitespace (likely base64-encoded model body).
- The byte stream contains non-ASCII characters with no UTF-8 validity (the
  raw cipher bytes).
- Vendor-specific markers: `*#protected`, `*$ENCRYPT`, `; @encrypted`.

## Include chains

`.INCLUDE <path>` and `.LIB <path> [<libname>]` reference external files.
The skill follows them **one level deep**:

- If `<path>` is relative, look for it in `INPUT/SYMBOL/` first, then in
  the directory of the file being parsed.
- If found, parse the included file and merge its `.SUBCKT` / `.MODEL`
  definitions into the result. Mark each definition with its source file.
- If not found, record the missing reference in the warnings list. Do not
  fail the entire parse — the main file may still be useful.

`.LIB` with a library section name (`*.LIB foo.lib SECTION_A`) is a hint
that only the named section should be included. Pass the section name into
the include-record but don't try to parse out only that section
(LTspice does not honor section names anyway as of LTspice 26).

## Multiple-model files

A single file may have multiple `.SUBCKT` and/or multiple `.MODEL`
definitions. Common patterns:

- **Vendor library** with one `.SUBCKT` per part (e.g., `op_amps.lib`
  containing `.SUBCKT LM358`, `.SUBCKT LM741`, `.SUBCKT TL072`). Generate
  one symbol per definition.
- **Helper subcircuits** — top-level definition plus several internal
  helpers. The main definition is usually the one whose name matches the
  filename (case-insensitive); helpers have prefixes like `_HELPER_` or
  short names like `IDEAL_DIODE`.
- **`.MODEL` accompanying a `.SUBCKT`** — the `.MODEL` defines a primitive
  that the `.SUBCKT` body uses. Generate symbols only for the `.SUBCKT`s;
  copy the `.MODEL`s into the normalized library file as supporting
  definitions.

When in doubt, list all candidates and ask the user.

## SPICE numeric format

For reference when normalizing:

| Suffix | Meaning |
|---|---|
| `T` | 1e12 |
| `G` | 1e9 |
| `MEG` | 1e6 (NOT `M`) |
| `K` | 1e3 |
| `M` | 1e-3 |
| `U`, `µ` | 1e-6 |
| `N` | 1e-9 |
| `P` | 1e-12 |
| `F` | 1e-15 |

Conversion gotcha: PSpice and LTspice both treat `M` as milli, but some
HSpice files use `M` as mega. If converting an HSpice file, look for unit
context (`1M` Ohms is mega, `1M` seconds is milli) and warn rather than
guess.

Unicode µ (U+00B5 or U+03BC) is fine in LTspice but cleaner to normalize
to `u` for cross-platform safety.
