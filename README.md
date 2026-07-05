# tes3-records

Record dump for Morrowind, Tribunal, Bloodmoon, [Tamriel_Data](https://www.nexusmods.com/morrowind/mods/44537),
[TR_Mainland](https://www.nexusmods.com/morrowind/mods/42145) and
[OAAB_Data](https://www.nexusmods.com/morrowind/mods/49042), one YAML file per
record, organized as `<Source>/<RecordType>/<id>.yaml`.

## Search website

The repository ships a static search site (GitHub Pages) that lets you search
all ~55,000 records by name or id, filter by source, record type and item tag
(e.g. `Chitin` + `Cuirass`), and view the full data of every record.

### How it works

- `scripts/build_site_data.py` walks all YAML records and generates:
  - `site/data/index.json` — a compact search index (`id`, `name`, `type`,
    `source`) that the browser loads once (~400 KB gzipped),
  - `site/data/shards/<Source>__<Type>.json` — the full records, lazy-loaded
    only when you open a record's detail view,
  - `site/data/meta.json` — sources, record types, tags and counts. Item tags
    come from the `_out` CSVs (see [Tagging items](#tagging-items)); they are
    attached to each record and exposed as a filter facet on the site,
  - `site/data/icons/**.png` — DDS/TGA files from `icons/` converted for
    browsers. Records whose `icon` field resolves to a file in `icons/`
    (matched case-insensitively, ignoring the `.tga`/`.dds` extension) show
    the icon in the detail panel. Drop more icons into `icons/` — mirroring
    the game's `Icons\` folder layout — and they are picked up on the next
    build.
- `site/` — a dependency-free HTML/JS/CSS single-page app. All searching and
  filtering happens client-side, so it works on GitHub Pages without any
  server.
- `.github/workflows/pages.yml` — rebuilds the database and deploys the site
  to GitHub Pages on every push to `main`. Generated data is never committed.

### Enabling GitHub Pages (one-time setup)

In the repository settings, go to **Settings → Pages** and set
**Source** to **GitHub Actions**. The next push to `main` (or a manual run of
the *Deploy search site to GitHub Pages* workflow) publishes the site at
`https://rfuzzo.github.io/tes3-records/`.

### Running locally

```sh
pip install pyyaml
python3 scripts/build_site_data.py   # writes site/data/ (~30 s)
cd site && python3 -m http.server    # open http://localhost:8000
```

## Regenerating the CSV dumps

The records are first extracted from the game plugins with `tes3util` (see the
comment in `scripts/generate.py`), then:

```sh
python3 scripts/generate.py       # fold the Tribunal/Bloodmoon folders into Morrowind/
python3 scripts/generate_csv.py   # write per-source/per-type id,name CSVs into _out/
python3 scripts/tag_records.py     # fill the tags column (see below)
```

`scripts/generate_csv.py` folds the Tribunal/Bloodmoon expansions into the
Morrowind CSVs (a DLC record overrides a base one with the same id) and leaves
the `tags` column empty for the tagger to fill.

### Tagging items

`scripts/tag_records.py` fills the `tags` column of the Armor / Ingredient /
MiscItem / Weapon CSVs with descriptive Morrowind tags (e.g.
*Chitin War Axe* → `Weapon, Axe, One-Handed, War Axe, Chitin`;
*Coda Flower* → `Ingredient, Plant, Flower`).

Weapon and armor type tags are read from the authoritative YAML records —
`data.weapon_type` for weapons, and `data.armor_type` plus the engine's
weight-class formula (weight vs a per-slot base weight) for the armor
Light/Medium/Heavy class, so e.g. *Ebony Mail* is correctly `Medium`. Materials,
cultures, the specific weapon type, ingredient categories (Plant / Creature /
Mineral / Food / Spice / Dye) and misc categories are keyword-derived from the
name — extend the dictionaries at the top of the script to refine those.

```sh
python3 scripts/tag_records.py           # tag all target CSVs
python3 scripts/tag_records.py --check    # report what would change, write nothing
```

`scripts/generate_csv.py` rewrites the CSVs with an empty tags column, so re-run
the tagger after regenerating.
