#!/usr/bin/env python3
"""
dx-grab — Find and download files from DNAnexus projects.

Usage:
    python dx-grab.py --name PATTERN [--project PATTERN] [--folder PATTERN]
                      [--output DIR] [--dry-run]
"""

import argparse
import fnmatch
import re
import os
import sys
import time
from collections import defaultdict
from datetime import datetime


def parse_args():
    parser = argparse.ArgumentParser(
        description="Find and download files across DNAnexus projects.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python dx-grab.py --name "*.vcf.gz" --dry-run
  python dx-grab.py --project "*230601*" --name "*.vcf.gz" --dry-run
  python dx-grab.py --project "run_*" --folder "*/fastq*" --name "*.fastq.gz" --output ./fastqs
  python dx-grab.py --project "project-xxxx" --name "*.bam"
        """,
    )
    parser.add_argument(
        "--project",
        default=None,
        metavar="PATTERN",
        help="Project name glob pattern (e.g. '*230601*', 'run_*'). Default: all projects.",
    )
    parser.add_argument(
        "--folder",
        default=None,
        metavar="PATTERN",
        help="Folder path glob pattern to filter by (e.g. '*/fastq*'). Default: all folders.",
    )
    parser.add_argument(
        "--name",
        required=True,
        metavar="PATTERN",
        help="Filename glob pattern (e.g. '*.vcf.gz')",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Exclude files whose name matches this glob (e.g. '*Q*'). Repeatable.",
    )
    parser.add_argument(
        "--output",
        default="./downloads",
        metavar="DIR",
        help="Local download directory. Default: ./downloads",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Limit download to the first N matched files. All files are listed; only N are downloaded.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List matched files without downloading.",
    )
    return parser.parse_args()


def check_auth():
    import dxpy
    try:
        dxpy.whoami()
    except dxpy.exceptions.DXAPIError as e:
        if e.code == 401:
            print("ERROR: Not logged in to DNAnexus. Run `dx login` first.", file=sys.stderr)
        else:
            print(f"ERROR: DNAnexus API error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    return dxpy


def fmt_size(n_bytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n_bytes < 1024:
            return f"{n_bytes:.1f} {unit}"
        n_bytes /= 1024
    return f"{n_bytes:.1f} PB"


def _glob_to_iregex(pattern):
    """Convert a shell glob pattern to a case-insensitive PCRE-compatible regex."""
    regex = re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".")
    return "(?i)^" + regex + "$"


def find_projects(dxpy, pattern):
    if pattern:
        print(f"\nSearching for projects matching: {pattern!r}")
    else:
        print("\nSearching all accessible projects...")
    projects = list(dxpy.find_projects(describe=True))
    if pattern:
        projects = [p for p in projects
                    if fnmatch.fnmatch(p["describe"]["name"].lower(), pattern.lower())]
    if not projects:
        print("No projects found.", file=sys.stderr)
        sys.exit(1)
    print(f"Found {len(projects)} project(s):")
    for p in projects:
        print(f"  {p['describe']['name']}  ({p['id']})")
    return projects


def find_files(dxpy, projects, name_pattern, folder_pattern):
    print(f"\nSearching for files matching name={name_pattern!r}"
          + (f", folder={folder_pattern!r}" if folder_pattern else "") + " ...")

    results = []
    for proj in projects:
        proj_id = proj["id"]
        proj_name = proj["describe"]["name"]

        try:
            hits = dxpy.find_data_objects(
                classname="file",
                project=proj_id,
                name=_glob_to_iregex(name_pattern),
                name_mode="regexp",
                folder="/",
                recurse=True,
                describe=True,
            )
            for h in hits:
                desc = h["describe"]
                folder = desc.get("folder", "/")

                if folder_pattern and not fnmatch.fnmatch(folder.lower(), folder_pattern.lower()):
                    continue

                results.append({
                    "file_id": h["id"],
                    "project_id": proj_id,
                    "project_name": proj_name,
                    "name": desc["name"],
                    "folder": folder,
                    "size": desc.get("size", 0),
                    "archival_state": desc.get("archivalState", "live"),
                })
        except dxpy.exceptions.PermissionDenied:
            print(f"  WARNING: Permission denied for project {proj_name} ({proj_id}), skipping.",
                  file=sys.stderr)
        except dxpy.exceptions.ResourceNotFound:
            print(f"  WARNING: Project {proj_name} ({proj_id}) not found, skipping.",
                  file=sys.stderr)

    return results


def print_table(files):
    if not files:
        print("No files found.")
        return

    col_proj = max(len(f["project_name"]) for f in files)
    col_folder = max(len(f["folder"]) for f in files)
    col_name = max(len(f["name"]) for f in files)
    col_size = max(len(fmt_size(f["size"])) for f in files)
    col_state = max(len(f["archival_state"]) for f in files)

    # header
    h = (f"{'Project':<{col_proj}}  {'Folder':<{col_folder}}  "
         f"{'Name':<{col_name}}  {'Size':>{col_size}}  {'State':<{col_state}}")
    print("\n" + h)
    print("-" * len(h))
    for f in files:
        print(f"{f['project_name']:<{col_proj}}  {f['folder']:<{col_folder}}  "
              f"{f['name']:<{col_name}}  {fmt_size(f['size']):>{col_size}}  "
              f"{f['archival_state']:<{col_state}}")

    total = sum(f["size"] for f in files)
    print(f"\nTotal: {len(files)} file(s), {fmt_size(total)}")


def handle_archives(dxpy, files):
    """
    Prompt the user about archived files, submit unarchive requests if needed,
    and poll until all files that were archiving are live.
    Returns the (possibly updated) file list.
    """
    archived = [f for f in files if f["archival_state"] == "archived"]
    archival = [f for f in files if f["archival_state"] == "archival"]
    unarchiving = [f for f in files if f["archival_state"] == "unarchiving"]

    if archival:
        print(f"\nWARNING: {len(archival)} file(s) are currently being archived and cannot be "
              f"retrieved right now. They will be skipped:")
        for f in archival:
            print(f"  {f['project_name']}/{f['folder']}/{f['name']}")
        files = [f for f in files if f["archival_state"] != "archival"]

    if archived:
        print(f"\n{len(archived)} file(s) are archived:")
        for f in archived:
            print(f"  {f['project_name']}{f['folder']}/{f['name']}  ({fmt_size(f['size'])})")
        answer = input("\nUnarchive them? Unarchiving typically takes several hours. [y/N] ").strip().lower()
        if answer == "y":
            _submit_unarchive(dxpy, archived)
            for f in archived:
                f["archival_state"] = "unarchiving"
            unarchiving = unarchiving + archived
        else:
            print("Skipping archived files.")
            files = [f for f in files if f["archival_state"] != "archived"]

    if unarchiving:
        files = _poll_until_live(dxpy, files, unarchiving)

    return files


def _submit_unarchive(dxpy, files):
    """Group files by project and submit unarchive requests (max 1000 per call)."""
    by_project = defaultdict(list)
    for f in files:
        by_project[f["project_id"]].append(f["file_id"])

    for proj_id, file_ids in by_project.items():
        for i in range(0, len(file_ids), 1000):
            batch = file_ids[i:i + 1000]
            try:
                dxpy.api.project_unarchive(proj_id, {"files": batch})
            except Exception as e:
                print(f"  WARNING: Unarchive request failed for {proj_id}: {e}", file=sys.stderr)

    print(f"Unarchive requested for {len(files)} file(s).")


def _poll_until_live(dxpy, all_files, waiting):
    """Poll every 10 minutes until all waiting files are live."""
    waiting_ids = {f["file_id"] for f in waiting}
    file_index = {f["file_id"]: f for f in all_files}

    print(f"\nWaiting for {len(waiting_ids)} file(s) to unarchive (polling every 10 minutes).")
    print("Press Ctrl+C to abort — re-run the same command to resume.\n")

    try:
        while waiting_ids:
            now = datetime.now().strftime("%H:%M")
            still_waiting = set()
            for fid in waiting_ids:
                f = file_index[fid]
                try:
                    state = dxpy.DXFile(fid, project=f["project_id"]).describe(
                        fields={"archivalState": True}
                    )["archivalState"]
                    f["archival_state"] = state
                    if state != "live":
                        still_waiting.add(fid)
                except Exception as e:
                    print(f"  WARNING: Could not check state of {fid}: {e}", file=sys.stderr)
                    still_waiting.add(fid)

            ready = len(waiting_ids) - len(still_waiting)
            total = len(waiting_ids)
            print(f"[{now}] Waiting for unarchive: {ready}/{total} files ready...")

            if not still_waiting:
                print("All files are now live.")
                break

            waiting_ids = still_waiting
            time.sleep(600)  # 10 minutes

    except KeyboardInterrupt:
        print("\n\nUnarchiving in progress on DNAnexus. Re-run the same command to resume.")
        sys.exit(0)

    return all_files


def resolve_local_path(output_dir, files):
    """
    Assign a local path to each file. Prefix with project name when two
    files from different projects share the same filename.
    """
    name_to_projects = defaultdict(set)
    for f in files:
        name_to_projects[f["name"]].add(f["project_id"])

    for f in files:
        if len(name_to_projects[f["name"]]) > 1:
            safe_proj = f["project_name"].replace("/", "_")
            local_name = f"{safe_proj}__{f['name']}"
        else:
            local_name = f["name"]
        f["local_path"] = os.path.join(output_dir, local_name)

    return files


def download_files(dxpy, files, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    files = resolve_local_path(output_dir, files)

    live = [f for f in files if f["archival_state"] == "live"]
    skipped = len(files) - len(live)

    if skipped:
        print(f"\nSkipping {skipped} non-live file(s).")

    if not live:
        print("Nothing to download.")
        return

    total_size = sum(f["size"] for f in live)
    print(f"\nDownloading {len(live)} file(s) ({fmt_size(total_size)}) to {output_dir}/\n")

    for i, f in enumerate(live, 1):
        local = f["local_path"]
        print(f"[{i}/{len(live)}] {f['name']}  ({fmt_size(f['size'])})...")
        try:
            dxpy.download_dxfile(f["file_id"], local, project=f["project_id"])
            print(f"  -> {local}")
        except dxpy.exceptions.ResourceNotFound:
            print(f"  WARNING: File not found: {f['file_id']}", file=sys.stderr)
        except Exception as e:
            print(f"  WARNING: Download failed for {f['name']}: {e}", file=sys.stderr)

    print("\nDone.")


def main():
    args = parse_args()
    dxpy = check_auth()

    projects = find_projects(dxpy, args.project)
    files = find_files(dxpy, projects, args.name, args.folder)

    if args.exclude:
        before = len(files)
        files = [
            f for f in files
            if not any(fnmatch.fnmatch(f["name"].lower(), pat.lower()) for pat in args.exclude)
        ]
        excluded = before - len(files)
        if excluded:
            print(f"Excluded {excluded} file(s) matching: {', '.join(args.exclude)}")

    if not files:
        print("\nNo matching files found.")
        sys.exit(0)

    print_table(files)

    if args.dry_run:
        sys.exit(0)

    if args.limit is not None:
        if args.limit < len(files):
            # Sort live files first so the limit is filled without touching archived files
            files = sorted(files, key=lambda f: 0 if f["archival_state"] == "live" else 1)
            print(f"\nLimit set: downloading {args.limit} of {len(files)} matched file(s) "
                  f"(live files preferred).")
        files = files[:args.limit]

    files = handle_archives(dxpy, files)
    download_files(dxpy, files, args.output)


if __name__ == "__main__":
    main()
