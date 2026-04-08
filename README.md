# dx-grab

A command-line tool to find and download files across DNAnexus projects.

## Requirements

- Python 3
- [dxpy](https://pypi.org/project/dxpy/)

## Installation

```bash
git clone https://github.com/eastgenomics/dx-grab.git
cd dx-grab
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Authentication

Log in to DNAnexus before use:

```bash
dx login
```

## Usage

```
python dx-grab.py --project PATTERN [--folder PATTERN] [--name PATTERN]
                  [--output DIR] [--dry-run]
```

| Argument | Required | Description |
|---|---|---|
| `--project` | Yes | Project name glob (e.g. `*230601*`) |
| `--folder` | No | Folder path glob (e.g. `*/fastq*`). Default: all folders |
| `--name` | No | Filename glob (e.g. `*.vcf.gz`). Default: all files |
| `--output` | No | Local download directory. Default: `./downloads` |
| `--dry-run` | No | List matched files without downloading |

## Examples

List all VCFs across projects matching `*230601*` without downloading:

```bash
python dx-grab.py --project "*230601*" --name "*.vcf.gz" --dry-run
```

Download FASTQs from all matching run projects into a local directory:

```bash
python dx-grab.py --project "run_*" --folder "*/fastq*" --name "*.fastq.gz" --output ./fastqs
```

Download all files from a specific project by ID:

```bash
python dx-grab.py --project "project-xxxx" --output ./downloads
```

## Archived files

DNAnexus files may be in one of four states: `live`, `unarchiving`, `archived`, or `archival`.

- **live** — downloaded immediately
- **archived** — dx-grab will prompt you to unarchive; unarchiving typically takes several hours
- **unarchiving** — dx-grab polls every 10 minutes and downloads once all files are live
- **archival** — file is currently being archived and cannot be retrieved; it will be skipped

If you interrupt the tool during polling (`Ctrl+C`), the unarchive request remains active on DNAnexus. Re-run the same command to resume polling and download once the files are ready.
