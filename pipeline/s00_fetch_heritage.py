"""Download listed buildings and scheduled monuments from Historic England (NHLE).

Writes work/<city>/listed.json (points), work/<city>/monuments.json (polygons) and
work/<city>/conservation.json (conservation areas, from Historic England's national layer compiled
from local planning authorities; "indicative, not definitive").
Licence: Open Government Licence, © Historic England.
"""
import re

from .common import city, log, save
from .web import http
from .geo import point_in_ring

NHLE = ("https://services-eu1.arcgis.com/ZOdPfBS3aqqDYPUQ/arcgis/rest/services/"
        "National_Heritage_List_for_England_NHLE_v02_VIEW/FeatureServer")
LISTED, SCHEDULED = 0, 6   # layer ids in the NHLE service
CONSERVATION = ("https://services-eu1.arcgis.com/ZOdPfBS3aqqDYPUQ/ArcGIS/rest/services/"
                "Conservation_Areas/FeatureServer/0/query")


def query(layer, b, fields, page=1000):
    """All features in the bounding box, fetched in pages (the service returns at most a few thousand at once)."""
    feats, offset = [], 0
    while True:
        r = http(f"{NHLE}/{layer}/query", params={
            "where": "1=1", "geometry": f"{b['w']},{b['s']},{b['e']},{b['n']}",
            "geometryType": "esriGeometryEnvelope", "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
            "outFields": fields, "outSR": "4326", "returnGeometry": "true",
            "resultOffset": str(offset), "resultRecordCount": str(page), "f": "geojson",
        })
        got = r.get("features", [])
        feats += got
        if len(got) < page and not r.get("exceededTransferLimit") and not r.get("properties", {}).get("exceededTransferLimit"):
            return {"features": feats}
        if not got:
            return {"features": feats}
        offset += len(got)


def main(city_id):
    c = city(city_id)
    b, poly = c["bbox"], c.get("polygon")
    inside = (lambda x, y: point_in_ring(x, y, poly)) if poly else (lambda x, y: True)
    log("s00 Historic England: listed buildings")
    listed = []
    for f in query(LISTED, b, "ListEntry,Name,Grade,hyperlink").get("features", []):
        g = f.get("geometry") or {}
        pts = [g["coordinates"]] if g.get("type") == "Point" else g.get("coordinates", []) if g.get("type") == "MultiPoint" else []
        listed += [{"x": p[0], "y": p[1], **f["properties"]} for p in pts if inside(p[0], p[1])]
    save(city_id, "listed", listed)
    log(f"    {len(listed)} listed building points")

    log("s00 Historic England: scheduled monuments")
    try:
        mons = query(SCHEDULED, b, "ListEntry,Name,hyperlink").get("features", [])
    except Exception as e:  # noqa: BLE001 - optional layer
        log(f"    failed, continuing without: {e}")
        mons = []
    save(city_id, "monuments", mons)
    log(f"    {len(mons)} scheduled monuments")

    log("s00 Historic England: conservation areas")
    areas = []
    try:
        r = http(CONSERVATION, params={
            "where": "1=1", "geometry": f"{b['w']},{b['s']},{b['e']},{b['n']}", "geometryType": "esriGeometryEnvelope",
            "inSR": "4326", "spatialRel": "esriSpatialRelIntersects", "outFields": "NAME,DATE_OF_DE,LPA",
            "outSR": "4326", "returnGeometry": "true", "geometryPrecision": "5", "resultRecordCount": "2000",
            "f": "geojson"})
        for f in r.get("features", []):
            g = f.get("geometry") or {}
            rings = [g["coordinates"][0]] if g.get("type") == "Polygon" else [q[0] for q in g.get("coordinates", [])] if g.get("type") == "MultiPolygon" else []
            pts = [pt for ring in rings for pt in ring]
            if not pts:
                continue
            cx, cy = sum(q[0] for q in pts) / len(pts), sum(q[1] for q in pts) / len(pts)
            if poly and not (point_in_ring(cx, cy, poly) or any(inside(*q) for q in pts[::4])):
                continue
            pr = f.get("properties") or {}
            date = pr.get("DATE_OF_DE")
            if isinstance(date, (int, float)):   # milliseconds since 1970
                import datetime as _dt
                date = _dt.datetime.fromtimestamp(date / 1000, _dt.timezone.utc).strftime("%Y")
            areas.append({"type": "Feature", "geometry": g, "properties": {
                "t": "conservation", "name": (pr.get("NAME") or "Conservation area").strip(),
                "designated": (re.search(r"(1[89]\d\d|20\d\d)", str(date)) or [None])[0] if date else None, "lpa": pr.get("LPA"), "source": "Historic England"}})
    except Exception as e:  # noqa: BLE001 - optional layer
        log(f"    failed, continuing without: {e}")
    save(city_id, "conservation", areas)
    log(f"    {len(areas)} conservation areas")

    # registered parks and gardens: designed landscapes of special historic interest (the Arboretum, the cemeteries).
    # The service's layer numbers are not fixed, so the layer is found by its name.
    log("s00 Historic England: registered parks and gardens")
    parks = []
    try:
        layer = next((L["id"] for L in http(NHLE, params={"f": "json"}).get("layers", [])
                      if re.search(r"park", L.get("name", ""), re.I) and re.search(r"garden", L.get("name", ""), re.I)), None)
        if layer is None:
            raise RuntimeError("no parks and gardens layer in the service")
        for f in query(layer, b, "*").get("features", []):
            g, pr = f.get("geometry") or {}, f.get("properties") or {}
            rings = [g["coordinates"][0]] if g.get("type") == "Polygon" else [q[0] for q in g.get("coordinates", [])] if g.get("type") == "MultiPolygon" else []
            pts = [pt for ring in rings for pt in ring]
            if not pts or (poly and not any(inside(*q) for q in pts[::3])):
                continue
            get = lambda *ks: next((pr[k] for k in ks if pr.get(k) not in (None, "")), None)  # noqa: E731
            parks.append({"type": "Feature", "geometry": g, "properties": {
                "t": "parkgarden", "name": (get("Name", "NAME") or "Registered park or garden").strip(),
                "grade": get("Grade", "GRADE"), "listEntry": get("ListEntry", "LISTENTRY", "List_Entry"),
                "url": get("hyperlink", "Hyperlink", "URL"), "source": "Historic England"}})
    except Exception as e:  # noqa: BLE001 - optional layer
        log(f"    failed, continuing without: {e}")
    save(city_id, "parks", parks)
    log(f"    {len(parks)} registered parks and gardens: {', '.join(p['properties']['name'] for p in parks)}")
