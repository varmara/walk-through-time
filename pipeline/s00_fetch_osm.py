"""Download buildings, roads, water, parks and named places from OpenStreetMap (Overpass API).

The city's area is split into tiles of about 2 x 3 km, fetched one at a time: public Overpass servers
refuse or time out on a single large request. Each tile is clipped to the city polygon, and elements
that cross tile edges are kept once.

Writes work/<city>/osm.json, plus osm.stamp (a fingerprint of the city settings and this script) and
osm.fresh (a marker that this run downloaded new data). Licence: ODbL, © OpenStreetMap contributors.

Downloading takes most of an hour, so GitHub Actions keeps the last download on the `downloads` branch.
`python -m pipeline.run <city> --reuse-downloads` skips this step when work/<city>/osm.json is there and
its stamp still matches, that is when neither the city's area nor this query has changed.
"""
import hashlib
import time
from pathlib import Path

from .common import city, http, log, save, work

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


def stamp(city_id):
    """Fingerprint of everything that decides what is downloaded."""
    h = hashlib.sha256(Path(f"cities/{city_id}.json").read_bytes())
    h.update(Path(__file__).read_bytes())
    return h.hexdigest()[:16]


def reusable(city_id):
    osm, st = work(city_id, "osm"), work(city_id, "osm").with_suffix(".stamp")
    return osm.exists() and st.exists() and st.read_text().strip() == stamp(city_id)


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
    work(city_id, "osm").with_suffix(".stamp").write_text(stamp(city_id))
    work(city_id, "osm").with_suffix(".fresh").write_text("1")
    log(f"    {len(elements)} elements in total")
