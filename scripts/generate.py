#!/usr/bin/env python3
"""Fold the classic DLC dumps into the Morrowind source folder.

The records are first extracted with tes3util, e.g.:

    tes3util dump .\\ -o .\\ -c -i ACTI, MISC, STAT, WEAP, CONT, LIGH, ARMO, \\
        CLOT, REPA, APPA, LOCK, PROB, INGR, BOOK, ALCH

which leaves ``Tribunal`` and ``Bloodmoon`` folders next to ``Morrowind``. This
script moves them inside ``Morrowind/`` (in that order) so the expansions live
under the Morrowind source. It is a no-op once they are already in place.

Python port of the former _generate.ps1.

Usage: python3 scripts/generate.py [--root REPO_ROOT]
"""

import argparse
import shutil
import sys
from pathlib import Path

# Classic DLC folders, merged in this order.
DLC_FOLDERS = ("Tribunal", "Bloodmoon")


def move_into_morrowind(root: Path, folder: str) -> None:
    source = root / folder
    destination = root / "Morrowind" / folder

    if not source.is_dir():
        print(f"Skipping {folder}: source folder not found.")
        return
    if destination.is_dir():
        print(f"Skipping {folder}: already present in Morrowind.")
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    print(f"Moved {folder} into Morrowind.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parent.parent,
                        help="repository root (default: the repo this script is in)")
    args = parser.parse_args()

    for folder in DLC_FOLDERS:
        move_into_morrowind(args.root, folder)
    return 0


if __name__ == "__main__":
    sys.exit(main())
