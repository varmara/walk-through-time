"""Download buildings, roads, water, parks and named places from OpenStreetMap (Overpass API).

Writes work/<city>/osm.json. Licence: ODbL, © OpenStreetMap contributors.
"""
from .common import city, http, log, save

OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def main(city_id):
    c = city(city_id)
    if c.get("polygon"):   # Overpass wants "lat lon lat lon ..."
        bb = 'poly:"' + " ".join(f"{y} {x}" for x, y in c["polygon"]) + '"'
    else:
        b = c["bbox"]
        bb = f"{b['s']},{b['w']},{b['n']},{b['e']}"
    q = f"""[out:json][timeout:300][maxsize:1073741824];(
      way["building"]({bb}); relation["building"]["type"="multipolygon"]({bb});
      way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|pedestrian|service)$"]({bb});
      way["natural"="water"]({bb}); way["waterway"~"^(canal|river)$"]({bb}); relation["natural"="water"]({bb});
      way["leisure"~"^(park|garden)$"]({bb}); way["landuse"="grass"]({bb});
      node["name"]["amenity"]({bb}); node["name"]["historic"]({bb}); node["name"]["tourism"]({bb});
    ); out tags geom qt;"""
    last = None
    for url in OVERPASS:
        try:
            log(f"s00 OpenStreetMap: {url}")
            osm = http(url, {"data": q}, tries=2)
            save(city_id, "osm", osm)
            log(f"    {len(osm['elements'])} elements")
            return
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"All Overpass servers failed: {last}")
