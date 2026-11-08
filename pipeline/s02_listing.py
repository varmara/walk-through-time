"""Match Historic England listed-building points to building outlines.

Reads buildings.json and listed.json. Writes listing.json: {building index: [list entries]},
highest grade first.
"""
from .common import building_at, load, log, save

RANK = {"I": 3, "II*": 2, "II": 1}


def main(city_id):
    buildings = load(city_id, "buildings")
    listed = load(city_id, "listed")
    out, missed = {}, 0
    for p in listed:
        i = building_at(buildings, p["x"], p["y"], near=8)
        if i is None:
            missed += 1
            continue
        out.setdefault(str(i), []).append({k: p.get(k) for k in ("ListEntry", "Name", "Grade", "hyperlink")})
    for entries in out.values():
        entries.sort(key=lambda e: -RANK.get(e["Grade"], 0))
    save(city_id, "listing", out)
    log(f"s02 {len(listed) - missed}/{len(listed)} listed points matched to {len(out)} buildings")
