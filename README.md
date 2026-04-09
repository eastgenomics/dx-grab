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
source .venv/bin/activate
```

## Authentication

Log in to DNAnexus before use:

```bash
dx login
```

## Usage

```
python3 dx-grab.py --name PATTERN [--project PATTERN] [--folder PATTERN]
                   [--exclude PATTERN] [--output DIR] [--limit N] [--dry-run]
```

| Argument | Required | Description |
|---|---|---|
| `--name` | Yes | Filename glob (e.g. `*.vcf.gz`) |
| `--project` | No but HIGHLY recommended | Project name glob (e.g. `*230601*`). Default: all projects |
| `--folder` | No | Folder path glob (e.g. `*/fastq*`). Default: all folders |
| `--exclude` | No | Exclude files matching this glob (e.g. `*Q*`). Repeatable. |
| `--output` | No | Local download directory. Default: `./downloads` |
| `--limit` | No | Limit download to N files (all files are listed; live files are preferred) |
| `--dry-run` | No | List matched files without downloading |

## Examples

List all VCFs across every accessible project without downloading:

```bash
python3 dx-grab.py --name "*.vcf.gz" --dry-run
```

List all VCFs across projects matching `*230601*` without downloading:

```bash
python3 dx-grab.py --project "*230601*" --name "*.vcf.gz" --dry-run
```

Download FASTQs from all matching run projects into a local directory:

```bash
python3 dx-grab.py --project "run_*" --folder "*/fastq*" --name "*.fastq.gz" --output ./fastqs
```

Download all BAMs from a specific project by ID:

```bash
python3 dx-grab.py --project "project-xxxx" --name "*.bam" --output ./downloads
```

Find `*.filter.vcf.gz` but exclude any filenames containing `Q`:

```bash
python3 dx-grab.py --project "*230601*" --name "*.filter.vcf.gz" --exclude "*Q*" --dry-run
```

Exclude multiple patterns:

```bash
python3 dx-grab.py --name "*.vcf.gz" --exclude "*Q*" --exclude "*fail*"
```

Download up to 5 files, preferring live files over archived ones:

```bash
python3 dx-grab.py --project "*230601*" --name "*.vcf.gz" --limit 5
```

## Archived files

DNAnexus files may be in one of four states: `live`, `unarchiving`, `archived`, or `archival`.

- **live** — downloaded immediately
- **archived** — dx-grab will prompt you to unarchive; unarchiving typically takes several hours
- **unarchiving** — dx-grab polls every 10 minutes and downloads once all files are live
- **archival** — file is currently being archived and cannot be retrieved; it will be skipped

If you interrupt the tool during polling (`Ctrl+C`), the unarchive request remains active on DNAnexus. Re-run the same command to resume polling and download once the files are ready.
