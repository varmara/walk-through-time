"""What each building is called: one place for every naming rule, so the card, the summary, the share page and the
checks in tests/ all see the same names.

For each building (rules in names.py: building_name, other_names, landmark, same_place, marker):
  name    what the building was: a hand-chosen name (stories/<city>/names.md), a story's place name, its own name
          in OpenStreetMap, Historic England's, Wikidata's, an old name, a named place inside it
  today   who or what uses it now, when that is not its name (the card's Today row)
  aka     its other names, oldest first where known
  full    the title for landmarks, what it was then what it is: 'Shire Hall · National Justice Museum'
          (stories/<city>/titles.md sets it by hand where the rule gets it wrong)
  where   for a building with no name: its address, or the named street nearest it

Reads buildings, listing, wikidata, curated, layers, places and base. Writes names.json: {building index: {...}}.
"""
import re

from .common import load, log, save
from .geo import centroid, metres
from .names import BUILDINGISH, LANDMARK, building_name, house_numbers, landmark, marker, other_names, same_place
from .s05_dates import info_for

NOT_A_BUILDING = re.compile(r"^(railings|walls?|gates?|gate piers|steps|boundary)\b", re.I)


def full_title(name, today, aka, tags_list):
    """What it was, then what it is, for landmarks: 'Shire Hall · National Justice Museum'; a station known by
    its modern name shows its old one first: 'Midland Railway Station · Nottingham station'."""
    if not name or re.match(r"^\d", name):        # an address and its occupier: the Today row says it
        return None
    if today and landmark(tags_list, today) and not same_place(name, today):
        return f"{name} · {today}"
    if not today and aka and landmark(tags_list, name):
        old = [a for a in aka if (BUILDINGISH.search(a) or LANDMARK.search(a)) and not re.search(r"\bformer\b", a, re.I)]
        if old and not same_place(old[0], name):
            return f"{old[0]} · {name}"
    return None


def streets(base):
    """Named roads on a grid, for where()."""
    grid = {}
    for r in base["roads"]:
        n = r["properties"].get("n")
        if n:
            for x, y in r["geometry"]["coordinates"]:
                grid.setdefault((round(x * 2000), round(y * 3000)), []).append((x, y, n))
    return grid


def where(t, xy, grid):
    """Where a building with no name is: its address, or the named street within 60 m of it."""
    if t.get("addr:housenumber") and t.get("addr:street"):
        return f"{house_numbers(t['addr:housenumber'])} {t['addr:street']}"
    if t.get("addr:street"):
        return t["addr:street"]
    gx, gy, best = round(xy[0] * 2000), round(xy[1] * 3000), None
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for x, y, n in grid.get((gx + dx, gy + dy), []):
                d = metres(xy, [x, y])
                if d <= 60 and (best is None or d < best[0]):
                    best = (d, n)
    return best and best[1]


def main(city_id):
    buildings = load(city_id, "buildings")
    listing = load(city_id, "listing")
    wd = load(city_id, "wikidata")
    lay = load(city_id, "layers")
    cur = load(city_id, "curated")
    hand, titles = cur.get("names", {}), cur.get("titles", {})
    story_name = {}
    for e in cur["entries"]:
        # a person's or a fact's name, or an event's (names: no), is not the building's
        if e.get("layer") not in ("people", "facts") and e.get("names", True):
            story_name.setdefault(str(e["b"]), e["name"])
    fallback = dict(lay.get("names", {}))           # plaque addresses
    inside, named = {}, {}
    for pl in load(city_id, "places"):
        if pl["b"] is None:
            continue
        inside.setdefault(str(pl["b"]), []).append(pl["tags"])
        if pl["name"] and not marker(pl["tags"]):
            named.setdefault(str(pl["b"]), set()).add(pl["name"])
    # a named place inside names the building only when it is the only one: a parade of shops is not called after
    # one of them (a tutoring centre's name on a building with a restaurant too)
    for k, ns in named.items():
        if len(ns) == 1:
            fallback.setdefault(k, next(iter(ns)))
    grid = streets(load(city_id, "base"))

    out, how = {}, {"hand": 0, "story": 0, "named": 0, "full": 0, "where": 0}
    for i, b in enumerate(buildings):
        t, k = b["tags"], str(i)
        best = (listing.get(k) or [None])[0] or {}
        info = info_for(b, i, wd, listing) or {}
        listed_as = best.get("Name")
        name, today = building_name(t, hand.get(b["osm"]) or story_name.get(k), info.get("label"), listed_as, fallback.get(k))
        if not name and listed_as and not NOT_A_BUILDING.match(listed_as):
            name = listed_as                          # Historic England's words, untidied ("1, 3 AND 5 HIGH PAVEMENT")
        aka = other_names(t, name, today, info.get("label"), listed_as)
        n = {"name": name, "today": today, "aka": aka,
             "full": titles.get(b["osm"]) or full_title(name, today, aka, [t] + inside.get(k, [])),
             "where": None if name else where(t, centroid(b["rings"][0]), grid)}
        n = {kk: v for kk, v in n.items() if v}
        if n:
            out[k] = n
        how["hand"] += b["osm"] in hand
        how["story"] += k in story_name and b["osm"] not in hand
        how["named"] += bool(name)
        how["full"] += "full" in n
        how["where"] += "where" in n
    save(city_id, "names", out)
    log(f"s06 names: {how['named']} buildings named ({how['hand']} by hand, {how['story']} from stories), "
        f"{how['full']} with a then-and-now title, {how['where']} titled by address or street")
