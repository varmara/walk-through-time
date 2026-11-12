"""Download buildings, roads, water, parks and named places from OpenStreetMap (Overpass API).

The city's area is split into squares of about 2 x 3 km on a fixed grid (the same squares whatever the city's
box), fetched one at a time: public Overpass servers refuse or time out on a single large request. Each square's
answer is saved like any web answer (pipeline/web.py), so a bigger map fetches only its new squares and a refresh
within a month fetches none. What lies outside the city's polygon is dropped afterwards, and elements that cross
square edges are kept once.

Writes work/<city>/osm.json, plus osm.stamp (a fingerprint of the city settings and this script) and
osm.fresh (a marker that this run downloaded new data). Licence: ODbL, © OpenStreetMap contributors.

Downloading takes most of an hour, so GitHub Actions keeps the last download on the `downloads` branch.
`python -m pipeline.run <city> --reuse-downloads` skips this step when work/<city>/osm.json is there and
its stamp still matches, that is when neither the city's area nor this query has changed.
"""
import hashlib
import os
import json
import time
import urllib.parse
from pathlib import Path

from .common import city, log, save, work
from .geo import point_in_ring
from .web import cached, http

OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
TILE_LON, TILE_LAT = 0.03, 0.02


def tiles(b, poly=None):
    """The grid's squares over the box (and touching the polygon, if one is given)."""
    import math
    for j in range(math.floor(b["s"] / TILE_LAT), math.ceil(b["n"] / TILE_LAT)):
        for i in range(math.floor(b["w"] / TILE_LON), math.ceil(b["e"] / TILE_LON)):
            t = {"s": round(j * TILE_LAT, 4), "w": round(i * TILE_LON, 4),
                 "n": round((j + 1) * TILE_LAT, 4), "e": round((i + 1) * TILE_LON, 4)}
            if not poly or touches(t, poly):
                yield t


def touches(t, poly):
    """Whether a square and the polygon overlap: a corner or a point of one inside the other, or a polygon edge
    crossing the square (checked at points along it)."""
    inside = lambda x, y: t["w"] <= x <= t["e"] and t["s"] <= y <= t["n"]
    if any(inside(x, y) for x, y in poly):
        return True
    if any(point_in_ring(x, y, poly) for x in (t["w"], t["e"]) for y in (t["s"], t["n"])):
        return True
    for (x1, y1), (x2, y2) in zip(poly, poly[1:]):
        if any(inside(x1 + (x2 - x1) * k / 20, y1 + (y2 - y1) * k / 20) for k in range(21)):
            return True
    return False


def in_area(el, poly):
    """An element with any point inside the polygon (as Overpass's own poly filter keeps them)."""
    if not poly:
        return True
    if "lat" in el:
        return point_in_ring(el["lon"], el["lat"], poly)
    pts = el.get("geometry") or [p for m in el.get("members", []) for p in (m.get("geometry") or [])]
    if not pts and el.get("bounds"):
        b = el["bounds"]
        pts = [{"lon": (b["minlon"] + b["maxlon"]) / 2, "lat": (b["minlat"] + b["maxlat"]) / 2}]
    return any(point_in_ring(p["lon"], p["lat"], poly) for p in pts[::max(1, len(pts) // 12)] if p)


def query(area):
    return f"""[out:json][timeout:180];(
      way["building"]{area};
      way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|pedestrian|service)$"]{area};
      way["natural"="water"]{area}; way["waterway"~"^(canal|river)$"]{area};
      way["leisure"~"^(park|garden)$"]{area}; way["landuse"="grass"]{area};
      node["name"]["amenity"]{area}; node["name"]["historic"]{area}; node["name"]["tourism"]{area};
    ); out tags geom qt;
    (relation["building"]["type"="multipolygon"]{area}; relation["natural"="water"]{area};); out body geom qt;"""


def cached_tile(area):
    """Whether a square's answer is saved (from any of the servers)."""
    body = urllib.parse.urlencode({"data": query(area)}).encode()
    return any(cached("application/json", url, body) is not None for url in OVERPASS)


def fetch(area):
    # ways and points: their tags and shape; relations (buildings and water drawn as multipolygons, e.g. the
    # Arkwright Building around its courtyard) need "body" too, or Overpass sends them without their members
    q = query(area)
    last = None
    for attempt in range(3):
        for url in OVERPASS:
            try:
                return http(url, {"data": q}, tries=1, timeout=240)["elements"]
            except Exception as e:  # noqa: BLE001 - try the next server
                last = e
                log(f"    {url.split('/')[2]}: {e}")
        time.sleep(30 * (attempt + 1))
    raise RuntimeError(f"All Overpass servers failed: {last}")


def stamp(city_id):
    """Fingerprint of everything that decides what is downloaded: the city's area and this script (not the rest of
    the city's settings, so that adding a council's source does not download OpenStreetMap again)."""
    c = city(city_id)
    h = hashlib.sha256(json.dumps([c.get("polygon"), c.get("bbox")]).encode())
    h.update(Path(__file__).read_bytes())
    return h.hexdigest()[:16]


def reusable(city_id):
    osm, st = work(city_id, "osm"), work(city_id, "osm").with_suffix(".stamp")
    return osm.exists() and st.exists() and st.read_text().strip() == stamp(city_id)


def main(city_id):
    c = city(city_id)
    poly = c.get("polygon")
    elements, seen = [], set()
    ts = list(tiles(c["bbox"], poly))
    saved = 0
    # a first download of a big area can take longer than one build may run: past $WTT_OSM_MINUTES the step stops
    # (each square fetched so far is saved), and the next build carries on from there
    budget = float(os.environ.get("WTT_OSM_MINUTES") or 0) * 60
    t0 = time.time()
    for n, t in enumerate(ts, 1):
        area = f"({t['s']},{t['w']},{t['n']},{t['e']})"
        was = cached_tile(area)
        if not was and budget and time.time() - t0 > budget:
            left = sum(1 for u in ts[n - 1:] if not cached_tile(f"({u['s']},{u['w']},{u['n']},{u['e']})"))
            raise SystemExit(f"s00 OpenStreetMap: stopped after {budget / 60:.0f} minutes with {left} of {len(ts)} "
                             "squares still to fetch; they are saved so far, and the next build carries on")
        got = fetch(area)
        new = 0
        for el in got:
            key = (el["type"], el["id"])
            if key not in seen and in_area(el, poly):
                seen.add(key)
                elements.append(el)
                new += 1
        saved += was
        log(f"s00 OpenStreetMap square {n}/{len(ts)}: {new} new elements{' (saved answer)' if was else ''}")
        if not was:
            time.sleep(3)
    log(f"    {saved} of {len(ts)} squares from saved answers")
    save(city_id, "osm", {"elements": elements})
    work(city_id, "osm").with_suffix(".stamp").write_text(stamp(city_id))
    work(city_id, "osm").with_suffix(".fresh").write_text("1")
    log(f"    {len(elements)} elements in total")
