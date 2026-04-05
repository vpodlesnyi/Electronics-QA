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
| CLI (`eqa`) | 🔧 In development |
| Schematic review | 📋 Planned |

---

## How it works

Electronics QA is built as a set of **skills** — separate modules, each focused on one type of QA check. You run them from your terminal using Claude Code by typing a plain-language command. Claude reads your files, performs the analysis, and saves a report.

You do not need to write any code to use it.

---

## Requirements

- [Node.js](https://nodejs.org/) (v18 or later)
- An [Anthropic API key](https://console.anthropic.com/) (Claude Code uses it to run AI analysis)
- A terminal (macOS Terminal, Windows PowerShell, Linux shell)

---

## Setup (first time only)

**Step 1 — Install Claude Code:**
```bash
npm install -g @anthropic-ai/claude-code
```

**Step 2 — Set your API key:**
```bash
export ANTHROPIC_API_KEY=your-key-here
```
To avoid doing this every session, add the line above to your `~/.bashrc` or `~/.zshrc` file.

**Step 3 — Clone this repo:**
```bash
git clone <your-repo-url>
cd <your-repo>
```

**Step 4 — Start Claude Code inside the repo folder:**
```bash
claude
```

That's it. The skills and MCP plugin are loaded automatically — no extra configuration needed.

---

## Module: BOM QA

Validates a Bill of Materials against common production readiness criteria.

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

## Folder structure

```
.
├── .claude/
│   └── skills/
│       └── bom-qa/
│           └── SKILL.md      ← BOM QA skill definition
├── INPUT/
│   └── BOM/                  ← place your BOM files here before running
├── OUTPUT/
│   └── BOM/                  ← reports are saved here automatically (git-ignored)
├── .mcp.json                 ← MCP plugin configuration (loaded automatically by Claude Code)
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

---

## Notes

- Reports in `OUTPUT/BOM/` are git-ignored — only the folder structure is tracked in git
- The BOM QA skill does **not** suggest replacement parts — that is out of scope and will be a separate module
- Data lookups are live (DigiKey, Mouser, LCSC APIs + manufacturer websites) — stock numbers reflect the moment the check was run
