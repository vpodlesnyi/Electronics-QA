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

### STEP 0 — Part Number Inference (MANDATORY — run BEFORE any API call)

**This step is mandatory and must be completed before calling any API.**

For passive components, decode the part number to extract known parameters from industry
standards. These values are deterministic and do not require API confirmation — they follow
the JEDEC EIA-198 standard.

**MLCC dielectric temperature class (from part number suffix or description):**

| Code | Temperature Range | Notes |
|---|---|---|
| C0G / NP0 | –55°C to +125°C | Most stable; used for precision circuits |
| X5R | –55°C to +85°C | Good for decoupling |
| X7R | –55°C to +125°C | General purpose |
| X7S | –55°C to +125°C | Similar to X7R |
| Y5V | –30°C to +85°C | Least stable; avoid for precision |
| X8R | –55°C to +150°C | High temp |

Record the inferred temperature as "Inferred from JEDEC [code] class" in the Temp Source field.
This inferred value **must still be confirmed by at least one distributor attribute or datasheet** —
but it gives you a strong prior to compare against.

**Resistor series temperature ranges (standard per manufacturer series):**

| Series | Manufacturer | Temp Range |
|---|---|---|
| CRCW series | Vishay | –55°C to +155°C |
| RC / RV / RT series | Yageo | –55°C to +155°C |
| CRMA series | Vishay | –55°C to +155°C |
| ERJ series | Panasonic | –55°C to +155°C |
| CR series | Samsung | –55°C to +155°C |

**Diodes and TVS:**
- Standard switching diodes (1N4148, SOD-123): –55°C to +150°C (Tj max)
- TVS diodes: ambient operating typically –55°C to +150°C

**If JEDEC class or series temperature is inferrable, record it immediately as a "pre-research" value.**
This prevents the mistake of leaving temp as N/A after API lookups return incomplete descriptions.

---

### 3.1 API Lookups (run in parallel)

Use these tools simultaneously for each part:

1. **`jlc_get_part(mpn=MPN)`** — Searches LCSC/JLCPCB database by MPN. Returns: LCSC part
   code, stock, price, package, specs, datasheet URL, EasyEDA footprint status.
   Optionally follow up with **`jlc_stock_check(mpn=MPN)`** if you need a real-time stock
   confirmation (jlc_get_part data can lag slightly).
   > **Warning:** JLC description fields are summaries, not complete parameter tables.
   > A missing temperature or RoHS field in JLC output does NOT mean the value is unknown —
   > it means JLC did not include it in the description. Always proceed to DigiKey and Mouser.
   >
   > **Critical — JLC API miss ≠ not on LCSC:** `jlc_get_part` searches a local snapshot of
   > LCSC's catalog. If it returns no results, the part may still be listed on LCSC.com.
   > For any part not found by `jlc_get_part`, always follow up with a direct LCSC web search
   > (`WebFetch("https://www.lcsc.com/search?q=MPN")`) before concluding the part is unavailable.
   >
   > **Critical — LCSC datasheet URL must be fetched:** When `jlc_get_part` returns a
   > `datasheet` URL (usually `wmsc.lcsc.com` or `lcsc.com/datasheet/...`), that URL links to
   > the actual manufacturer datasheet hosted by LCSC. Always call `WebFetch(url=datasheet_url)`
   > to extract temperature, RoHS, and other parameters. This is where LCSC parametric data
   > lives for Chinese-market parts that don't appear on Mouser or DigiKey.

2. **`mouser_get_part(part_number=MPN)`** — Full Mouser lookup. Returns: detailed attributes
   including lifecycle status, RoHS, temperature range, stock, pricing tiers, datasheet link.
   You can batch up to 10 MPNs at once using pipe-delimited format: `"MPN1|MPN2|MPN3"`.

3. **`digikey_get_part(product_number=MPN)`** — DigiKey lookup. Returns: comprehensive
   parameters, availability, pricing, datasheet URL, lifecycle/status info.
   > **DigiKey is MANDATORY for every part where JLC or Mouser data is incomplete.**
   > DigiKey has the most normalized parameter tables of any distributor. Skipping DigiKey
   > when data is incomplete is a workflow error. Specifically, call DigiKey if:
   > - Temperature range is missing or N/A after JLC and Mouser
   > - RoHS status is missing or ambiguous after JLC and Mouser
   > - Lifecycle status is not clearly Active after JLC and Mouser
   > - The part was not found in JLC
   > - **Stock at JLC AND Mouser is zero** — DigiKey must always be the third stock check
   >   before a STOCK FAIL verdict can be issued. CC0402FPNPO9BN560 had 185k pcs on DigiKey
   >   when JLC=0 and Mouser=0. Never issue STOCK FAIL without a DigiKey stock check.
   > - The part is in WARN status for any reason (unknown mfr, not found, low stock)

4. **`cse_search(query=MPN)`** — ComponentSearchEngine lookup. Returns: additional datasheet
   URLs, package/footprint confirmation, and specs from a separate aggregator. Useful as a
   fourth data point when the three distributor APIs conflict or return incomplete data.

> **API priority for data fields:**
> - Lifecycle status: Manufacturer website > DigiKey > Mouser > LCSC
> - RoHS: Datasheet compliance section > Manufacturer website > DigiKey > Mouser > LCSC
> - Temperature range: Datasheet PDF (LCSC-hosted) > DigiKey parameters > Mouser attributes > JEDEC inference
> - Stock quantity: compare JLC + Mouser + DigiKey for **every** part; zero at two distributors
>   does NOT mean zero everywhere; all three must be checked before a stock verdict is issued

---

### 3.2 Mandatory Datasheet Fetch (NO EXCEPTIONS)

**Fetching at least one datasheet per unique MPN is mandatory. This step cannot be skipped.**

For every component:
1. Check if any API (JLC, Mouser, DigiKey) returned a datasheet URL.
2. If yes: call `WebFetch(url=datasheet_url)` with prompt:
   `"Extract: operating temperature range min and max from Absolute Maximum Ratings and
   Recommended Operating Conditions; RoHS compliance statement; package dimensions"`
3. **For LCSC-hosted datasheets specifically:** `jlc_get_part` (lcsc code lookup) returns a
   `datasheet` field pointing to `wmsc.lcsc.com` or `lcsc.com/datasheet/...`. This URL is the
   actual manufacturer datasheet, not a summary. Always fetch it — it is the primary source
   for Chinese-market parts that may not be indexed on Mouser or DigiKey.
4. If no datasheet URL was returned by any API, run:
   `WebSearch("[MPN] [manufacturer] datasheet filetype:pdf site:datasheet.octopart.com OR site:[manufacturer-domain]")`
   Then fetch the first PDF result.
5. Also check the **LCSC product page parametric table**: even when the JLC API returns empty
   specs, the LCSC product page (`lcsc.com/product-detail/...`) shows operating temperature
   and other parameters in a structured table. Fetch the LCSC product page when JLC API specs
   are empty. The LCSC part code (lcsc field) gives the direct URL.
6. From the datasheet or LCSC parametric table, extract:
   - **Operating Temperature** — from "Absolute Maximum Ratings", "Recommended Operating Conditions", or parametric table
   - **RoHS compliance** — from "Ordering Information", compliance section, LCSC ROHS badge, or RoHS/REACH declaration
   - **Package confirmation** — from "Package Information" or "Mechanical Dimensions"
7. Record the datasheet URL in the output — always.

> **Why this is mandatory:** API description fields are aggregator summaries. Datasheets and
> LCSC product pages are the primary source of truth. Any temperature range or RoHS status
> that cannot be traced to a datasheet, LCSC page, or manufacturer page is unverified data.

---

### 3.3 Manufacturer Website Verification

For lifecycle status specifically, always check the manufacturer's own product page:

Use `WebSearch` to find the official manufacturer product page:
> `[MPN] site:[manufacturer domain] product status`
> e.g. `STM32F103C8T6 site:st.com product status`

Then use `WebFetch` to read that page. Look for: Product Status, Lifecycle Phase,
Last Order Date, Last Ship Date. This is ground truth for lifecycle — treat it as such.

---

### 3.4 RoHS Reconciliation Rule

**When a distributor labels a part "RoHS Compliant By Exemption," do NOT use this as
the final RoHS answer.**

"By Exemption" means the component IS RoHS-3 compliant but contains a substance covered
by a listed exemption provision (e.g., Exemption 7c-I for lead in high-temperature solder
used in resistor terminations). This is a compliance characterization, not a
non-compliance finding.

Steps when you see "By Exemption":
1. Check the manufacturer's own compliance page (e.g., Yageo compliance declarations,
   Vishay RoHS page). Search: `"[manufacturer] [series] RoHS compliance declaration"`
2. Check the datasheet compliance section.
3. If the manufacturer confirms RoHS-3 compliance, record: **"Yes (RoHS-3, By Exemption [X])"**
   with a note explaining the exemption and confirming compliance.
4. Only mark as "Non-Compliant" if the manufacturer explicitly states the part does NOT
   comply with RoHS.
5. Flag a 🔴 SOURCE CONFLICT if the distributor label and manufacturer declaration
   differ in wording — even if both ultimately indicate compliance.

---

### 3.5 N/A Policy (STRICT — violating this is a workflow error)

**N/A may only be used for a field after ALL of the following have been attempted and
specifically failed to return that field's value:**

1. JEDEC/standard inference from part number or series (for passives)
2. `jlc_get_part` (lcsc code) — check `specs` and `attributes` fields, not just `description`
3. **LCSC product page** — `WebFetch("https://www.lcsc.com/product-detail/C{lcsc_code}.html")` — check the parametric table directly (often has temp when API specs is empty)
4. **LCSC-hosted datasheet** — if `jlc_get_part` returns a `datasheet` URL, fetch it now
5. `digikey_get_part` — check `parameters` field
6. `mouser_get_part` — check `attributes` field
7. `WebSearch("[MPN] datasheet operating temperature RoHS")` — fetch top result
8. Manufacturer official product page (`WebFetch`)
9. Datasheet PDF (`WebFetch` on datasheet URL or search result)

**For every N/A in the final report, you MUST document:**
- Which of the 9 steps above was attempted
- What was found at each step (even if "parameter not listed")
- Why the field remains unresolved

**If more than 20% of parts have N/A in any single field (temperature, RoHS, or lifecycle),
treat this as a red flag and re-examine your research process before writing the report.**

**Anti-regression rule:** If a user manually finds a value on DigiKey or LCSC that the
workflow missed, that is a process failure. After any such miss is reported:
1. Immediately re-open the audit for all parts that share the same root cause.
2. Identify which rule in this skill was not followed.
3. Apply the missing lookup to all other parts that may have the same gap.
4. Document the root cause in the report's conflict section.
Do not treat user-found values as isolated exceptions — treat them as signals of systematic gaps.

---

### 3.6 Data to Collect Per Component

For each field that has multiple source values, record all of them before settling on a final value.

| Field | Description |
|---|---|
| MPN | As-received from BOM |
| Manufacturer | From BOM or confirmed via lookup |
| Reference Designator(s) | From BOM |
| Lifecycle Status | Final value (Active / NRND / EOL / Discontinued / Unknown) |
| Lifecycle — Source Breakdown | e.g. "Mouser: Active · DigiKey: Active · Mfr website: Active" |
| Operating Temp Range | Final value (e.g. –40°C to +85°C) |
| Temp Range — Source Breakdown | e.g. "JEDEC X7R: –55/+125°C · DigiKey: –55/+125°C · Datasheet: –55/+125°C" |
| RoHS Compliant | Final value (Yes / Yes-By-Exemption [N] / No / Unknown) |
| RoHS — Source Breakdown | e.g. "Mouser: By Exemption · Manufacturer page: RoHS-3 Compliant" |
| Stock — Mouser | pcs |
| Stock — DigiKey | pcs |
| Stock — LCSC | pcs (confirmed via jlc_stock_check if real-time accuracy needed) |
| 🔴 Source Conflicts | List every field where sources disagreed and what each said |
| Datasheet URL | Link to the PDF that was fetched |
| Notes | Any other caveats or observations |

---

### 3.7 Conflict Detection Rules

After collecting all source values for a component, apply these checks and mark the row
with 🔴 **SOURCE CONFLICT** if any trigger:

- Lifecycle values differ between any two sources (e.g. Mouser says Active, DigiKey says NRND)
- Temperature range min or max differs by more than 5°C between any two sources
- RoHS status contradicts between sources (one says Yes, another says No or Unknown)
- A distributor's spec page and the manufacturer datasheet list different package codes
- A distributor says "By Exemption" and you have not yet confirmed the manufacturer's
  own compliance declaration

A 🔴 conflict does **not** mean the part fails compliance — it means the data is uncertain and
the engineer must manually verify before making a procurement decision. Always explain clearly
what was found on each source so they know exactly where to look.

---

## Phase 4 — Pre-Final Checklist (MANDATORY before writing any output)

Before generating any report output, verify every item on this checklist. Do not proceed
to Phase 5 until all items are checked.

- [ ] Operating temperature is filled for **100%** of parts, OR each N/A documents all 9 research steps per the N/A Policy
- [ ] RoHS is filled for **100%** of parts, OR each N/A documents all 9 research steps
- [ ] Lifecycle is confirmed for **100%** of parts, OR clearly marked Unknown with steps documented
- [ ] DigiKey was called for every part where JLC or Mouser returned incomplete parameters
- [ ] DigiKey was called for **every WARN part** (not found / unknown manufacturer)
- [ ] **DigiKey stock was checked before any STOCK FAIL verdict** — zero stock at JLC+Mouser does not mean zero everywhere
- [ ] At least one datasheet URL was fetched per unique MPN
- [ ] **LCSC product page was fetched** for any part where JLC API `specs` field was empty
- [ ] **LCSC-hosted datasheet was fetched** when `jlc_get_part` returned a `datasheet` URL
- [ ] For parts not found by `jlc_get_part`, a direct LCSC web search was performed
- [ ] No more than 20% of parts have N/A in any single field; if exceeded, re-examine research
- [ ] All "RoHS By Exemption" distributor labels are reconciled against manufacturer compliance pages
- [ ] Source conflicts are documented with all source values — not just the final verdict
- [ ] Stock data is cross-referenced across **all three distributors** (JLC, Mouser, DigiKey) per part
- [ ] JEDEC inference was applied before any API call for all passive components
- [ ] BOM-supplied manufacturer and component type labels were validated against distributor data (mismatches flagged)

---

## Phase 5 — Compliance Evaluation

For each component, compare the collected data against the user's criteria from Phase 2.

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

## Phase 6 — Output

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
  red for FAIL rows, orange for conflict rows, yellow for WARN rows.
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
In Excel output, highlight 🔴 conflict rows in orange; FAIL rows in red; PASS rows in green;
WARN rows in yellow.

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
  with note "Part not found — manual verification required." Document all 7 N/A steps.
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
- **JLC description ≠ complete datasheet**: JLC's description field is a brief summary. Missing
  temperature or RoHS in the JLC description means JLC didn't include it — not that it's unknown.
  Always check DigiKey parameters and the datasheet before concluding a value is unavailable.
- **JEDEC class is deterministic**: For MLCCs with a known dielectric code (C0G, X7R, X5R, etc.),
  the temperature class is defined by the standard. You do not need an API call to know that
  an X7R capacitor operates from –55 to +125°C. Record it, then confirm with a datasheet.
