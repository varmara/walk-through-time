"""Choose one construction year per building, keep every other date that disagrees with it.

Candidates:
  OpenStreetMap  start_date (or building:start_date, construction_date) tagged on the outline itself
  Wikipedia      a `year` given in a story (stories/<city>.py); the year must appear in the article (step s04)
  Wikidata       inception (P571) of the item linked to the building

Flags (see common.parse_year): exact (a single year), approx (circa, a decade, a short range),
century (only the century is known). The page draws less precise dates paler.

Choosing: OpenStreetMap and Wikipedia dates come first, the more precise one winning (OpenStreetMap
before Wikipedia when equally precise). Wikidata is used only when neither has a date, however precise
it is: its item often describes an institution (a theatre company, a museum) rather than the building
it occupies, so its exact year must not displace an approximate date for the building itself.

Two dates disagree when their ranges do not overlap: an exact year is a single year, an approximate
date covers ten years either side, a century covers the century. Every date that disagrees with the
chosen one is kept in `alts` and shown on the building's card: sources often describe different
moments (a first church and its rebuilding, a founding and a completion) and the reader can judge.

Area estimates (flag "area"): a home with no date from any of these sources may get the build period that
at least half of the homes in its small area (LSOA) share, from Council Tax records (step s00_fetch_voa).
This is an estimate for the area, not a date for the building: it never displaces a real date, is drawn
palest of all, and the card says so with the share behind it.

Writes dates.json: {building index: {y, f, src, alts?: [{y, f, src}], period?, share?}}.
"""
import re

import math

from .common import APPROX, AREA, CENTURY, EXACT, bbox, centroid, load, log, point_in_ring, save, work

RANK = {EXACT: 3, APPROX: 2, CENTURY: 1, AREA: 0}
HOMES = {"house", "detached", "semidetached_house", "terrace", "residential", "apartments", "bungalow", "flats",
         "semi", "cottage"}
MIN_SHARE = 0.5


def footprint_m2(ring):
    lat = math.radians(sum(p[1] for p in ring) / len(ring))
    kx, ky = 111320 * math.cos(lat), 110540
    a = 0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        a += (x1 * kx) * (y2 * ky) - (x2 * kx) * (y1 * ky)
    return abs(a) / 2


def is_home(b):
    kind = b["tags"].get("building")
    return kind in HOMES or (kind == "yes" and 25 <= footprint_m2(b["rings"][0]) <= 220)
ORDER = {"OpenStreetMap": 0, "Wikipedia": 1, "Wikidata": 2}


def span(y, f):
    if f == EXACT:
        return y, y
    if f == APPROX:
        return y - 10, y + 10
    c = (y - 1) // 100
    return c * 100 + 1, c * 100 + 100


def disagree(a, b):
    a0, a1 = span(a["y"], a["f"])
    b0, b1 = span(b["y"], b["f"])
    return a1 < b0 or b1 < a0


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
    from .common import parse_year
    buildings = load(city_id, "buildings")
    wd = load(city_id, "wikidata")
    listing = load(city_id, "listing")
    story_years = {}
    for e in load(city_id, "curated")["entries"]:
        if e.get("year") and e["b"] is not None:
            story_years.setdefault(e["b"], []).append({"y": e["year"][0], "f": e["year"][1], "src": "Wikipedia"})

    voa = load(city_id, "voa") if work(city_id, "voa").exists() else []
    for a in voa:
        a["bb"] = [bbox(r) for r in a["rings"]]
        top = max(a["periods"], key=lambda p: p[3]) if a["known"] else None
        a["top"] = top if top and top[3] / a["known"] >= MIN_SHARE else None

    def area_estimate(b):
        x, y = centroid(b["rings"][0])
        for a in voa:
            if a["top"] and any(bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3] and point_in_ring(x, y, r)
                                for bb, r in zip(a["bb"], a["rings"])):
                label, start, end, n = a["top"]
                mid = 1880 if start < 1900 else (start + end) // 2
                return {"y": mid, "f": AREA, "src": "Council Tax (area)", "period": label,
                        "share": round(100 * n / a["known"])}
        return None

    out, conflicts, estimated = {}, 0, 0
    for i, b in enumerate(buildings):
        t = b["tags"]
        cands = []
        osm = parse_year(t.get("start_date") or t.get("building:start_date") or t.get("construction_date")
                         or t.get("year_of_construction"))
        if osm:
            cands.append({"y": osm[0], "f": osm[1], "src": "OpenStreetMap"})
        cands += story_years.get(i, [])
        w = wikidata_year(info_for(b, i, wd, listing))
        if w:
            cands.append({"y": w[0], "f": w[1], "src": "Wikidata"})
        if not cands:
            est = area_estimate(b) if voa and is_home(b) else None
            if est:
                out[str(i)] = est
                estimated += 1
            continue
        cands.sort(key=lambda c: (c["src"] == "Wikidata", -RANK[c["f"]], ORDER[c["src"]]))
        best = dict(cands[0])
        alts, seen = [], set()
        for c in cands[1:]:
            key = (c["y"], c["f"], c["src"])
            if key not in seen and disagree(best, c):
                seen.add(key)
                alts.append(c)
        if alts:
            best["alts"] = alts
            conflicts += 1
        out[str(i)] = best
    save(city_id, "dates", out)
    by_flag = {f: sum(1 for d in out.values() if d["f"] == f) for f in RANK}
    log(f"s05 {len(out) - estimated}/{len(buildings)} buildings dated {by_flag}, {conflicts} where sources disagree; "
        f"{estimated} homes given an area estimate from Council Tax records")
