from pipeline.common import http
from pipeline.s00_fetch_osm import OVERPASS
q = """[out:json][timeout:60];(way(around:60,52.95722,-1.15222)["building"];relation(around:60,52.95722,-1.15222)["building"];
way(around:60,52.95722,-1.15222)["name"~"Arkwright"];relation(around:120,52.95722,-1.15222)["name"~"Arkwright"];);out tags center;"""
for url in OVERPASS:
    try:
        r = http(url, {"data": q}, tries=2); break
    except Exception as e: print(url, e)
for el in r["elements"]:
    print(el["type"], el["id"], el.get("center"), {k: v for k, v in el["tags"].items() if k in ("name", "building", "type", "building:part", "amenity")})
