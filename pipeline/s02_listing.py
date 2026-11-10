"""Match Historic England listed-building points to building outlines.

Historic England's points are not always on their building: in a street of listed buildings a point can fall
inside the next one (the Bell Inn carried the listing of Exchange House next door). So, in order:
  1. an outline that names the list entry itself in OpenStreetMap (ref:GB:nhle);
  2. an outline within NEAR_NAME metres whose OpenStreetMap name, or a named place inside it, has the listing's
     own name ("THE BELL INN" -> the outline named "The Bell Inn");
  3. the outline the point falls in (or within 8 m of).
On an outline with several entries, the one that names it comes first, then the highest grade.

Reads buildings.json, listed.json and places.json. Writes listing.json: {building index: [list entries]}.
"""
import re

from .common import building_at, centroid, load, log, metres, save, tidy_listing

RANK = {"I": 3, "II*": 2, "II": 1}
NEAR_NAME = 40
PLAIN = {"the", "and", "of", "at", "to", "on", "in", "for", "st", "saint", "nottingham", "house", "building",
         "buildings", "former", "old", "attached", "with", "railings", "walls", "wall", "numbers", "number"}


def words(s):
    s = re.sub(r"['’]", "", (s or "").lower())
    return {w.rstrip("s") for w in re.findall(r"[a-z]{3,}", s) if w not in PLAIN}


def main(city_id):
    buildings = load(city_id, "buildings")
    listed = load(city_id, "listed")
    places = load(city_id, "places")
    names = {}          # outline -> the names it goes by in OpenStreetMap
    for i, b in enumerate(buildings):
        if b["tags"].get("name"):
            names.setdefault(i, set()).update(words(b["tags"]["name"]))
    for p in places:
        if p["b"] is not None and p.get("name"):
            names.setdefault(p["b"], set()).update(words(p["name"]))
    by_nhle = {}
    for i, b in enumerate(buildings):
        for n in re.findall(r"\d{7}", b["tags"].get("ref:GB:nhle", "") + ";" + b["tags"].get("heritage:ref", "")):
            by_nhle.setdefault(n, i)
    grid = {}
    for i in names:
        x, y = centroid(buildings[i]["rings"][0])
        grid.setdefault((round(x * 200), round(y * 300)), []).append((i, x, y))

    out, missed, how = {}, 0, {"nhle": 0, "name": 0, "point": 0}
    for p in listed:
        n = str(p.get("ListEntry"))
        i = by_nhle.get(n)
        if i is not None:
            how["nhle"] += 1
        else:
            own = words(tidy_listing(p.get("Name")) or "")
            best = None
            if own:
                gx, gy = round(p["x"] * 200), round(p["y"] * 300)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for j, x, y in grid.get((gx + dx, gy + dy), []):
                            common = own & names[j]
                            if common and len(common) * 2 >= len(own):
                                d = metres([p["x"], p["y"]], [x, y])
                                if d <= NEAR_NAME and (best is None or d < best[0]):
                                    best = (d, j)
            if best:
                i = best[1]
                how["name"] += 1
            else:
                i = building_at(buildings, p["x"], p["y"], near=8)
                if i is not None:
                    how["point"] += 1
        if i is None:
            missed += 1
            continue
        out.setdefault(str(i), []).append({k: p.get(k) for k in ("ListEntry", "Name", "Grade", "hyperlink")})
    for k, entries in out.items():
        mine = names.get(int(k), set())
        entries.sort(key=lambda e: (-bool(words(tidy_listing(e["Name"]) or "") & mine), -RANK.get(e["Grade"], 0)))
    save(city_id, "listing", out)
    log(f"s02 {len(listed) - missed}/{len(listed)} listed points matched to {len(out)} buildings "
        f"({how['nhle']} by list entry number in OpenStreetMap, {how['name']} by name nearby, {how['point']} by point)")
