#!/usr/bin/env python3
"""Build the static search-site data from the YAML record dumps.

Walks every ``<Source>/<RecordType>/*.yaml`` file in the repository and writes:

  site/data/meta.json                  sources, record types and counts
  site/data/index.json                 compact search index [id, name, type, source]
  site/data/shards/<Source>__<Type>.json   full records keyed by id (lazy-loaded)
  site/data/icons/<path>.png           icons/ DDS/TGA files converted for browsers

Records whose ``icon`` field resolves to a file under ``icons/`` get an
``_icon`` key with the browser path. Game icon paths are case-insensitive and
often name ``.tga`` while the shipped file is ``.dds``, so matching is done on
the lowercased path without extension.

Usage: python3 scripts/build_site_data.py [--root REPO_ROOT] [--out SITE_DIR]
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import yaml

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:  # pure-python fallback
    from yaml import SafeLoader

try:
    from PIL import Image
except ImportError:
    Image = None

# (display source, directory) pairs walked in order. The Tribunal and Bloodmoon
# expansions are folded into the Morrowind source; walking base -> Tribunal ->
# Bloodmoon means that when an id exists in more than one, the later (DLC)
# record overrides the earlier, matching the game's plugin load order.
SOURCE_DIRS = [
    ("Morrowind", "Morrowind"),
    ("Morrowind", "Morrowind/Tribunal"),
    ("Morrowind", "Morrowind/Bloodmoon"),
    ("Tamriel_Data", "Tamriel_Data"),
    ("TR_Mainland", "TR_Mainland"),
    ("OAAB_Data", "OAAB_Data"),
]

# Distinct display sources, in UI order.
SOURCES = ["Morrowind", "Tamriel_Data", "TR_Mainland", "OAAB_Data"]

# Subfolders of the Morrowind dir that are separate source dirs, not record types.
NESTED_DIRS = {"Tribunal", "Bloodmoon"}

# Record types whose _out/<Source>_<Type>.csv carries a tags column.
TAGGED_TYPES = ("Armor", "Ingredient", "MiscItem", "Weapon")


def load_tags(root: Path):
    """Read the tags columns of the _out CSVs into {(source, type, id): [tag]}."""
    out_dir = root / "_out"
    tags = {}
    if not out_dir.is_dir():
        return tags
    for rtype in TAGGED_TYPES:
        for csv_path in sorted(out_dir.glob(f"*_{rtype}.csv")):
            source = csv_path.stem[: -(len(rtype) + 1)]  # Foo_Weapon -> Foo
            with csv_path.open(encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    tag_list = [t.strip() for t in (row.get("tags") or "").split(",")
                                if t.strip()]
                    if tag_list:
                        tags[(source, rtype, row["id"])] = tag_list
    return tags


def icon_key(icon_field: str) -> str:
    """Normalize a record icon path ('pc\\n\\Foo.TGA') to a lookup key."""
    key = icon_field.replace("\\", "/").strip().strip("/").lower()
    return key.rsplit(".", 1)[0] if "." in key.rsplit("/", 1)[-1] else key


def convert_icons(root: Path, out_dir: Path):
    """Convert icons/**.dds|tga to PNG; return {key: browser path}."""
    icons_dir = root / "icons"
    converted = {}
    if not icons_dir.is_dir():
        return converted
    if Image is None:
        print("warning: Pillow not installed, skipping icon conversion",
              file=sys.stderr)
        return converted

    # .dds files win over same-named .tga; sorted() puts them first.
    sources = sorted(p for p in icons_dir.rglob("*")
                     if p.suffix.lower() in (".dds", ".tga"))
    failures = 0
    for src in sources:
        key = src.relative_to(icons_dir).with_suffix("").as_posix().lower()
        if key in converted:
            continue
        dest = out_dir / f"{key}.png"
        try:
            if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
                with Image.open(src) as im:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    im.convert("RGBA").save(dest, "PNG", optimize=True)
            converted[key] = f"icons/{key}.png"
        except Exception:
            failures += 1
    print(f"icons: converted {len(converted)} ({failures} unreadable)")
    return converted


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
    for stale in shard_dir.glob("*.json"):  # drop shards from a previous run
        stale.unlink()

    icons = convert_icons(root, data_dir / "icons")
    tag_lookup = load_tags(root)

    index = []           # [id, name, type, source, tags]
    shards = {}          # shard key -> {id: record}
    counts = {}          # source -> count
    type_counts = {}     # type -> count
    tag_counts = {}      # tag -> count
    errors = []
    started = time.time()

    overrides = 0
    for source, rel in SOURCE_DIRS:
        src_dir = root / rel
        if not src_dir.is_dir():
            print(f"warning: missing source dir {src_dir}", file=sys.stderr)
            continue
        for type_dir in sorted(p for p in src_dir.iterdir() if p.is_dir()):
            rtype = type_dir.name
            if rel == "Morrowind" and rtype in NESTED_DIRS:
                continue  # walked separately, still under the Morrowind source
            shard = shards.setdefault(f"{source}__{rtype}", {})
            for yaml_file in sorted(type_dir.glob("*.yaml")):
                record = load_record(yaml_file)
                if record is None:
                    errors.append(str(yaml_file.relative_to(root)))
                    continue
                rid = str(record.get("id") or yaml_file.stem)
                record["_file"] = yaml_file.relative_to(root).as_posix()
                icon = record.get("icon")
                if icon and isinstance(icon, str):
                    path = icons.get(icon_key(icon))
                    if path:
                        record["_icon"] = path
                tags = tag_lookup.get((source, rtype, rid), [])
                if tags:
                    record["_tags"] = tags
                if rid in shard:  # DLC record overriding a base one
                    overrides += 1
                shard[rid] = record

    # Build the index/counts from the deduped shards, so DLC overrides are
    # reflected and each effective record is listed exactly once.
    for shard_key, shard in shards.items():
        source, rtype = shard_key.rsplit("__", 1)
        out = shard_dir / f"{shard_key}.json"
        out.write_text(json.dumps(shard, ensure_ascii=False, separators=(",", ":")),
                       encoding="utf-8")
        for rid, record in shard.items():
            tags = record.get("_tags", [])
            index.append([rid, str(record.get("name") or ""), rtype, source, tags])
            counts[source] = counts.get(source, 0) + 1
            type_counts[rtype] = type_counts.get(rtype, 0) + 1
            for t in tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1

    for source in SOURCES:
        print(f"{source}: {counts.get(source, 0)} records")
    if overrides:
        print(f"{overrides} base records overridden by Tribunal/Bloodmoon")

    (data_dir / "index.json").write_text(
        json.dumps({"records": index}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")

    meta = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "total": len(index),
        "sources": {s: counts.get(s, 0) for s in SOURCES},
        "types": dict(sorted(type_counts.items())),
        # Tags sorted by frequency (descending) so the UI can show common first.
        "tags": dict(sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
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
