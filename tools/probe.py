import json
from pipeline import s00_fetch_plaques
from pipeline.common import city, load, point_in_ring
s00_fetch_plaques.main("nottingham")
poly = city("nottingham")["polygon"]
for p in load("nottingham", "plaques"):
    print("PQ", json.dumps({k: p.get(k) for k in ("subject", "type", "roles", "primary", "year", "org", "qid", "osm")}),
          "IN" if point_in_ring(p["x"], p["y"], poly) else "OUT", round(p["x"], 5), round(p["y"], 5), "::", (p.get("inscription") or p.get("title") or "")[:150].replace("\n", " "))
