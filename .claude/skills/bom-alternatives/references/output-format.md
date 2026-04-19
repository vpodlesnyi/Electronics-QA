# Excel Report Output Format

Complete specification for the alternatives report generated in Phase 5.
Use the `xlsx` skill to create this file.

**Filename:** `electronics-qa/alternatives_report_YYYY-MM-DD.xlsx`

---

## Sheet 1: Summary

### Header Section
- **Report title:** "Component Alternatives Report"
- **Date of analysis:** YYYY-MM-DD
- **Number of reference parts analyzed:** N
- **Total alternatives found:** N (breakdown by tier)
- **User requirements recap:** Package, temperature, stock, budget constraints applied

### Tier Breakdown Table

| Tier | Count | Description |
|---|---|---|
| ★★★★ Second-source identical | N | Same part, different manufacturer |
| ★★★ Drop-in replacement | N | Different part, fully compatible |
| ★★☆ Functional alternative | N | Close match, minor differences |
| ★☆☆ Parametric near-match | N | Similar specs, notable differences |
| No alternative found | N | Parts with no suitable replacement |

### Quick Reference Table

| # | Reference MPN | Reference Mfr | Top Alternative | Alt Mfr | Tier | Stock |
|---|---|---|---|---|---|---|
| 1 | LM358DR | TI | LM358DT | STMicro | ★★★★ | 45,000 |
| 2 | AO3400 | Alpha & Omega | SI2302CDS | Vishay | ★★★ | 12,000 |
| ... | | | | | | |

---

## Sheet 2: Detailed Alternatives Table

This is the main output sheet. Group alternatives under their reference part with
a merged header row in bold showing the reference MPN and manufacturer.

### Column Definitions

| Column | Width | Description |
|---|---|---|
| A: Reference MPN | 20 | The original part being replaced |
| B: Reference Manufacturer | 18 | |
| C: Alternative MPN | 20 | The candidate replacement |
| D: Alternative Manufacturer | 18 | |
| E: Compatibility Tier | 12 | ★★★★ / ★★★ / ★★☆ / ★☆☆ |
| F: Package / Footprint | 14 | Candidate's package |
| G: Package Match | 10 | ✅ or ❌ |
| H: Pin Compatible | 10 | ✅ / ⚠️ / ❌ / N/A |
| I–P: Key Parameters | 14 each | Reference value → Candidate value |
| Q: Operating Temp Range | 16 | e.g., –40°C to +85°C |
| R: Lifecycle Status | 12 | Active / NRND / EOL |
| S: RoHS | 8 | Yes / No |
| T: Stock — LCSC | 12 | pcs (include LCSC code in parentheses) |
| U: Stock — DigiKey | 12 | pcs |
| V: Stock — Mouser | 12 | pcs |
| W: Unit Price (qty 1) | 12 | Lowest across distributors, in USD |
| X: Unit Price (qty 100) | 12 | Lowest across distributors, in USD |
| Y: Buy Link — LCSC | 30 | Clickable hyperlink |
| Z: Buy Link — DigiKey | 30 | Clickable hyperlink |
| AA: Buy Link — Mouser | 30 | Clickable hyperlink |
| AB: Datasheet URL | 30 | Clickable hyperlink |
| AC: Visual Match | 14 | Visually identical / Similar / Different |
| AD: Notes | 40 | Differences, caveats, special considerations |

### Key Parameter Columns (I–P)

These columns are dynamic — their headers and content depend on the component type.
Use the most important parameters from the reference profile:

**Passives:** Value, Tolerance, Voltage Rating, Power Rating, Dielectric/Type
**MOSFETs:** Vds, Vgs(th), Id, Rds(on), Qg
**Diodes:** Vr, If, Vf, trr
**Op-amps:** Supply Voltage, GBW, Slew Rate, Iq
**Regulators:** Vin Range, Vout, Iout Max, Dropout, Iq
**MCUs:** Core, Flash, RAM, Clock, GPIOs
**Connectors:** Pitch, Positions, Current Rating, Mating Part

Format each cell as: `Reference → Candidate` (e.g., "30V → 40V")

### Formatting Rules

| Tier | Row Background Color | RGB |
|---|---|---|
| ★★★★ Second-source | Dark green | (198, 239, 206) |
| ★★★ Drop-in | Light green | (226, 239, 218) |
| ★★☆ Functional alt | Light yellow | (255, 242, 204) |
| ★☆☆ Near-match | Light orange | (252, 228, 196) |

Additional formatting:
- **Bold** the top-recommended alternative row for each reference part
- **Merged header row** above each group: reference MPN + manufacturer in bold,
  spanning all columns, with light gray background
- **Freeze** row 1 (column headers) and column A (reference MPN)
- **Hyperlinks**: columns Y, Z, AA, AB should be clickable
- **Auto-adjust** column widths for readability (or use the widths above)
- **Borders**: light gray grid lines for all data cells

---

## Sheet 3: Reference Part Profiles

One section per reference part, showing the complete parameter profile from Phase 1.
This lets the engineer verify what benchmark was used for the comparison.

### Layout

For each reference part:

**Row 1 (merged, bold):** MPN — Manufacturer — Category

**Profile table:**
| Parameter | Value | Source |
|---|---|---|
| Package | SOIC-8 | Mouser, DigiKey, Datasheet |
| Lifecycle | Active | Manufacturer website |
| Vds | 30V | Datasheet (Table 3) |
| ... | | |

Include the source for each value so the engineer can trace back to the original data.

Separate each reference part with a blank row.

---

## Sheet 4: Parameter Comparison Matrix

Side-by-side comparison for each reference part vs. its top 3 alternatives.
Designed for quick visual scanning.

### Layout

| Parameter | Reference: LM358DR | Alt 1: LM358DT | Alt 2: LM2904DR | Alt 3: MC1458D |
|---|---|---|---|---|
| Manufacturer | TI | STMicro | TI | ON Semi |
| Package | SOIC-8 | SOIC-8 ✅ | SOIC-8 ✅ | SOIC-8 ✅ |
| Supply Voltage | 3–32V | 3–32V ✅ | 3–26V ⚠️ | 3–36V ✅ |
| GBW | 1.1MHz | 1.1MHz ✅ | 1.0MHz ✅ | 1.0MHz ✅ |
| Slew Rate | 0.6V/µs | 0.6V/µs ✅ | 0.6V/µs ✅ | 0.8V/µs ✅ |
| Iq | 0.7mA | 0.7mA ✅ | 0.7mA ✅ | 3.0mA ❌ |
| **Tier** | **REF** | **★★★★** | **★★★** | **★★☆** |

### Formatting
- ✅ cells: green text
- ⚠️ cells: orange text
- ❌ cells: red text, bold
- Reference column: light blue background
- Tier row: bold, colored by tier
