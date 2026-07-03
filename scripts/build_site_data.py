#!/usr/bin/env python3
"""Build the static search-site data from the YAML record dumps.

Walks every ``<Source>/<RecordType>/*.yaml`` file in the repository and writes:

  site/data/meta.json                  sources, record types and counts
  site/data/index.json                 compact search index [id, name, type, source]
  site/data/shards/<Source>__<Type>.json   full records keyed by id (lazy-loaded)

Usage: python3 scripts/build_site_data.py [--root REPO_ROOT] [--out SITE_DIR]
"""

import argparse
import json
import sys
import time
from pathlib import Path

import yaml

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:  # pure-python fallback
    from yaml import SafeLoader

# Top-level folders that contain record dumps. Morrowind nests the two
# expansions, which we surface as sources of their own.
SOURCE_DIRS = {
    "Morrowind": "Morrowind",
    "Tribunal": "Morrowind/Tribunal",
    "Bloodmoon": "Morrowind/Bloodmoon",
    "Tamriel_Data": "Tamriel_Data",
    "TR_Mainland": "TR_Mainland",
    "OAAB_Data": "OAAB_Data",
}

# Folders inside a source dir that are sources themselves, not record types.
NESTED_SOURCES = {"Tribunal", "Bloodmoon"}


def load_record(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        data = yaml.load(text, Loader=SafeLoader)
        if isinstance(data, dict):
            return data
    except yaml.YAMLError:
        pass
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=Path(__file__).resolve().parent.parent,
                        type=Path, help="repository root")
    parser.add_argument("--out", default=None, type=Path,
                        help="site directory (default: <root>/site)")
    args = parser.parse_args()

    root: Path = args.root
    site_dir: Path = args.out or root / "site"
    data_dir = site_dir / "data"
    shard_dir = data_dir / "shards"
    shard_dir.mkdir(parents=True, exist_ok=True)

    index = []           # [id, name, type, source]
    shards = {}          # shard key -> {id: record}
    counts = {}          # source -> count
    type_counts = {}     # type -> count
    errors = []
    started = time.time()

    for source, rel in SOURCE_DIRS.items():
        src_dir = root / rel
        if not src_dir.is_dir():
            print(f"warning: missing source dir {src_dir}", file=sys.stderr)
            continue
        for type_dir in sorted(p for p in src_dir.iterdir() if p.is_dir()):
            rtype = type_dir.name
            if source == "Morrowind" and rtype in NESTED_SOURCES:
                continue
            shard_key = f"{source}__{rtype}"
            shard = shards.setdefault(shard_key, {})
            for yaml_file in sorted(type_dir.glob("*.yaml")):
                record = load_record(yaml_file)
                if record is None:
                    errors.append(str(yaml_file.relative_to(root)))
                    continue
                rid = str(record.get("id") or yaml_file.stem)
                name = str(record.get("name") or "")
                record["_file"] = yaml_file.relative_to(root).as_posix()
                shard[rid] = record
                index.append([rid, name, rtype, source])
                counts[source] = counts.get(source, 0) + 1
                type_counts[rtype] = type_counts.get(rtype, 0) + 1
        print(f"{source}: {counts.get(source, 0)} records")

    for shard_key, shard in shards.items():
        out = shard_dir / f"{shard_key}.json"
        out.write_text(json.dumps(shard, ensure_ascii=False, separators=(",", ":")),
                       encoding="utf-8")

    (data_dir / "index.json").write_text(
        json.dumps({"records": index}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")

    meta = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "total": len(index),
        "sources": {s: counts.get(s, 0) for s in SOURCE_DIRS},
        "types": dict(sorted(type_counts.items())),
        "repo": "rfuzzo/tes3-records",
        "parse_errors": errors,
    }
    (data_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n{len(index)} records, {len(shards)} shards in "
          f"{time.time() - started:.1f}s -> {data_dir}")
    if errors:
        print(f"{len(errors)} files failed to parse (listed in meta.json)",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
