"""Download buildings, roads, water, parks and named places from OpenStreetMap (Overpass API).

The city's area is split into tiles of about 2 x 3 km, fetched one at a time: public Overpass servers
refuse or time out on a single large request. Each tile is clipped to the city polygon, and elements
that cross tile edges are kept once.

Writes work/<city>/osm.json. Licence: ODbL, © OpenStreetMap contributors.
"""
import time

from .common import city, http, log, save

OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
TILE_LON, TILE_LAT = 0.03, 0.02


def tiles(b):
    y = b["s"]
    while y < b["n"]:
        x = b["w"]
        while x < b["e"]:
            yield {"s": y, "w": x, "n": min(y + TILE_LAT, b["n"]), "e": min(x + TILE_LON, b["e"])}
            x += TILE_LON
        y += TILE_LAT


def fetch(area):
    q = f"""[out:json][timeout:180];(
      way["building"]{area}; relation["building"]["type"="multipolygon"]{area};
      way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|pedestrian|service)$"]{area};
      way["natural"="water"]{area}; way["waterway"~"^(canal|river)$"]{area}; relation["natural"="water"]{area};
      way["leisure"~"^(park|garden)$"]{area}; way["landuse"="grass"]{area};
      node["name"]["amenity"]{area}; node["name"]["historic"]{area}; node["name"]["tourism"]{area};
    ); out tags geom qt;"""
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


def main(city_id):
    c = city(city_id)
    poly = ('(poly:"' + " ".join(f"{y} {x}" for x, y in c["polygon"]) + '")') if c.get("polygon") else ""
    elements, seen = [], set()
    ts = list(tiles(c["bbox"]))
    for n, t in enumerate(ts, 1):
        area = poly + f"({t['s']},{t['w']},{t['n']},{t['e']})"
        got = fetch(area)
        new = 0
        for el in got:
            key = (el["type"], el["id"])
            if key not in seen:
                seen.add(key)
                elements.append(el)
                new += 1
        log(f"s00 OpenStreetMap tile {n}/{len(ts)}: {new} new elements")
        time.sleep(3)
    save(city_id, "osm", {"elements": elements})
    log(f"    {len(elements)} elements in total")
