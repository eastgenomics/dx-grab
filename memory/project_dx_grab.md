---
name: dx-grab project context
description: Context for the dx-grab DNAnexus file finder/downloader tool at eastgenomics
type: project
originSessionId: 5684aff3-c294-4a42-bd66-1edf31b018b7
---
dx-grab is a Python CLI tool at `/home/wook/Documents/dx-grab/` for finding and downloading files across DNAnexus projects.

**Why:** Clinical bioinformatics team at East Genomics (org-emee_1) stores NGS sequencing runs as individual DNAnexus projects and needed a way to search and download files across them.

**How to apply:** When working on this tool, the repo is `eastgenomics/dx-grab` (public), `main` branch. All development has been directly on main — no PRs raised yet. The venv is at `.venv/` and must be recreated if the directory is moved (shebangs break on rename).

A preset system (`--preset NAME`) was added; presets are defined in the `PRESETS` dict at the top of `dx-grab.py`. Current presets: `haem-vcf` (HaemOnc diagnostic pre-workbook mutect2 VCFs from 2026 `002_26*MYE` projects).
