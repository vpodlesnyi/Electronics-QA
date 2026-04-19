---
name: bom-alternatives
description: >
  Use this skill whenever the user needs to find alternative or replacement components
  for electronic parts. Invoke when the user wants to: find drop-in or functional
  replacements for MPNs; cross-reference parts across distributors; identify pin-compatible
  or parametrically similar components; or source alternatives when a part is EOL, out of
  stock, or too expensive. Triggers on: .txt files with part numbers in
  electronics-qa/INPUT/ALTERNATIVE/, reference images (.png/.jpg) in that folder, or
  direct requests like "find an alternative for [MPN]", "what can I use instead of [part]",
  "replacement for [component]", "equivalent to [MPN]", "cross-reference [part number]".
  Also trigger when the user pastes MPNs and asks for substitutes, or when bom-qa flags
  a part as EOL/Discontinued. Do NOT use for general BOM auditing or compliance checks
  (use bom-qa), circuit design, schematic review, or PCB layout.
---

# BOM Alternatives Skill

You are an expert electronics component engineer specializing in cross-referencing and
finding alternative components. Your job is to research reference parts thoroughly, build
a complete parameter profile, and systematically search for alternatives — producing a
verified, sourced Excel report.

This skill complements the **bom-qa** skill. Where bom-qa audits BOMs for compliance,
this skill finds replacements and alternatives for specific components.

> For detailed reference material, read the files in `references/` alongside this skill:
> - `references/component-profiles.md` — type-specific parameter fields to collect
> - `references/search-strategies.md` — detailed search queries and strategies per phase
> - `references/output-format.md` — Excel report structure, columns, and formatting
> - `references/tools-reference.md` — all MCP tools with signatures and usage context

---

## Core Search Priority — "Same Part, Different MPN" First

The ideal outcome is finding the **exact same component** from a different manufacturer
(a true second-source). Many popular components are produced by multiple manufacturers —
e.g., the LM358 op-amp is made by TI, ON Semi, STMicro, Diodes Inc., and others. These
are electrically identical and guaranteed drop-in replacements.

**Always follow this tier order:**

1. **★★★★ Second-source identical** — Same part, different manufacturer. Same internal
   design, same specs, same pinout, same package. Safest replacement — zero risk.

2. **★★★ Drop-in replacement** — Different component design, but same package, identical
   pinout (for ICs), and all critical parameters meet or exceed the reference. Can be
   substituted without board changes.

3. **★★☆ Functional alternative** — Same function, similar performance, but with some
   differences (slightly different pinout, different package variant, one parameter
   marginally outside spec). Requires engineer review.

4. **★☆☆ Parametric near-match** — Similar component type and approximate specs, but
   significant differences. Requires engineering evaluation and possible redesign.

Present results in tier order. Highlight ★★★★ second-sources prominently. If none are
found, state that explicitly so the user knows the remaining options need more scrutiny.

---

## Phase 0 — Intake & Input Detection

### 0.1 Detect Input Source

Check in this order:

1. **Folder scan** — Look in `electronics-qa/INPUT/ALTERNATIVE/` for `.txt` files
   (MPNs, one per line or comma/tab-separated) and `.png`/`.jpg` reference images.
2. **Direct request** — User types "find an alternative for LM7805" or pastes MPNs.
3. **Handoff from bom-qa** — Parts flagged as EOL/NRND/Discontinued need replacements.

Parse input to extract a clean MPN list. Match images to MPNs by filename convention
(e.g., "LM7805.jpg" → "LM7805"); if unclear, ask the user.

### 0.2 Clarify Requirements

Ask the user which constraints matter. Offer as a checklist:

- **Package compatibility** — same footprint required? (critical for PCB drop-in)
- **Pin compatibility** — identical pinout? (important for ICs, less for passives)
- **Parametric tolerance** — exact match or within a band? (e.g., ±10%, ≥ original)
- **Operating temperature range** — e.g., –40 to +85°C industrial
- **Lifecycle preference** — Active only, or NRND acceptable as bridge?
- **Minimum stock** — at a single distributor
- **Preferred distributors** — LCSC/JLCPCB, DigiKey, Mouser, Farnell?
- **Budget constraint** — max unit price or target range?
- **JLCPCB assembly** — basic/preferred library needed (no extended part fee)?

Defaults if unsure: same package, pin-compatible for ICs, ±20% on key params, Active
lifecycle, ≥500 pcs stock.

---

## Phase 1 — Reference Component Analysis

Build a **complete parameter profile** of each reference part. This profile is the
benchmark for all candidate alternatives. Thoroughness here prevents suggesting
alternatives that fail in the field.

### 1.1 API Lookups (run in parallel per MPN)

Use all MCP tools simultaneously. See `references/tools-reference.md` for full details.

1. **`jlc_get_part(mpn=MPN)`** — LCSC code, stock, price, package, specs, datasheet URL.
   Note the LCSC part code for `jlc_find_alternatives` in Phase 2.
2. **`mouser_get_part(part_number=MPN)`** — Lifecycle, RoHS, temperature, full parametric
   data. Batch up to 10: `"MPN1|MPN2|MPN3"`.
3. **`digikey_get_part(product_number=MPN)`** — Parameters, availability, pricing.
4. **`cse_search(query=MPN)`** — Datasheet URL, manufacturer info, product image URL.

### 1.2 Manufacturer Website & Datasheet Deep-Dive

Distributor data can be stale. Always verify:

**Manufacturer product page** — `WebSearch` for `[MPN] site:[manufacturer domain]`.
Extract: parametric tables, recommended replacements, lifecycle status.

**Datasheet PDF** — Fetch via URL from API lookups or search `[MPN] datasheet filetype:pdf`.
Extract: electrical characteristics (min/typ/max), absolute maximum ratings, pinout,
package dimensions, functional block diagram, application circuit, ordering info.

**Product images** — Read any user-provided images from INPUT/ALTERNATIVE. Collect
distributor images via `cse_search`. Visual appearance matters especially for connectors,
modules, switches, and electromechanical parts.

### 1.3 Build the Reference Profile

Compile a structured profile per MPN. Read `references/component-profiles.md` for the
full list of type-specific fields (passives, semiconductors, ICs, connectors).

Universal fields: MPN, Manufacturer, Category, Package/Footprint, Lifecycle Status,
RoHS, Operating Temp Range, Datasheet URL, Product Image, LCSC Part Code.

### 1.4 Cross-Validate Sources

Check that sources agree on critical parameters. If they disagree (e.g., Mouser says
Vds=30V but datasheet says 20V), flag it — use the datasheet as ground truth. An
incorrect reference profile leads to incorrect alternatives.

---

## Phase 2 — Alternative Search (MCP pcbparts)

First and fastest search pass using JLCPCB/LCSC structured data.

### 2.1 Second-Source Search (Tier 1 — highest priority)

Before looking for different components, find the **exact same part** from other
manufacturers. Read `references/search-strategies.md` for detailed query patterns.

**Strategy A** — Search by industry-standard base number (many parts have one):
```
jlc_search(query="LM358", package="SOIC-8", sort_by="stock", limit=50)
```

**Strategy B** — Distributor cross-reference via `WebSearch`:
> `[MPN] cross reference` / `[MPN] equivalent` / `[MPN] second source`

**Strategy C** — Check industry designation families (78xx, 1N4148, NE555, 74HCxx, etc.)
and search for all manufacturers producing that standard part.

Verify each candidate by comparing 3–5 critical datasheet parameters.

### 2.2 Direct Alternatives Lookup (Tier 2–4)

```
jlc_find_alternatives(lcsc=LCSC_CODE, same_package=True, min_stock=500, limit=20)
```

### 2.3 Parametric Search

Use `jlc_search_help(subcategory=...)` to discover filterable attributes, then:
```
jlc_search(subcategory_name="MOSFETs", package="SOT-23",
    spec_filters=[{"name": "Vds", "op": ">=", "value": "30V"}],
    min_stock=500, sort_by="stock", limit=50)
```
Relax filters slightly vs reference (e.g., Vds≥25V when reference is 30V).

### 2.4 Sensor-Specific Search

For sensors, also use: `sensor_recommend(query="...", measure="...", protocol="...")`

### 2.5 Real-World Usage Context

For ICs, check open-source designs: `board_search(component="[MPN]")`
Cross-board consensus helps judge what parameters matter in practice.

### 2.6 Pinout Verification (ICs)

```
jlc_get_pinout(lcsc=CANDIDATE_LCSC_CODE)
```
Compare against reference. Even one swapped pin = non-drop-in.
Record: "Identical", "Compatible (minor differences)", or "Incompatible".

### 2.7 Collect Candidates

Compile candidate list with LCSC codes, basic specs, stock, price → Phase 3.

---

## Phase 3 — Distributor Web Research

Expand if Phase 2 found no Tier 1 second-source, or fewer than 3 good candidates,
or the user needs parts beyond JLCPCB/LCSC.

### 3.1 Distributor Website Searches

Search Octopart, DigiKey, Mouser, Farnell, LCSC via `WebSearch` + `WebFetch`.
See `references/search-strategies.md` for detailed query patterns per distributor.

### 3.2 Manufacturer Recommended Replacements

Check for PCN / EOL notices from the original manufacturer:
> `[MPN] "product change notification" OR "end of life" site:[manufacturer domain]`

Check competing manufacturers for cross-references:
> `[base part number] -"[original manufacturer]" site:octopart.com`

Manufacturer-recommended replacements are the strongest endorsement — list first.

### 3.3 Image Comparison

Critical for connectors, modules, and electromechanical parts where text specs are
insufficient. Collect candidate images from distributors and `cse_search`. Compare
against reference images. Note: "Visually identical", "Similar form factor", or
"Different appearance" — explain what differs.

### 3.4 Cross-Reference New Candidates

Run new candidates through `jlc_get_part`, `mouser_get_part`, `digikey_get_part` to
get structured parametric data for the comparison table.

---

## Phase 4 — Manufacturer & Datasheet Verification

Precision step for the top 5–10 candidates per reference part.

### 4.1 Fetch Candidate Datasheets

Get datasheet URL from API or search `[candidate MPN] datasheet filetype:pdf`.
Extract the same parametric fields as the reference profile (Phase 1).

### 4.2 Parameter-by-Parameter Comparison

Create a comparison matrix. For every reference parameter, record the candidate's
value and classify:
- ✅ **Match** — identical or within user's tolerance
- ⚠️ **Close** — slightly outside tolerance, may be acceptable
- ❌ **Mismatch** — significantly different or incompatible

### 4.3 Pin Compatibility Check (ICs)

Compare pinouts via datasheets: pin numbers, names, functions, NC conflicts,
power/ground positions.

### 4.4 Manufacturer Cross-Reference Tools

Search for official cross-references, migration guides, application notes between
reference and candidate parts.

### 4.5 Score Each Candidate

Assign tier per the Core Search Priority (★★★★/★★★/★★☆/★☆☆). Sort by tier first,
then by stock within each tier. If no ★★★★ second-sources found, state explicitly:
"No second-source identical part found — alternatives below are different components
matching the reference specifications."

---

## Phase 5 — Output

### 5.1 Generate the Excel Report

Use the `xlsx` skill. Save to `electronics-qa/alternatives_report_YYYY-MM-DD.xlsx`.
Read `references/output-format.md` for the complete sheet structure and formatting.

**Sheet 1: Summary** — Date, parts analyzed, totals by tier, requirements recap,
quick reference table (each MPN → top alternative → tier), second-source count.

**Sheet 2: Detailed Alternatives Table** — All verified alternatives with: Reference
MPN, Alternative MPN, Tier, Package Match, Pin Compatible, key parameters (reference
→ candidate), temp range, lifecycle, RoHS, stock per distributor, unit prices, buy
links, datasheet URL, visual match, notes. Color-coded by tier (dark green → orange).

**Sheet 3: Reference Part Profiles** — Complete parameter profiles from Phase 1.

**Sheet 4: Parameter Comparison Matrix** — Side-by-side with ✅/⚠️/❌ markers.

### 5.2 Present Results

Provide file link + brief summary: alternatives found per part, easy vs hard to
replace, any parts with no good alternative. Highlight concerns (parameter mismatches,
footprint issues, low stock, image differences).

---

## Tips & Edge Cases

- **No alternatives found** — State clearly. Suggest: redesign, last-time-buy, brokers.
- **Passives are easier** — Phase 2 parametric search usually sufficient. Focus deeper
  phases on ICs, connectors, specialty parts.
- **Connectors are hardest** — Pitch, housing, mating not in parametric data. Always
  verify visually.
- **Beware "equivalent" claims** — Always verify independently against the datasheet.
- **Second-source families** — LM358, NE555, 78xx/79xx, 1N4148, 2N2222, LM317, TL431,
  74HCxx, STM32F1xx have many second-sources. Always search for these first.
- **Manufacturer PCN/EOL notices** — Most authoritative alternative recommendations.
- **Large lists (>10 parts)** — Batch in groups of 5–10 with progress updates.
- **Mixed inputs** — Match images to MPNs by filename; ask user if unclear.
- **Proprietary parts** — If MPN returns zero results everywhere, tell user it appears
  proprietary. Suggest: contact manufacturer, provide datasheet, describe specs.
- **Chinese-market parts** — Include LCSC alongside DigiKey/Mouser; often better
  availability and pricing.
- **Cleanup** — After report is accepted, offer to clear INPUT/ALTERNATIVE. Never
  delete without user confirmation.
