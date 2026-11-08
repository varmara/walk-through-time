"""Choose one construction year per building, with a flag for how precise it is.

Candidates:
  OpenStreetMap  start_date (or building:start_date, construction_date) on the building outline itself
  Wikidata       inception (P571) of the item linked to the building

Flags (see common.parse_year): exact (a single year), approx (circa, a decade, a short range),
century (only the century is known). The page draws less precise dates paler.

Order of trust: an exact date beats an approximate one, which beats a century. Between two dates
of the same precision, OpenStreetMap wins: its date is tagged on this outline, while a Wikidata
item can describe an older institution or site (a castle's founding rather than the building
standing on the rock today). When the two disagree by more than 25 years, the
other date is kept as `alt` and shown on the building's card.

Writes dates.json: {building index: {y, f, src, alt?}}.
"""
import re

from .common import APPROX, CENTURY, EXACT, load, log, parse_year, save

RANK = {EXACT: 3, APPROX: 2, CENTURY: 1}
DISAGREE = 25


def wikidata_year(info):
    if not info or not info.get("inception"):
        return None
    m = re.match(r"^([+-]?\d+)-", info["inception"])
    if not m:
        return None
    y, p = int(m[1]), info.get("prec") or 0
    if p >= 9:
        return y, EXACT
    if p == 8:
        return y + 5, APPROX
    if p == 7:
        return (-(-y // 100) - 1) * 100 + 50, CENTURY
    return None


def info_for(b, i, wd, listing):
    t = b["tags"]
    if t.get("wikidata") in wd:
        return wd[t["wikidata"]]
    for e in listing.get(str(i), []):
        if f"nhle:{e['ListEntry']}" in wd:
            return wd[f"nhle:{e['ListEntry']}"]
    return None


def main(city_id):
    buildings = load(city_id, "buildings")
    wd = load(city_id, "wikidata")
    listing = load(city_id, "listing")
    out, conflicts = {}, 0
    for i, b in enumerate(buildings):
        t = b["tags"]
        cands = []
        osm = parse_year(t.get("start_date") or t.get("building:start_date") or t.get("construction_date")
                         or t.get("year_of_construction"))
        if osm:
            cands.append({"y": osm[0], "f": osm[1], "src": "OpenStreetMap", "order": 0})
        w = wikidata_year(info_for(b, i, wd, listing))
        if w:
            cands.append({"y": w[0], "f": w[1], "src": "Wikidata", "order": 1})
        if not cands:
            continue
        cands.sort(key=lambda c: (-RANK[c["f"]], c["order"]))
        best = {k: cands[0][k] for k in ("y", "f", "src")}
        other = next((c for c in cands[1:] if abs(c["y"] - best["y"]) > DISAGREE), None)
        if other:
            best["alt"] = {k: other[k] for k in ("y", "f", "src")}
            conflicts += 1
        out[str(i)] = best
    save(city_id, "dates", out)
    by_flag = {f: sum(1 for d in out.values() if d["f"] == f) for f in RANK}
    log(f"s04 {len(out)}/{len(buildings)} buildings dated {by_flag}, {conflicts} where sources disagree")
