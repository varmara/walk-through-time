"""Download bridges from OpenStreetMap, so they can be drawn and dated like buildings.

Two kinds of mapping are used:
  - bridge outlines (man_made=bridge), drawn as they are;
  - roads, paths and railways tagged bridge=*, at least MIN_LEN metres long and not already inside an outline,
    widened into a deck of a typical width (footbridges narrow, roads wide).
A separate small query, so the saved building download (and its stamp) is untouched.

Writes work/<city>/bridges.json: [{osm, rings, tags, base}]  base = height of the deck above the ground, m.
"""
import math

from .common import city, http, log, metres, point_in_ring, rnd, save, stitch_rings
from .s00_fetch_osm import OVERPASS

MIN_LEN = 25
WIDTH = {"footway": 4, "path": 3, "cycleway": 4, "pedestrian": 6, "steps": 3, "service": 6, "railway": 9}


def width_of(t):
    if t.get("width"):
        try:
            return max(2.0, min(30.0, float(str(t["width"]).split()[0])))
        except ValueError:
            pass
    if t.get("railway"):
        return WIDTH["railway"]
    return WIDTH.get(t.get("highway"), 12 if t.get("highway") in ("primary", "trunk", "secondary") else 9)


def deck(line, w):
    """A line widened into a polygon w metres wide (square ends, mitred joints)."""
    lat = sum(p[1] for p in line) / len(line)
    kx, ky = 111320 * math.cos(math.radians(lat)), 110540
    pts = [(x * kx, y * ky) for x, y in line]
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(0, i - 1)], pts[min(len(pts) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        ox, oy = -dy / n * w / 2, dx / n * w / 2
        left.append((x + ox, y + oy))
        right.append((x - ox, y - oy))
    ring = left + right[::-1] + [left[0]]
    return rnd([[x / kx, y / ky] for x, y in ring])


def main(city_id):
    c = city(city_id)
    b, poly = c["bbox"], c.get("polygon")
    box = f'({b["s"]},{b["w"]},{b["n"]},{b["e"]})'
    q = (f'[out:json][timeout:180];(way["man_made"="bridge"]{box};relation["man_made"="bridge"]{box};'
         f'way["bridge"]["bridge"!="no"]["highway"]{box};way["bridge"]["bridge"!="no"]["railway"]{box};);out tags geom qt;')
    els = None
    for url in OVERPASS:
        try:
            els = http(url, {"data": q}, tries=2, timeout=240)["elements"]
            break
        except Exception as e:  # noqa: BLE001
            log(f"    bridges via {url.split('/')[2]}: {e}")
    if els is None:
        log("s00 bridges: all Overpass servers failed, no bridges this run")
        save(city_id, "bridges", [])
        return
    inside = (lambda x, y: point_in_ring(x, y, poly)) if poly else (lambda x, y: True)
    outlines, lines = [], []
    for el in els:
        t = el.get("tags", {})
        if t.get("man_made") == "bridge":
            if el["type"] == "way" and el.get("geometry"):
                rings = [[[g["lon"], g["lat"]] for g in el["geometry"]]]
            elif el["type"] == "relation":
                rings = stitch_rings([[[g["lon"], g["lat"]] for g in m["geometry"]] for m in el.get("members", [])
                                      if m.get("role") == "outer" and m.get("geometry")])
            else:
                continue
            rings = [r for r in rings if len(r) >= 4 and r[0] == r[-1]]
            if rings and any(inside(*p) for p in rings[0][::3]):
                outlines.append({"osm": f"{el['type']}/{el['id']}", "rings": [rnd(r) for r in rings], "tags": t, "base": 4})
        elif el["type"] == "way" and el.get("geometry"):
            line = [[g["lon"], g["lat"]] for g in el["geometry"]]
            length = sum(metres(line[i], line[i + 1]) for i in range(len(line) - 1))
            if length >= MIN_LEN and inside(*line[len(line) // 2]):
                lines.append((el, t, line))
    out = list(outlines)
    skipped = 0
    for el, t, line in lines:
        mid = line[len(line) // 2]
        if any(point_in_ring(mid[0], mid[1], o["rings"][0]) for o in outlines):
            skipped += 1      # the outline already draws this bridge; give it the road's name if it has none
            o = next(o for o in outlines if point_in_ring(mid[0], mid[1], o["rings"][0]))
            for k in ("name", "wikidata", "start_date", "bridge:name"):
                if t.get(k) and not o["tags"].get(k):
                    o["tags"][k] = t[k]
            continue
        tags = {k: v for k, v in t.items() if k in ("name", "bridge:name", "wikidata", "start_date", "bridge", "highway", "railway", "heritage")}
        if tags.get("bridge:name"):
            tags["name"] = tags["bridge:name"]
        out.append({"osm": f"way/{el['id']}", "rings": [deck(line, width_of(t))], "tags": tags, "base": 5})
    for o in out:
        if o["tags"].get("bridge:name") and not o["tags"].get("name"):
            o["tags"]["name"] = o["tags"]["bridge:name"]
    save(city_id, "bridges", out)
    log(f"s00 bridges: {len(outlines)} bridge outlines, {len(out) - len(outlines)} more from bridge roads, paths and "
        f"railways ({skipped} already covered by an outline); {sum(1 for o in out if o['tags'].get('name'))} named")
