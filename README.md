# Electronics QA

**Electronics QA** is an open-source AI-powered quality assurance tool for electronics design.

It is built to help engineers catch issues early during design review and act as a first-pass QA assistant for electronics projects.

At the current stage, the project is focused primarily on **BOM validation and quality checks**, with future expansion planned for broader electronics design review.

---

## Current status

🚧 Early development

- BOM validation — in progress
- CLI (`eqa`) — in development
- Initial checks and review flow — in progress

---

## Current focus

The first version is focused on practical BOM QA checks that are useful in real hardware workflows.

### Planned checks

- **Lifecycle**
  - obsolete / NRND components
  - missing lifecycle information

- **RoHS compliance**
  - missing or inconsistent compliance data

- **Temperature range**
  - missing ratings
  - insufficient temperature range for expected conditions

- **Stock availability**
  - low or zero stock
  - sourcing risks

- **BOM structure**
  - required columns validation
  - mandatory fields:
    - designator
    - MPN
  - incomplete or inconsistent rows

---

## Why Electronics QA

Electronics reviews are often manual, inconsistent, and dependent on the reviewer.

This project aims to make QA checks more repeatable and scalable by using AI to assist with early-stage review.

The goal is not to replace engineering judgment, but to help engineers identify issues faster and more systematically.

---

## CLI

A command-line interface is planned for the project.

Example target workflow:

```bash
eqa check bom bom.csv
