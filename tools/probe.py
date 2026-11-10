from pipeline.common import city, http
from pipeline.s00_fetch_osm import OVERPASS
c = city("nottingham")
poly = '(poly:"' + " ".join(f"{y} {x}" for x, y in c["polygon"]) + '")'
box = "(52.955,-1.156,52.959,-1.149)"
for name, area in [("poly+box", poly + box), ("box", box)]:
    q = f'[out:json][timeout:120];(relation["building"]["type"="multipolygon"]{area};); out tags geom qt;'
    for url in OVERPASS:
        try:
            r = http(url, {"data": q}, tries=1, timeout=200); break
        except Exception as e: print(url, e); r = {"elements": []}
    els = r["elements"]
    print(name, len(els), [(e["id"], e["tags"].get("name"), len(e.get("members", [])), [m.get("role") for m in e.get("members", [])][:4], bool(e.get("members") and e["members"][0].get("geometry"))) for e in els][:8])
