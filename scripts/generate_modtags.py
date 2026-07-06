#!/usr/bin/env python3
"""Generate per-CSV tag-map YAML files under ``ModTags/``.

Each ``_out/<Source>_<Type>.csv`` is inverted into
``ModTags/<Source>_<Type>.yaml``: a map of tag -> the record ids carrying that
tag. Tag keys are lowercased. For example:

    axe:
      - chitin war axe
      - iron war axe
    shovel:
      - misc_de_muck_shovel_01
    wood:
      - ic_wood

Only CSVs that actually carry tags produce a file. Run after
``scripts/tag_records.py`` (the tags come from the CSVs' tags column).

Usage: python3 scripts/generate_modtags.py [--root REPO_ROOT] [--out MODTAGS_DIR]
"""

import argparse
import csv
import sys
from pathlib import Path

import yaml


class IndentDumper(yaml.Dumper):
    """Indent sequence items under their mapping key (matches the example)."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, indentless=False)


def tag_map_for(csv_path: Path):
    """Invert a CSV into {lowercased tag: [ids...]}, preserving CSV (id) order."""
    tag_map = {}
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            rid = row["id"]
            tags = (t.strip() for t in (row.get("tags") or "").split(","))
            for tag in tags:
                if tag:
                    tag_map.setdefault(tag.lower(), []).append(rid)
    return tag_map


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parent.parent,
                        help="repository root")
    parser.add_argument("--out", type=Path, default=None,
                        help="output directory (default: <root>/ModTags)")
    args = parser.parse_args()

    out_dir = args.out or args.root / "ModTags"
    out_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for csv_path in sorted((args.root / "_out").glob("*.csv")):
        tag_map = tag_map_for(csv_path)
        if not tag_map:
            continue  # untagged record types (Book, Static, ...) get no file
        ordered = {tag: tag_map[tag] for tag in sorted(tag_map)}
        yaml_path = out_dir / f"{csv_path.stem}.yaml"
        with yaml_path.open("w", encoding="utf-8") as fh:
            yaml.dump(ordered, fh, Dumper=IndentDumper, default_flow_style=False,
                      sort_keys=False, allow_unicode=True, width=1 << 20)
        print(f"Wrote {yaml_path.name} ({len(ordered)} tags)")
        written += 1

    print(f"\n{written} tag-map files -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
