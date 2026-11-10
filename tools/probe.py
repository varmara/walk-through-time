from pipeline.common import city, http, point_in_ring
from pipeline.s00_fetch_nature import OVERPASS, centre, reaches
c = city("nottingham"); b = c["bbox"]; poly = c["polygon"]
print("polygon", poly)
q = f"""[out:json][timeout:120];(
  nwr["leisure"="nature_reserve"]({b['s']},{b['w']},{b['n']},{b['e']});
  nwr["boundary"="protected_area"]({b['s']},{b['w']},{b['n']},{b['e']});
  nwr["designation"]({b['s']},{b['w']},{b['n']},{b['e']});
  nwr["name"~"Fairham",i]({b['s']},{b['w']},{b['n']},{b['e']});
); out tags center qt;"""
for url in OVERPASS:
    try:
        r = http(url, {"data": q}, tries=2, timeout=180); break
    except Exception as e: print(url, e)
for el in r["elements"]:
    ce = el.get("center") or {"lon": el.get("lon"), "lat": el.get("lat")}
    inside = ce["lon"] is not None and point_in_ring(ce["lon"], ce["lat"], poly)
    print(el["type"], el["id"], round(ce["lon"] or 0, 4), round(ce["lat"] or 0, 4), "inside" if inside else "OUT", {k: v for k, v in el["tags"].items() if k in ("name", "leisure", "boundary", "designation", "protect_class", "natural", "landuse", "operator", "protection_title")})
