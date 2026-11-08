"""Turn the OpenStreetMap download into buildings, a base map, and named places.

Reads work/<city>/osm.json. Writes:
  buildings.json  [{osm, rings, bb, tags, h}]  one entry per building outline
  base.json       {roads, water, parks}         GeoJSON for the plain base map
  places.json     [{x, y, name, tags, b}]        named points (pubs, museums...), b = building index or null
"""
from .common import bbox, building_at, load, log, rnd, save, stitch_rings


def height_of(t):
    for k in ("height", "building:height"):
        try:
            h = float(str(t.get(k, "")).replace("m", "").strip())
            if 0 < h < 400:
                return round(h, 1)
        except ValueError:
            pass

    def num(k):
        try:
            return float(t.get(k, ""))
        except ValueError:
            return 0

    lv, rl = num("building:levels"), num("roof:levels")
    if lv > 0:
        return round(lv * 3.2 + rl * 1.6 + 1, 1)
    kind = t.get("building")
    if kind in ("house", "detached", "semidetached_house", "terrace", "residential"):
        return 8
    if kind in ("garage", "garages", "shed", "hut", "kiosk", "roof", "carport"):
        return 3
    if kind in ("church", "chapel"):
        return 16
    if kind == "cathedral":
        return 28
    return 10


def feature(kind, coords, props=None):
    # the base map is drawn faintly: five decimals (about a metre) is plenty and keeps the file small
    c = [[round(x, 5), round(y, 5)] for x, y in coords]
    geom = {"type": kind, "coordinates": c if kind == "LineString" else [c]}
    return {"type": "Feature", "properties": props or {}, "geometry": geom}


def main(city_id):
    osm = load(city_id, "osm")
    buildings, roads, water, parks, nodes = [], [], [], [], []
    for el in osm["elements"]:
        t = el.get("tags", {})
        if el["type"] == "node":
            nodes.append({"x": el["lon"], "y": el["lat"], "name": t.get("name"), "tags": t})
        elif el["type"] == "way" and el.get("geometry"):
            c = [[g["lon"], g["lat"]] for g in el["geometry"]]
            if t.get("building"):
                if len(c) >= 4:
                    buildings.append({"osm": f"way/{el['id']}", "rings": [rnd(c)], "tags": t})
            elif t.get("highway"):
                k = "minor" if t["highway"] in ("service", "pedestrian", "residential", "living_street") else "major"
                roads.append(feature("LineString", c, {"k": k}))
            elif t.get("waterway"):
                water.append(feature("LineString", c))
            elif t.get("natural") == "water" and len(c) > 3:
                water.append(feature("Polygon", c))
            elif (t.get("leisure") or t.get("landuse")) and len(c) > 3:
                parks.append(feature("Polygon", c))
        elif el["type"] == "relation" and el.get("members"):
            outers = [[[g["lon"], g["lat"]] for g in m["geometry"]] for m in el["members"]
                      if m.get("role") == "outer" and m.get("geometry")]
            rings = stitch_rings(outers)
            if not rings:
                continue
            if t.get("building"):
                buildings.append({"osm": f"relation/{el['id']}", "rings": [rnd(r) for r in rings], "tags": t})
            elif t.get("natural") == "water":
                water += [feature("Polygon", r) for r in rings]

    for b in buildings:
        b["bb"] = bbox(b["rings"][0])
        b["h"] = height_of(b["tags"])
    for n in nodes:
        n["b"] = building_at(buildings, n["x"], n["y"])

    save(city_id, "buildings", buildings)
    save(city_id, "base", {"roads": roads, "water": water, "parks": parks})
    save(city_id, "places", nodes)
    log(f"s01 {len(buildings)} buildings, {len(nodes)} named places "
        f"({sum(n['b'] is not None for n in nodes)} inside a building)")
