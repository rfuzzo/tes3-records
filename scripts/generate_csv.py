#!/usr/bin/env python3
"""Write per-source/per-record-type ``id,name,tags`` CSVs into ``_out/``.

Each top-level source folder (Morrowind, OAAB_Data, TR_Mainland, Tamriel_Data)
becomes ``_out/<Source>_<Type>.csv``. The classic expansions nested under
Morrowind (Tribunal, Bloodmoon) are folded into the Morrowind CSVs: they are
walked after the base game, so a later (DLC) record overrides an earlier one
that shares its id, matching the game's plugin load order. The ``tags`` column
is left empty here — run ``scripts/tag_records.py`` afterwards to fill it.

Python port of the former _generate_csv.ps1.

Usage: python3 scripts/generate_csv.py [--root REPO_ROOT] [--out OUT_DIR]
"""

import argparse
import csv
import sys
from pathlib import Path

import yaml
try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:  # pure-python fallback
    from yaml import SafeLoader

# Expansion folders folded into their parent source, in load order (a later
# entry overrides an earlier one when both define a record with the same id).
NESTED_SOURCES = {"Morrowind": ("Tribunal", "Bloodmoon")}

# Top-level directories that are not record sources.
SKIP_DIRS = {"_out", "site", "scripts"}


def read_row(yaml_file: Path):
    """Return (id, name) for a record, matching the PowerShell field reader."""
    try:
        text = yaml_file.read_text(encoding="utf-8", errors="replace")
        data = yaml.load(text, Loader=SafeLoader)
    except yaml.YAMLError:
        data = None
    data = data if isinstance(data, dict) else {}
    rid = str(data.get("id") or yaml_file.stem)
    return rid, str(data.get("name") or "")


def type_names(source_dir: Path, nested) -> list:
    """Record-type folder names across the source and its expansions."""
    names = []
    for p in sorted(source_dir.iterdir()):
        if p.is_dir() and p.name not in nested and p.name not in names:
            names.append(p.name)
    for n in nested:
        nested_dir = source_dir / n
        if nested_dir.is_dir():
            for p in sorted(nested_dir.iterdir()):
                if p.is_dir() and p.name not in names:
                    names.append(p.name)
    return names


def write_csv(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_ALL, lineterminator="\n")
        writer.writerow(["id", "name", "tags"])
        for rid, name in rows:
            writer.writerow([rid, name, ""])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parent.parent,
                        help="repository root")
    parser.add_argument("--out", type=Path, default=None,
                        help="output directory (default: <root>/_out)")
    args = parser.parse_args()

    root: Path = args.root
    out_dir: Path = args.out or root / "_out"
    out_dir.mkdir(parents=True, exist_ok=True)

    sources = sorted(p for p in root.iterdir()
                     if p.is_dir() and p.name not in SKIP_DIRS
                     and not p.name.startswith("."))

    for source_dir in sources:
        nested = NESTED_SOURCES.get(source_dir.name, ())
        for rtype in type_names(source_dir, nested):
            # Source dirs for this type, base first then each expansion.
            dirs = [source_dir / rtype]
            dirs += [source_dir / n / rtype for n in nested]

            by_id = {}
            for d in dirs:
                if not d.is_dir():
                    continue
                for yaml_file in sorted(d.glob("*.yaml")):
                    rid, name = read_row(yaml_file)
                    by_id[rid] = name  # later dir (DLC) overrides an earlier one

            if not by_id:
                continue
            rows = sorted(by_id.items(), key=lambda kv: kv[0].lower())
            csv_path = out_dir / f"{source_dir.name}_{rtype}.csv"
            write_csv(csv_path, rows)
            print(f"Wrote {csv_path.name} ({len(rows)} records)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
