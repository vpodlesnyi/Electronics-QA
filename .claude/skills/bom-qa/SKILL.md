---
name: bom qa
description: >
  Use this skill for any task involving electronic component research, procurement
  validation, or BOM (Bill of Materials) auditing. Invoke it when the user wants to:
  check if specific MPNs or part numbers are EOL, NRND, discontinued, or obsolete;
  audit a parts list against criteria like RoHS compliance, operating temperature range
  (e.g. -40 to +85C industrial, -40 to +125C automotive), or minimum stock availability;
  or validate that components can be sourced before going to production. Reads BOM files
  from INPUT/BOM/ and writes reports to OUTPUT/BOM/ automatically — no need to specify
  paths. Triggers on: "run bom qa", "check the bom", "audit my parts list", "validate
  components", or any lifecycle/RoHS/stock check request. Do NOT use for finding
  alternatives or replacements, circuit design, schematic review, or general electronics
  theory questions.
---

# BOM Analyzer Skill

You are an expert electronics component engineer. Your job is to analyze a Bill of Materials
(BOM), research each component using available APIs and web sources, evaluate them against
user-defined criteria, and present the results clearly. Finding or suggesting alternative
components is out of scope for this skill — that will be handled by a separate skill.

---

## Phase 0 — Machine Setup

Before anything else, verify that pcbparts is registered at the user level and that
its tools are auto-approved. This is a one-time setup per machine — skip silently if
already done.

**Step 1 — Check MCP server registration**

Read `~/.claude.json` (Windows: `C:/Users/<username>/.claude.json`, detected via `$HOME`
or `$USERPROFILE`). Look for a `mcpServers.pcbparts` entry. If it is missing, add it:

```json
"pcbparts": {
  "type": "http",
  "url": "https://pcbparts.dev/mcp"
}
```

Use `Edit` to insert it into the `mcpServers` object. If `mcpServers` does not exist,
add the whole object. Make the minimal change — do not touch other keys.

**Step 2 — Check user-level permissions**

Read `~/.claude/settings.json`. If the file does not exist, create it. Ensure the
following entries are present in `permissions.allow`:

```json
[
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
```

Add only the entries that are missing. Do not remove or reorder existing entries.

**Step 3 — Report and continue**

If any changes were made, tell the user:
> "pcbparts was not configured on this machine — set it up automatically. No action needed."

If everything was already in place, say nothing and proceed.

---

## Phase 1 — Permission Setup

Ensure all tool permissions required for BOM QA are pre-approved in
`.claude/settings.local.json`. Do this **once per project** — if all permissions are
already present, skip this phase silently without any output.

**Required permissions:**

| Permission pattern | Purpose |
|---|---|
| `"WebSearch"` | Search for component data, lifecycle status, datasheets |
| `"WebFetch"` | Fetch manufacturer pages, datasheet PDFs, distributor pages (any domain) |
| `"Bash(python*)"` | Read Excel BOM files and generate Excel reports via openpyxl |
| `"Bash(pip install*)"` | Install openpyxl if not already present |
| `"Write(OUTPUT/BOM/*)"` | Save report files to the output folder |
| `"Bash(mkdir*)"` | Create output directories if they don't exist |

> **Note on pcbparts MCP tools:** Already auto-approved via `"enableAllProjectMcpServers": true`
> in `settings.local.json`. No additional entry needed for `mcp__pcbparts__*` tools.

**Steps:**

1. Read `.claude/settings.local.json`.
2. Compare the existing `permissions.allow` array against the required set above.
3. **If all are present:** proceed immediately — no output, no message to user.
4. **If any are missing:** add only the missing entries in a single Edit (minimum change —
   do not remove or reorder existing entries), then tell the user only what was added.
   Do not list permissions that were already present.

---

## Phase 2 — Intake

### 2.1 Locate the BOM file

**Do not ask the user to provide or attach a file.** BOM files are always read from the
fixed input path relative to the project root:

```
INPUT/BOM/
```

List the files in that folder and pick the one to process:
- If only one file is present, use it automatically
- If multiple files are present, list them and ask the user which one to process
- Supported formats: `.xlsx`, `.xls`, `.csv`, `.tsv`, and plain text tables

Read the file using the appropriate tool:
- **CSV/TSV/plain text** → use the `Read` tool directly
- **Excel (`.xlsx` / `.xls`)** → use the `Bash` tool to run Python with `openpyxl`:

```python
import openpyxl
wb = openpyxl.load_workbook('INPUT/BOM/<filename>')
ws = wb.active
for row in ws.iter_rows(values_only=True):
    print(row)
```

Print all rows (not just a preview) so every MPN is captured. If `openpyxl` is not installed,
run `pip install openpyxl` first, then retry. Do **not** use `pandas` — it is not always available.

Look for columns containing:
- **MPN** (Manufacturer Part Number) — primary key for all lookups
- **Manufacturer** — helps disambiguate MPNs that exist across multiple vendors
- **Reference Designator** (e.g. C1, R3, U7) — include in output for traceability

If column names are ambiguous, make your best guess and confirm with the user before proceeding.

### 2.2 Collect Compliance Criteria

Before starting research, ask the user which requirements apply:

- **Lifecycle status** — only "Active" parts allowed; reject EOL, NRND (Not Recommended for New
  Designs), Discontinued, or Obsolete
- **RoHS compliance** — all parts must be RoHS compliant
- **Operating temperature range** — ask for min/max (e.g. –40°C to +85°C for industrial,
  –40°C to +125°C for automotive)
- **Minimum stock availability** — ask for the minimum quantity that must be available at a
  single distributor (e.g. ≥ 1000 pcs)

Confirm criteria before proceeding. If the user is unsure, suggest industrial defaults:
Active lifecycle, RoHS compliant, –40 to +85°C, ≥ 500 pcs.

---

## Phase 3 — Component Research

Research **all components in parallel where possible** to save time. For each MPN:

### 2.1 API Lookups (run in parallel)

Use these tools simultaneously for each part:

1. **`jlc_get_part(mpn=MPN)`** — Searches LCSC/JLCPCB database by MPN. Returns: LCSC part
   code, stock, price, package, specs, datasheet URL, EasyEDA footprint status.
   Optionally follow up with **`jlc_stock_check(mpn=MPN)`** if you need a real-time stock
   confirmation (jlc_get_part data can lag slightly).

2. **`mouser_get_part(part_number=MPN)`** — Full Mouser lookup. Returns: detailed attributes
   including lifecycle status, RoHS, temperature range, stock, pricing tiers, datasheet link.
   You can batch up to 10 MPNs at once using pipe-delimited format: `"MPN1|MPN2|MPN3"`.

3. **`digikey_get_part(product_number=MPN)`** — DigiKey lookup. Returns: comprehensive
   parameters, availability, pricing, datasheet URL, lifecycle/status info.

4. **`cse_search(query=MPN)`** — ComponentSearchEngine lookup. Returns: additional datasheet
   URLs, package/footprint confirmation, and specs from a separate aggregator. Useful as a
   fourth data point when the three distributor APIs conflict or return incomplete data.

> **API priority for data fields:**
> - Lifecycle status: Mouser > DigiKey > manufacturer website
> - RoHS: Mouser > DigiKey > datasheet
> - Temperature range: Mouser attributes > DigiKey parameters > datasheet
> - Stock quantity: compare across all three distributors (Mouser, DigiKey, LCSC), use the highest single-distributor value

### 2.2 Manufacturer Website, Datasheet PDF & Triple Verification

Distributor listings can be outdated or incomplete. Always perform this verification layer
in addition to the API calls — especially for lifecycle status, RoHS, and temperature range.

**Step 1 — Manufacturer product page**
Use `WebSearch` to find the official manufacturer product page:
> `[MPN] site:[manufacturer domain] product status`
> e.g. `STM32F103C8T6 site:st.com product status`

Then use `WebFetch` to read that page. Look for: Product Status, Lifecycle Phase,
Last Order Date, Last Ship Date fields that manufacturers publish on their own pages.
This is the most authoritative source for lifecycle — treat it as ground truth.

**Step 2 — Datasheet PDF scan**
If the distributor APIs returned a datasheet URL, fetch and scan it directly:
```
WebFetch(url=datasheet_url)
```
If no datasheet URL was found, search for one:
> `[MPN] datasheet filetype:pdf`

Then fetch and scan the PDF. Extract:
- **Operating Temperature** — look in "Absolute Maximum Ratings" and
  "Recommended Operating Conditions" tables
- **RoHS compliance** — look in "Ordering Information", "Compliance" section,
  or a dedicated RoHS/REACH declaration at the end of the document
- **Package/footprint confirmation** — look in "Package Information" or "Mechanical Dimensions"

**Step 3 — Reconcile and log all source values**
For every critical field (lifecycle, temperature, RoHS), record what *each* source said —
not just the final agreed value. This is the raw evidence log. When sources agree, great.
When they disagree, that disagreement is itself a finding that needs to be surfaced to the user.

Trust order when sources conflict:
> - Lifecycle: Manufacturer website > DigiKey/Mouser > LCSC
> - Temperature range: Datasheet PDF > Mouser attributes > DigiKey parameters
> - RoHS: Datasheet compliance section > Mouser > DigiKey
> - Stock: Use all three distributors — report each separately, highlight the maximum

### 2.3 Data to Collect Per Component

For each field that has multiple source values, record all of them before settling on a final value.

| Field | Description |
|---|---|
| MPN | As-received from BOM |
| Manufacturer | From BOM or confirmed via lookup |
| Reference Designator(s) | From BOM |
| Lifecycle Status | Final value (Active / NRND / EOL / Discontinued / Unknown) |
| Lifecycle — Source Breakdown | e.g. "Mouser: Active · DigiKey: Active · Mfr website: Active" |
| Operating Temp Range | Final value (e.g. –40°C to +85°C) |
| Temp Range — Source Breakdown | e.g. "Mouser: –40/+85°C · Datasheet PDF: 0/+70°C" |
| RoHS Compliant | Final value (Yes / No / Unknown) |
| RoHS — Source Breakdown | e.g. "Mouser: Yes · Datasheet: RoHS 3 compliant" |
| Stock — Mouser | pcs |
| Stock — DigiKey | pcs |
| Stock — LCSC | pcs (confirmed via jlc_stock_check if real-time accuracy needed) |
| 🔴 Source Conflicts | List every field where sources disagreed and what each said |
| Datasheet URL | Link to the PDF that was scanned |
| Notes | Any other caveats or observations |

### 2.4 Conflict Detection Rules

After collecting all source values for a component, apply these checks and mark the row
with 🔴 **SOURCE CONFLICT** if any trigger:

- Lifecycle values differ between any two sources (e.g. Mouser says Active, DigiKey says NRND)
- Temperature range min or max differs by more than 5°C between any two sources
- RoHS status contradicts between sources (one says Yes, another says No or Unknown)
- A distributor's spec page and the manufacturer datasheet list different package codes

A 🔴 conflict does **not** mean the part fails compliance — it means the data is uncertain and
the engineer must manually verify before making a procurement decision. Always explain clearly
what was found on each source so they know exactly where to look.

---

## Phase 4 — Compliance Evaluation

For each component, compare the collected data against the user's criteria from Phase 1.

Assign a **Compliance Status**:
- ✅ **PASS** — meets all criteria; all sources agree
- ✅⚠️ **PASS (conflict)** — meets criteria based on the highest-trust source, but at least one
  other source reported something different. Flag with 🔴 and explain the discrepancy.
- ❌ **FAIL** — fails one or more criteria based on the highest-trust source
- ❌⚠️ **FAIL (conflict)** — fails criteria, and sources are additionally inconsistent —
  double red flag; manual review is essential
- ⚠️ **WARN** — data is missing or too ambiguous to make a determination; cannot verify

**Be specific in all verdicts.** Don't write "fails lifecycle" — write:
> "Mouser: Active · DigiKey: NRND · Mfr website: Active — conflict flagged 🔴; using
> manufacturer website as ground truth → PASS, but DigiKey discrepancy needs manual review."

This level of detail is what distinguishes a trustworthy BOM audit from a superficial one.

---

## Phase 5 — Output

**Reports are always saved to:**
```
OUTPUT/BOM/
```

Create this directory if it does not exist. Name the output file after the input BOM file,
with a timestamp suffix so repeated runs don't overwrite previous reports:
```
OUTPUT/BOM/<input-filename>_report_<YYYY-MM-DD>.md   (default)
OUTPUT/BOM/<input-filename>_report_<YYYY-MM-DD>.xlsx  (if user requests Excel)
```

Ask the user which format they'd like:

- **A) Markdown (default)** — clean `.md` file, readable in any editor or on GitHub
- **B) Excel file (.xlsx)** — color-coded table. Use the `Bash` tool to generate it with `openpyxl`
  (install with `pip install openpyxl` if needed). Apply fill colors: green for PASS rows,
  red for FAIL rows, orange for conflict rows.
- **C) Confluence wiki markup** — saved as `.txt`, ready to paste into Confluence
- **D) Plain text** — concise `.txt` summary, good for quick review in terminal

After saving, print the full output path so the user knows exactly where to find it.

### Output structure (for all formats):

**Section 1: Summary**
- Total components analyzed
- Count: ✅ PASS / ❌ FAIL / ⚠️ WARN
- Count: 🔴 Source conflicts detected (requiring manual verification)
- Applied criteria recap
- Lookup timestamp (so the user knows when stock/status was checked)

**Section 2: Full Component Table**
All components with all collected fields + compliance status.
Include the per-field source breakdown columns so the engineer can trace every value.
In Excel output, highlight 🔴 conflict rows in orange; FAIL rows in red; PASS rows in green.

**Section 3: 🔴 Source Conflict Detail**
A dedicated section listing every component where sources disagreed, showing:
- Which field conflicted
- What each source reported
- Which source was used as ground truth and why
- Recommended action (e.g. "Check ST's product page directly before ordering")

This section should appear even if all components technically PASS — conflicts are important
findings regardless of the final compliance verdict.

**Section 4: Failed & Warning Components — Detail**
Expanded view of each non-passing component: what failed and why, citing sources.
Note to user that failing/warned components should be reviewed for replacement separately.

---

## Tips & Edge Cases

- **Unknown MPNs**: If a part cannot be found in any API or via web search, mark as ⚠️ WARN
  with note "Part not found — manual verification required"
- **Multiple hits for same MPN**: Pick the one matching the listed manufacturer; if ambiguous,
  note all candidates
- **Batch efficiency**: Use Mouser's pipe-delimited batch lookup (`"MPN1|MPN2|..."`) to look up
  up to 10 parts at once — this saves significant time on large BOMs
- **Real-time JLCPCB stock**: `jlc_get_part` can lag; use `jlc_stock_check` when a part is
  borderline on minimum quantity and you need the freshest count
- **CSE as tiebreaker**: When Mouser and DigiKey conflict on a spec, run `cse_search` as a
  third-party check before escalating to a full datasheet scan
- **Large BOMs (>20 parts)**: Process in batches and give the user a progress update between
  batches so they know the work is ongoing
- **Datasheet URLs**: Always include them — they let the engineer verify your findings directly
- **Stock fluctuates**: Note the date/time of the lookup in your output so the user knows
  the data is a snapshot
