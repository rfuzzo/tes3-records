#!/usr/bin/env python3
"""Fill the ``tags`` column of the Armor / Ingredient / MiscItem / Weapon CSVs
in ``_out/`` with descriptive tags, in a Morrowind context.

Tags are derived from each record's name (and, for Tamriel_Data ingredients,
the id prefix taxonomy T_IngFlor/Food/Crea/Mine/Spice/Dye). The rules encode
Morrowind item vocabulary: weapon and armor names carry their type + material,
so those tag richly; ingredients get a category (Plant/Creature/Mineral/Food/
Spice/Dye) plus a subtype; misc items get a functional category.

Because ``_generate_csv.ps1`` rewrites these CSVs with an empty tags column,
re-run this script after regenerating to repopulate the tags.

Usage: python3 scripts/tag_records.py [--root REPO_ROOT] [--check]
"""

import argparse
import csv
import re
import sys
from pathlib import Path

TARGET_TYPES = ("Armor", "Ingredient", "MiscItem", "Weapon")


def word(kw: str) -> re.Pattern:
    """Whole-word matcher, tolerating an optional trailing plural 's'."""
    return re.compile(r"(?<![a-z0-9])" + re.escape(kw) + r"s?(?![a-z0-9])")


def compile_pairs(pairs):
    return [(word(kw), tag) for kw, tag in pairs]


# --- materials and cultures/styles (shared by weapons, armor, misc) ----------
# Order matters: multi-word and more specific entries first.
DESCRIPTORS = compile_pairs([
    ("netch leather", "Netch Leather"), ("boiled netch", "Netch Leather"),
    ("stalhrim", "Stalhrim"), ("adamantium", "Adamantium"),
    ("adamantite", "Adamantium"),
    ("dwarven", "Dwemer"), ("dwemer", "Dwemer"), ("dwemeri", "Dwemer"),
    ("daedric", "Daedric"), ("ebony", "Ebony"),
    ("malachite", "Glass"), ("glass", "Glass"),
    ("orichalc", "Orcish"), ("orcish", "Orcish"),
    ("bonemold", "Bonemold"), ("chitin", "Chitin"),
    ("silver", "Silver"), ("steel", "Steel"), ("iron", "Iron"),
    ("corprus", "Corprus"), ("dreugh", "Dreugh"),
    ("golden", "Gold"), ("gold", "Gold"),
    ("stoneware", "Stoneware"), ("ceramic", "Ceramic"), ("pewter", "Pewter"),
    ("bronze", "Bronze"), ("redware", "Redware"), ("clay", "Clay"),
    ("chainmail", "Chainmail"), ("ringmail", "Chainmail"), ("chain", "Chainmail"),
    ("lamellar", "Lamellar"), ("leather", "Leather"), ("fur", "Fur"),
    ("wooden", "Wood"), ("wood", "Wood"), ("bone", "Bone"),
    ("indoril", "Indoril"), ("ordinator", "Ordinator"),
    ("telvanni", "Telvanni"), ("redoran", "Redoran"), ("hlaalu", "Hlaalu"),
    ("colovian", "Colovian"), ("chuzei", "Chuzei"), ("templar", "Templar"),
    ("nordic", "Nordic"), ("imperial", "Imperial"),
    ("ashlander", "Ashlander"), ("velothi", "Velothi"),
    ("ayleid", "Ayleid"), ("ynesai", "Ynesai"),
    ("sixth house", "Sixth House"), ("6th", "Sixth House"),
    ("dark brotherhood", "Dark Brotherhood"),
    ("argonian", "Argonian"), ("khajiit", "Khajiit"),
    ("redguard", "Redguard"), ("breton", "Breton"),
])

# Materials that map to a Morrowind armor skill class (conservative — only the
# ones whose class is unambiguous in the base game).
ARMOR_CLASS = {
    "Iron": "Heavy", "Steel": "Heavy", "Silver": "Heavy", "Dwemer": "Heavy",
    "Ebony": "Heavy", "Daedric": "Heavy", "Indoril": "Heavy",
    "Bonemold": "Medium", "Orcish": "Medium", "Nordic": "Medium",
    "Adamantium": "Medium", "Dreugh": "Medium", "Chainmail": "Medium",
    "Netch Leather": "Light", "Chitin": "Light", "Glass": "Light",
    "Fur": "Light", "Leather": "Light",
}

# --- weapons: (keyword, specific type, broad class) --------------------------
WEAPON_RAW = [
    ("throwing star", "Throwing Star", "Thrown"),
    ("throwing knife", "Throwing Knife", "Thrown"),
    ("throwing dagger", "Throwing Dagger", "Thrown"),
    ("throwing axe", "Throwing Axe", "Thrown"),
    ("dai-katana", "Dai-katana", "Long Blade"),
    ("dai katana", "Dai-katana", "Long Blade"),
    ("war axe", "War Axe", "Axe"),
    ("battle axe", "Battle Axe", "Axe"), ("battleaxe", "Battle Axe", "Axe"),
    ("war hammer", "Warhammer", "Blunt"), ("warhammer", "Warhammer", "Blunt"),
    ("morning star", "Morningstar", "Blunt"), ("morningstar", "Morningstar", "Blunt"),
    ("longbow", "Longbow", "Marksman"), ("long bow", "Longbow", "Marksman"),
    ("shortbow", "Short Bow", "Marksman"), ("short bow", "Short Bow", "Marksman"),
    ("crossbow", "Crossbow", "Marksman"),
    ("broadsword", "Broadsword", "Long Blade"),
    ("longsword", "Longsword", "Long Blade"), ("long sword", "Longsword", "Long Blade"),
    ("shortsword", "Shortsword", "Short Blade"), ("short sword", "Shortsword", "Short Blade"),
    ("claymore", "Claymore", "Long Blade"),
    ("wakizashi", "Wakizashi", "Short Blade"),
    ("katana", "Katana", "Long Blade"),
    ("scimitar", "Scimitar", "Long Blade"),
    ("saber", "Saber", "Long Blade"), ("sabre", "Saber", "Long Blade"),
    ("rapier", "Rapier", "Long Blade"),
    ("tanto", "Tanto", "Short Blade"),
    ("dagger", "Dagger", "Short Blade"),
    ("halberd", "Halberd", "Spear"), ("javelin", "Javelin", "Spear"),
    ("glaive", "Glaive", "Spear"), ("trident", "Trident", "Spear"),
    ("lance", "Lance", "Spear"), ("pike", "Pike", "Spear"),
    ("spear", "Spear", "Spear"),
    ("mace", "Mace", "Blunt"), ("flail", "Flail", "Blunt"),
    ("club", "Club", "Blunt"), ("quarterstaff", "Staff", "Blunt"),
    ("staff", "Staff", "Blunt"), ("nunchaku", "Nunchaku", "Blunt"),
    ("axe", "Axe", "Axe"), ("hammer", "Hammer", "Blunt"),
    ("sword", "Sword", "Long Blade"),
    ("arrow", "Arrow", "Ammunition"), ("bolt", "Bolt", "Ammunition"),
    ("dart", "Dart", "Thrown"), ("star", "Throwing Star", "Thrown"),
    ("knife", "Knife", "Short Blade"), ("whip", "Whip", "Blunt"),
    ("cleaver", "Cleaver", "Axe"), ("scepter", "Scepter", "Blunt"),
    ("sceptre", "Scepter", "Blunt"), ("cutlass", "Cutlass", "Long Blade"),
    ("sickle", "Sickle", "Blade"), ("scythe", "Scythe", "Blade"),
    ("cudgel", "Cudgel", "Blunt"), ("cane", "Cane", "Blunt"),
    ("rod", "Rod", "Blunt"), ("pick", "Pick", "Blunt"),
    ("bow", "Bow", "Marksman"), ("blade", "Blade", "Blade"),
]
WEAPON_TYPES = [(word(k), s, b) for k, s, b in WEAPON_RAW]
# Fallback: match a type word even when fused to an element prefix, e.g.
# "Flamesword", "Shardarrow", "Frostdagger" -> no left word-boundary required.
# Restrict to tokens >= 4 chars so short ones don't hit random substrings.
WEAPON_LOOSE = [(re.compile(re.escape(k) + r"s?(?![a-z0-9])"), s, b)
                for k, s, b in WEAPON_RAW if k.isalpha() and len(k) >= 4]

# --- armor: (keyword, slot) --------------------------------------------------
ARMOR_SLOTS = [
    ("tower shield", "Tower Shield"), ("shield", "Shield"), ("heater", "Shield"),
    ("cuirass", "Cuirass"), ("breastplate", "Cuirass"), ("hauberk", "Cuirass"),
    ("helmet", "Helmet"), ("helm", "Helmet"), ("hood", "Hood"),
    ("hat", "Hat"), ("cap", "Cap"), ("mask", "Mask"), ("crown", "Crown"),
    ("circlet", "Circlet"),
    ("pauldron", "Pauldron"), ("spaulder", "Pauldron"),
    ("gauntlets", "Gauntlet"), ("gauntlet", "Gauntlet"), ("bracer", "Bracer"),
    ("gloves", "Gloves"),
    ("greaves", "Greaves"), ("cuisse", "Greaves"), ("skirt", "Skirt"),
    ("sabatons", "Boots"), ("boots", "Boots"), ("shoes", "Shoes"),
    ("ringmail", "Cuirass"), ("chainmail", "Cuirass"), ("mail", "Cuirass"),
    ("armor", "Armor"), ("armour", "Armor"),
]
ARMOR_SLOTS = [(word(k), s) for k, s in ARMOR_SLOTS]

# --- misc items: (keyword, category) ----------------------------------------
MISC_CATS = compile_pairs([
    ("key", "Key"), ("keystone", "Key"),
    ("soul gem", "Soul Gem"), ("soulgem", "Soul Gem"),
    ("propylon", "Propylon Index"),
    ("goblet", "Tableware"), ("tankard", "Tableware"), ("chalice", "Tableware"),
    ("bowl", "Tableware"), ("platter", "Tableware"), ("plate", "Tableware"),
    ("cup", "Tableware"), ("mug", "Tableware"), ("pitcher", "Tableware"),
    ("jug", "Tableware"), ("flask", "Tableware"), ("bottle", "Tableware"),
    ("kettle", "Tableware"), ("pot", "Tableware"), ("pan", "Tableware"),
    ("ladle", "Utensil"), ("fork", "Utensil"), ("spoon", "Utensil"),
    ("knife", "Utensil"), ("silverware", "Utensil"), ("utensil", "Utensil"),
    ("candle", "Lighting"), ("lantern", "Lighting"), ("lamp", "Lighting"),
    ("soul gem", "Soul Gem"),
    ("ingot", "Metal"), ("ore", "Ore"),
    ("ring", "Jewelry"), ("amulet", "Jewelry"), ("necklace", "Jewelry"),
    ("diamond", "Gem"), ("ruby", "Gem"), ("emerald", "Gem"),
    ("sapphire", "Gem"), ("pearl", "Gem"), ("gemstone", "Gem"), ("gem", "Gem"),
    ("basket", "Container"), ("sack", "Container"), ("barrel", "Container"),
    ("crate", "Container"), ("chest", "Container"), ("box", "Container"),
    ("scroll", "Paper"), ("letter", "Paper"), ("note", "Paper"),
    ("paper", "Paper"), ("page", "Paper"), ("index", "Paper"),
    ("painting", "Decoration"), ("statue", "Decoration"), ("idol", "Decoration"),
    ("figurine", "Decoration"), ("bust", "Decoration"), ("vase", "Decoration"),
    ("urn", "Urn"),
    ("skull", "Bone"), ("skeleton", "Bone"), ("bones", "Bone"), ("bone", "Bone"),
    ("ashes", "Remains"), ("remains", "Remains"),
    ("pillow", "Furnishing"), ("cushion", "Furnishing"), ("rug", "Furnishing"),
    ("comb", "Grooming"), ("mirror", "Grooming"), ("razor", "Grooming"),
    ("drum", "Instrument"), ("lute", "Instrument"), ("flute", "Instrument"),
    ("shell", "Shell"),
    ("cloth", "Cloth"), ("rag", "Cloth"), ("towel", "Cloth"),
    ("coherer", "Dwemer Artifact"), ("cog", "Dwemer Artifact"),
    ("gear", "Dwemer Artifact"), ("tube", "Dwemer Artifact"),
    ("scales", "Tool"), ("hammer", "Tool"), ("tongs", "Tool"),
    ("saw", "Tool"), ("shovel", "Tool"), ("pick", "Tool"),
    ("nail", "Tool"), ("pin", "Tool"), ("needle", "Tool"), ("pipe", "Tool"),
    ("dust", "Powder"), ("powder", "Powder"),
    ("coin", "Coin"), ("septim", "Coin"), ("drake", "Coin"),
])

# --- ingredients -------------------------------------------------------------
ING_PREFIX = {
    "T_IngFlor": "Plant", "T_IngFood": "Food", "T_IngCrea": "Creature",
    "T_IngMine": "Mineral", "T_IngSpice": "Spice", "T_IngDye": "Dye",
}

# (keyword, category, subtype-tag). First match sets the category; more specific
# / decisive keywords come first so e.g. "Ash Salts" -> Mineral, "Ash Yam" -> Food.
ING_RULES = [
    # prepared food
    ("bread", "Food", "Bread"), ("muffin", "Food", "Bread"),
    ("sweetroll", "Food", "Pastry"), ("biscuit", "Food", "Pastry"),
    ("pastry", "Food", "Pastry"), ("cake", "Food", "Pastry"),
    ("pie", "Food", "Food"), ("dough", "Food", "Food"),
    ("porridge", "Food", "Food"), ("jam", "Food", "Food"),
    ("dumpling", "Food", "Food"), ("jerky", "Food", "Food"),
    ("cheese", "Food", "Cheese"), ("scuttle", "Food", "Food"),
    ("yam", "Food", "Vegetable"), ("saltrice", "Food", "Grain"),
    ("wickwheat", "Food", "Grain"), ("cabbage", "Food", "Vegetable"),
    ("pomegranate", "Food", "Fruit"),
    # spice / dye
    ("moon sugar", "Spice", "Moon Sugar"), ("sugar", "Spice", "Spice"),
    ("pepper", "Spice", "Spice"), ("spice", "Spice", "Spice"),
    ("dye", "Dye", "Dye"), ("pigment", "Dye", "Dye"),
    # minerals / gems
    ("salts", "Mineral", "Salt"), ("salt", "Mineral", "Salt"),
    ("bonemeal", "Mineral", "Bonemeal"), ("gravedust", "Mineral", "Dust"),
    ("sulphur", "Mineral", "Mineral"), ("sulfur", "Mineral", "Mineral"),
    ("lodestone", "Mineral", "Mineral"), ("chalk", "Mineral", "Mineral"),
    ("obsidian", "Mineral", "Mineral"), ("pumice", "Mineral", "Mineral"),
    ("scrap metal", "Mineral", "Metal"), ("ingot", "Mineral", "Metal"),
    ("ore", "Mineral", "Ore"), ("meteor", "Mineral", "Mineral"),
    ("diamond", "Mineral", "Gem"), ("ruby", "Mineral", "Gem"),
    ("sapphire", "Mineral", "Gem"), ("emerald", "Mineral", "Gem"),
    ("topaz", "Mineral", "Gem"), ("amethyst", "Mineral", "Gem"),
    ("ametrine", "Mineral", "Gem"), ("amber", "Mineral", "Gem"),
    ("onyx", "Mineral", "Gem"), ("opal", "Mineral", "Gem"),
    ("peridot", "Mineral", "Gem"), ("garnet", "Mineral", "Gem"),
    ("tourmaline", "Mineral", "Gem"), ("diopside", "Mineral", "Gem"),
    ("moonstone", "Mineral", "Gem"), ("pearl", "Mineral", "Gem"),
    ("raw ebony", "Mineral", "Ore"), ("raw glass", "Mineral", "Ore"),
    ("raw gold", "Mineral", "Ore"),
    # fungus (plant)
    ("mushroom", "Plant", "Mushroom"), ("russula", "Plant", "Mushroom"),
    ("coprinus", "Plant", "Mushroom"), ("chanterelle", "Plant", "Mushroom"),
    ("fomentarius", "Plant", "Mushroom"), ("mycena", "Plant", "Mushroom"),
    ("polypore", "Plant", "Mushroom"), ("urnula", "Plant", "Mushroom"),
    ("bane", "Plant", "Mushroom"), ("facia", "Plant", "Mushroom"),
    ("dustcap", "Plant", "Mushroom"), ("bloat", "Plant", "Mushroom"),
    ("hypha", "Plant", "Mushroom"), ("spore", "Plant", "Spore"),
    # flora
    ("flower", "Plant", "Flower"), ("blossom", "Plant", "Flower"),
    ("rose", "Plant", "Flower"), ("lily", "Plant", "Flower"),
    ("petal", "Plant", "Petals"), ("anther", "Plant", "Flower"),
    ("leaf", "Plant", "Leaf"), ("leaves", "Plant", "Leaf"),
    ("root", "Plant", "Root"), ("seed", "Plant", "Seeds"),
    ("pod", "Plant", "Pod"), ("bark", "Plant", "Bark"),
    ("stalk", "Plant", "Stalk"), ("frond", "Plant", "Frond"),
    ("fern", "Plant", "Plant"), ("moss", "Plant", "Plant"),
    ("lichen", "Plant", "Lichen"), ("grass", "Plant", "Plant"),
    ("weed", "Plant", "Plant"), ("sedge", "Plant", "Plant"),
    ("berry", "Plant", "Berry"), ("fruit", "Plant", "Fruit"),
    ("kanet", "Plant", "Plant"), ("corkbulb", "Plant", "Plant"),
    ("hackle-lo", "Plant", "Plant"), ("roobrush", "Plant", "Plant"),
    ("scathecraw", "Plant", "Plant"), ("trama", "Plant", "Plant"),
    ("marshmerrow", "Plant", "Plant"), ("heather", "Plant", "Plant"),
    ("chokeweed", "Plant", "Plant"), ("bittergreen", "Plant", "Plant"),
    ("comberry", "Plant", "Berry"), ("willow", "Plant", "Plant"),
    ("bloodgrass", "Plant", "Plant"), ("harrada", "Plant", "Plant"),
    ("silkgut", "Plant", "Plant"),
    ("flax", "Plant", "Plant"), ("fiber", "Plant", "Fiber"),
    ("resin", "Plant", "Resin"), ("incense", "Plant", "Plant"),
    ("ampoule", "Plant", "Plant"),
    # creature / daedric parts
    ("hide", "Creature", "Hide"), ("pelt", "Creature", "Pelt"),
    ("fur", "Creature", "Fur"), ("beak", "Creature", "Beak"),
    ("talon", "Creature", "Talon"), ("gills", "Creature", "Gills"),
    ("leather", "Creature", "Leather"), ("scales", "Creature", "Scales"),
    ("scale", "Creature", "Scales"), ("meat", "Creature", "Meat"),
    ("flesh", "Creature", "Flesh"), ("heart", "Creature", "Heart"),
    ("claw", "Creature", "Claw"), ("teeth", "Creature", "Teeth"),
    ("tooth", "Creature", "Teeth"), ("tusk", "Creature", "Tusk"),
    ("horn", "Creature", "Horn"), ("hoof", "Creature", "Hoof"),
    ("feather", "Creature", "Feather"), ("plume", "Creature", "Feather"),
    ("wing", "Creature", "Wing"), ("egg", "Creature", "Egg"),
    ("shell", "Creature", "Shell"), ("skin", "Creature", "Skin"),
    ("hair", "Creature", "Hair"), ("tail", "Creature", "Tail"),
    ("venom", "Creature", "Venom"), ("poison", "Creature", "Venom"),
    ("blood", "Creature", "Blood"), ("marrow", "Creature", "Marrow"),
    ("jelly", "Creature", "Jelly"), ("gall", "Creature", "Gall"),
    ("bile", "Creature", "Bile"), ("gland", "Creature", "Gland"),
    ("carapace", "Creature", "Carapace"), ("sting", "Creature", "Stinger"),
    ("membrane", "Creature", "Membrane"), ("thorax", "Creature", "Thorax"),
    ("ectoplasm", "Creature", "Ectoplasm"), ("wax", "Creature", "Wax"),
    ("cuttle", "Food", "Food"), ("roe", "Food", "Roe"),
    ("milk", "Creature", "Milk"), ("liver", "Creature", "Organ"),
    ("ear", "Creature", "Ear"), ("eye", "Creature", "Eye"),
    ("silk", "Creature", "Silk"), ("soap", "Creature", "Soap"),
    ("lard", "Creature", "Fat"), ("dung", "Creature", "Dung"),
    ("corprusmeat", "Creature", "Meat"), ("corprus", "Creature", "Corprus"),
    ("fin", "Creature", "Fin"),
    # daedra / undead residues
    ("vampire dust", "Creature", "Dust"), ("lich dust", "Creature", "Dust"),
    ("ash", "Mineral", "Ash"), ("dust", "Mineral", "Dust"),
    ("clay", "Mineral", "Clay"), ("stone", "Mineral", "Mineral"),
    ("crystal", "Mineral", "Crystal"), ("water", "Mineral", "Water"),
    ("powder", "Mineral", "Powder"), ("ice", "Mineral", "Ice"),
]
ING_RULES = [(word(kw), cat, sub) for kw, cat, sub in ING_RULES]

# Known Morrowind creatures — add the creature's name as a tag on ingredients.
CREATURES = compile_pairs([(c, c.title()) for c in [
    "alit", "kagouti", "guar", "netch", "kwama", "scrib", "shalk", "dreugh",
    "mudcrab", "slaughterfish", "sturgeon", "cliff racer", "racer", "nix-hound",
    "rat", "durzog", "betty netch", "bull netch", "corprus", "ash hopper",
    "clannfear", "daedroth", "scamp", "dremora", "golden saint", "winged twilight",
    "ghoul", "lich", "vampire", "skeleton", "bonewalker", "bonelord",
    "spider", "wolf", "bear", "goat", "horse", "hound", "boar", "crab",
    "moth", "butterfly", "bristleback", "snow bear", "spriggan", "hunger",
]])

UNIQUE_RE = re.compile(r"uniq|unique|artifact|_uni_|_uni\b", re.IGNORECASE)


def find_first(name_lc, patterns):
    for entry in patterns:
        if entry[0].search(name_lc):
            return entry
    return None


def descriptors_for(name_lc):
    return [tag for pat, tag in DESCRIPTORS if pat.search(name_lc)]


def dedup(tags):
    seen, out = set(), []
    for t in tags:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def tag_weapon(rid, name):
    lc = name.lower()
    tags = ["Weapon"]
    hit = find_first(lc, WEAPON_TYPES) or find_first(lc, WEAPON_LOOSE)
    if hit:
        tags += [hit[2], hit[1]]  # broad class, specific type
    tags += descriptors_for(lc)
    if UNIQUE_RE.search(rid):
        tags.append("Unique")
    return dedup(tags)


def tag_armor(rid, name):
    lc = name.lower()
    tags = ["Armor"]
    mats = descriptors_for(lc)
    cls = next((ARMOR_CLASS[m] for m in mats if m in ARMOR_CLASS), None)
    if cls:
        tags.append(cls)
    hit = find_first(lc, ARMOR_SLOTS)
    if hit:
        tags.append(hit[1])
    if word("left").search(lc) or word("l").search(lc):
        tags.append("Left")
    elif word("right").search(lc) or word("r").search(lc):
        tags.append("Right")
    tags += mats
    if UNIQUE_RE.search(rid):
        tags.append("Unique")
    return dedup(tags)


def tag_ingredient(rid, name):
    lc = name.lower()
    tags = ["Ingredient"]
    category = None
    for prefix, cat in ING_PREFIX.items():
        if rid.startswith(prefix):
            category = cat
            break
    hit = find_first(lc, ING_RULES)
    if hit:
        if category is None:
            category = hit[1]
        tags.append(category)
        tags.append(hit[2])  # subtype
    elif category:
        tags.append(category)
    for pat, cname in CREATURES:
        if pat.search(lc):
            tags.append(cname)
            break
    if UNIQUE_RE.search(rid):
        tags.append("Unique")
    return dedup(tags)


def tag_misc(rid, name):
    lc = name.lower()
    tags = ["MiscItem"]
    if lc.strip() == "gold":
        return ["MiscItem", "Coin", "Currency"]
    hit = find_first(lc, MISC_CATS)
    tags.append(hit[1] if hit else "Clutter")
    tags += descriptors_for(lc)
    if UNIQUE_RE.search(rid):
        tags.append("Unique")
    return dedup(tags)


TAGGERS = {
    "Weapon": tag_weapon, "Armor": tag_armor,
    "Ingredient": tag_ingredient, "MiscItem": tag_misc,
}


def process(path: Path, rtype: str, check: bool) -> int:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        return 0
    header, body = rows[0], rows[1:]
    tagger = TAGGERS[rtype]
    changed = 0
    for row in body:
        if len(row) < 3:
            row += [""] * (3 - len(row))
        rid, name = row[0], row[1]
        tags = ", ".join(tagger(rid, name))
        if row[2] != tags:
            changed += 1
        row[2] = tags
    if not check:
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh, quoting=csv.QUOTE_ALL, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(body)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--check", action="store_true",
                        help="report rows that would change without writing")
    args = parser.parse_args()

    out_dir = args.root / "_out"
    total = 0
    for path in sorted(out_dir.glob("*.csv")):
        rtype = next((t for t in TARGET_TYPES
                      if path.stem.endswith("_" + t)), None)
        if rtype is None:
            continue
        n = process(path, rtype, args.check)
        total += n
        print(f"{path.name:32} {rtype:10} {n:5d} rows tagged")
    verb = "would change" if args.check else "tagged"
    print(f"\n{total} rows {verb}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
