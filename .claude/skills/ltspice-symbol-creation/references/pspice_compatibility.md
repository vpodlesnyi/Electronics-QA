# PSpice → LTspice compatibility catalog

For each non-LTspice construct that appears in vendor models, this lists
what to do during normalization. Reasoning included so the skill can judge
edge cases.

## Status legend

- **Safe to keep** — LTspice supports the construct directly. No rewrite
  needed.
- **Safe to rewrite** — Mechanical transformation that preserves meaning.
  Apply automatically; record in the report.
- **Risky** — Rewrite is possible but may change behavior in edge cases.
  Apply if confident; flag in the report.
- **Manual review** — Don't rewrite. Surface the lines and ask the user.
- **Refuse** — Don't try. Mark `NEEDS_MANUAL_REVIEW` or `FAILED`.

---

## `PARAMS:` keyword on `.SUBCKT` line

```
.SUBCKT MYAMP IN OUT V+ V- PARAMS: GAIN=100 BW=1MEG
```

**Status: Safe to rewrite.** LTspice accepts this exact syntax as of
LTspice 17 — it's silently tolerated. But many older LTspice builds choke,
and stripping the keyword is harmless because LTspice's own format is just
to list `param=value` directly:

```
.SUBCKT MYAMP IN OUT V+ V- GAIN=100 BW=1MEG
```

**Rewrite:** delete the literal token `PARAMS:` (case-insensitive). Record:
"Stripped PARAMS: keyword on line N for cross-version compatibility."

## `VALUE = { expr }` on a behavioral source

```
EOUT OUT 0 VALUE = { V(IN1)*V(IN2) }
```

**Status: Safe to rewrite.** LTspice's native form is `B`-source with `V=`:

```
BOUT OUT 0 V = V(IN1)*V(IN2)
```

For `E`/`G` (linear-controlled) sources written in PSpice's `VALUE` form,
the cleanest rewrite is to switch the device letter to `B` (LTspice's
behavioral source) and use `V=` or `I=`. The `B` source supports the same
expression syntax.

**Rewrite:** match `E<n> <out> <ref> VALUE = { <expr> }` →
`B<n> <out> <ref> V = <expr>`. Same for `G<n>` → `B<n> ... I = <expr>`.
Record each rewrite.

## `TABLE( in, x1, y1, x2, y2, ... )` function

```
EOUT OUT 0 TABLE { V(IN) } = (-1, -10) (0, 0) (1, 10)
```

**Status: Risky → Manual review.** LTspice's equivalent uses a piecewise
linear via the `B`-source `pwl()` function:

```
BOUT OUT 0 V = pwl(V(IN), -1, -10, 0, 0, 1, 10)
```

The mechanical transform is doable but it's easy to misparse the comma
patterns. Default behavior: **leave the original alone, flag for manual
review**. Offer the user the rewrite with a confidence note.

## `IF( cond, a, b )` function

```
V1 OUT 0 VALUE = { IF( V(IN) > 0, 5, 0 ) }
```

**Status: Safe to rewrite.** LTspice prefers ternary:

```
B1 OUT 0 V = (V(IN) > 0) ? 5 : 0
```

Both syntaxes work in LTspice; the ternary is cleaner. Apply only if also
rewriting `VALUE` form to `B`-source.

## `LIMIT( x, lo, hi )` function

**Status: Safe to keep.** LTspice has `limit()` natively. No rewrite.

## `ABS()`, `MIN()`, `MAX()`, `SQRT()`, `EXP()`, `LN()`, `LOG()`, `PWR()`

**Status: Safe to keep.** All native in LTspice. PSpice's `PWR(x,y)` is
LTspice's `pow(x,y)`; both names work in LTspice.

## `.PARAM` directive

```
.PARAM GAIN = 100
.PARAM ALPHA = { 1k * 2 }
```

**Status: Safe to keep.** LTspice supports `.PARAM` identically. The braces
around expressions are optional in LTspice but required in PSpice — safe
either way.

## `.FUNC` directive

```
.FUNC SQR(x) { x*x }
```

**Status: Safe to keep.** Both engines support `.FUNC`. Body must be a
single expression in braces or with `=` form; LTspice tolerates both.

## `.STIMULUS` directive (PSpice-only)

```
.STIMULUS MYWAVE PWL TIME_SCALE_FACTOR=1 (0,0) (1m,5) (2m,0)
```

**Status: Manual review.** PSpice-specific. The cleanest path is to embed
the stimulus directly in the test schematic as a `PWL` source. Don't
rewrite inside the model file — surface the lines and explain.

## `.STEP` directive

**Status: Safe to keep.** Both engines support it. Syntax is identical
enough.

## `.NOISE`, `.AC`, `.TRAN`, `.DC`, `.OP`

**Status: Safe to keep.** Universal SPICE.

## `.OPTIONS`

```
.OPTIONS ABSTOL=1n RELTOL=0.001
```

**Status: Risky.** Many `.OPTIONS` settings are universal but a few
PSpice-specific ones (`STEPGMIN`, `RSHUNT`, `LIMPTS`) are not. Strategy:
keep the line in the normalized library but verify against the LTspice
options reference; flag any PSpice-only options for review.

## ABM (analog behavioral modeling) blocks

```
GFOO 1 2 VALUE = { sgn(V(3,4)) * sqrt(abs(V(3,4))) }
```

**Status: Safe to rewrite** if it's a simple `VALUE` expression on `E`/`G`
(see above). For block-form ABM with multiple inputs and `LAPLACE` /
`FREQ` / `CHEBYSHEV` modifiers, **manual review** — those have no clean
LTspice equivalent.

## Encrypted models

```
*#protected
*$PROTECTED MODEL_BODY_FOLLOWS
... base64 body ...
```

**Status: Refuse.** Set status `FAILED`. Suggest the user contact the
vendor for an LTspice-compatible model.

## Vendor-specific macros

E.g., TI's `OPMACRO`, `CMACRO`; ADI's `IDEAL_INTEGRATOR`. These are vendor
helpers that often expand to vanilla SPICE inside their own internal
macroset.

**Status: Manual review.** Don't try to expand. Surface the line and let
the user decide whether to source the macro library or hand-rewrite.

## Digital primitives

```
U1 BUFFER DPWR DGND IN OUT IO_STD
```

**Status: Refuse.** PSpice digital simulation doesn't translate to LTspice
(LTspice has only behavioral digital via `A`-devices, very different
syntax). Set status `NEEDS_MANUAL_REVIEW`. Suggest the user redo the
digital portion as `A`-devices or replace with simple analog
approximations.

## `STIMLIB` / external stimulus references

**Status: Refuse.** External stimulus libraries are a PSpice-OrCAD thing.
Surface and ask.

---

## Quick decision flow for a new construct

1. Is it a known PSpice keyword? → look up here.
2. Does it appear inside a `.SUBCKT` body that LTspice will parse? Try the
   rewrite if confident.
3. Is it inside a comment? Leave alone.
4. Is it isolated (one occurrence in a 500-line file) and safe to leave
   verbatim? Mark as warning, leave as-is, status
   `READY_WITH_WARNINGS`.
5. Is it pervasive (every output is a PSpice ABM block)? Status
   `NEEDS_MANUAL_REVIEW` — the model is fundamentally PSpice and
   half-rewriting it is worse than not rewriting at all.
