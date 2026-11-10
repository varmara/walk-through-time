"""Download nature conservation areas: Natural England designations and OpenStreetMap nature reserves.

Natural England (Open Government Licence): National Nature Reserves, Local Nature Reserves, Sites of
Special Scientific Interest, and the Ancient Woodland Inventory. OpenStreetMap (ODbL): other areas
tagged leisure=nature_reserve, such as reserves run by wildlife trusts.

Local councils: Local Wildlife Sites (once "Sites of Importance for Nature Conservation"), places of local
importance for wildlife chosen by the county's Local Wildlife Sites partnership, such as the Fairham Brook
corridor between Clifton and Silverdale. Most are not nature reserves and have no legal protection, but are
looked after through the planning system. Nottingham City Council publishes them for the whole county area.

Writes work/<city>/nature.json: GeoJSON features with properties {t: type key, name, source}.
Only areas whose centre lies inside the city's polygon are kept, so large sites just across the boundary
stay out. OpenStreetMap reserves whose centre lies inside a Natural England area are left out as duplicates.
"""
from .common import city, http, log, point_in_ring, save

NE = "https://services.arcgis.com/JJzESW51TqeY9uat/ArcGIS/rest/services/{}/FeatureServer/0/query"
TYPES = [
    # key, Natural England service, title
    ("nnr", "National_Nature_Reserves_England", "National Nature Reserve"),
    ("lnr", "Local_Nature_Reserves_England", "Local Nature Reserve"),
    ("sssi", "SSSI_England", "Site of Special Scientific Interest"),
    ("ancient", "Ancient_Woodland_England", "Ancient woodland"),
]
# per city: council map services with Local Wildlife Sites (key, ArcGIS layer, name field, publisher)
LOCAL = {
    "nottingham": [("lws", "https://maps164.nottinghamcity.gov.uk/server/rest/services/Core_services/Environment/MapServer/7/query",
                    "SITE_NAME", "Nottingham City Council")],
}
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter"]


def name_of(props):
    for k, v in props.items():
        if "NAME" in k.upper() and "ID" not in k.upper() and isinstance(v, str) and v.strip():
            return v.strip().title() if v.isupper() else v.strip()
    return None


def rings_of(geom):
    if not geom:
        return []
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    if geom["type"] == "MultiPolygon":
        return [p[0] for p in geom["coordinates"]]
    return []


def centre(geom):
    pts = [p for r in rings_of(geom) for p in r]
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)) if pts else (0, 0)


def reaches(geom, poly):
    """True if the area's centre (the mean of its outline points) lies inside the city polygon."""
    return point_in_ring(*centre(geom), poly)


def rnd(geom):
    r = lambda ring: [[round(x, 5), round(y, 5)] for x, y in ring]  # noqa: E731
    if geom["type"] == "Polygon":
        return {"type": "Polygon", "coordinates": [r(x) for x in geom["coordinates"]]}
    return {"type": "MultiPolygon", "coordinates": [[r(x) for x in p] for p in geom["coordinates"]]}


def main(city_id):
    c = city(city_id)
    b = c["bbox"]
    poly = c.get("polygon") or [[b["w"], b["s"]], [b["e"], b["s"]], [b["e"], b["n"]], [b["w"], b["n"]], [b["w"], b["s"]]]
    feats = []
    for key, service, title in TYPES:
        try:
            gj = http(NE.format(service), params={
                "where": "1=1", "geometry": f"{b['w']},{b['s']},{b['e']},{b['n']}",
                "geometryType": "esriGeometryEnvelope", "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
                "outFields": "*", "outSR": "4326", "returnGeometry": "true", "geometryPrecision": "5",
                "maxAllowableOffset": "0.00002", "resultRecordCount": "2000", "f": "geojson"})
        except Exception as e:  # noqa: BLE001 - each designation is optional
            log(f"s00 Natural England {title}: failed, continuing without it ({e})")
            continue
        n = 0
        for f in gj.get("features", []):
            if f.get("geometry") and reaches(f["geometry"], poly):
                feats.append({"type": "Feature", "geometry": rnd(f["geometry"]),
                              "properties": {"t": key, "name": name_of(f["properties"]) or title,
                                             "source": "Natural England"}})
                n += 1
        log(f"s00 Natural England {title}: {n} areas")

    q = f"""[out:json][timeout:120];(
      way["leisure"="nature_reserve"]({b['s']},{b['w']},{b['n']},{b['e']});
      relation["leisure"="nature_reserve"]({b['s']},{b['w']},{b['n']},{b['e']});
    ); out tags geom qt;"""
    osm = None
    for url in OVERPASS:
        try:
            osm = http(url, {"data": q}, tries=2, timeout=180)
            break
        except Exception as e:  # noqa: BLE001
            log(f"    {url.split('/')[2]}: {e}")
    named = {f["properties"]["name"].lower() for f in feats}
    n = 0
    for el in (osm or {}).get("elements", []):
        t = el.get("tags", {})
        if el["type"] == "way" and el.get("geometry"):
            rings = [[[g["lon"], g["lat"]] for g in el["geometry"]]]
        elif el["type"] == "relation":
            rings = [[[g["lon"], g["lat"]] for g in m["geometry"]] for m in el.get("members", [])
                     if m.get("role") == "outer" and m.get("geometry")]
        else:
            continue
        rings = [r for r in rings if len(r) > 3 and r[0] == r[-1]]
        if not rings:
            continue
        geom = {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}
        name = t.get("name")
        cx, cy = centre(geom)
        dup = (name and name.lower() in named) or any(point_in_ring(cx, cy, r) for f in feats for r in rings_of(f["geometry"]))
        if dup or not reaches(geom, poly):
            continue   # already covered by a Natural England designation, or outside the city
        feats.append({"type": "Feature", "geometry": rnd(geom),
                      "properties": {"t": "reserve", "name": name or "Nature reserve", "source": "OpenStreetMap"}})
        n += 1
    log(f"s00 OpenStreetMap nature reserves: {n} more areas")

    for key, url, field, publisher in LOCAL.get(city_id, []):
        try:
            gj = http(url, params={
                "where": "1=1", "geometry": f"{b['w']},{b['s']},{b['e']},{b['n']}", "geometryType": "esriGeometryEnvelope",
                "inSR": "4326", "spatialRel": "esriSpatialRelIntersects", "outFields": field, "outSR": "4326",
                "returnGeometry": "true", "geometryPrecision": "5", "maxAllowableOffset": "0.00002", "f": "geojson"})
        except Exception as e:  # noqa: BLE001 - optional
            log(f"s00 {publisher} Local Wildlife Sites: failed, continuing without them ({e})")
            continue
        n = 0
        for f in gj.get("features", []):
            g = f.get("geometry")
            if not g or not rings_of(g) or not reaches(g, poly):
                continue
            name = (f["properties"].get(field) or "").strip()
            cx, cy = centre(g)
            # already drawn as a reserve or a designated site (often the same place under its own name)
            if (any(point_in_ring(cx, cy, r) for e in feats for r in rings_of(e["geometry"]))
                    or (name and any(name.lower() in e["properties"]["name"].lower() for e in feats))):
                continue    # "Holme Pit" is "Holme Pit SSSI", drawn with a slightly different outline
            feats.append({"type": "Feature", "geometry": rnd(g),
                          "properties": {"t": key, "name": name or "Local Wildlife Site", "source": publisher,
                                         "url": url.rsplit("/query", 1)[0],
                                         "credit": f"© {publisher}. Contains Ordnance Survey data © Crown copyright "
                                                   "and database rights."}})
            n += 1
        log(f"s00 {publisher} Local Wildlife Sites: {n} more areas")
    save(city_id, "nature", feats)
