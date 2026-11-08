"""Download listed buildings and scheduled monuments from Historic England (NHLE).

Writes work/<city>/listed.json (points) and work/<city>/monuments.json (polygons).
Licence: Open Government Licence, © Historic England.
"""
from .common import city, http, log, save

NHLE = ("https://services-eu1.arcgis.com/ZOdPfBS3aqqDYPUQ/arcgis/rest/services/"
        "National_Heritage_List_for_England_NHLE_v02_VIEW/FeatureServer")
LISTED, SCHEDULED = 0, 6   # layer ids in the NHLE service


def query(layer, b, fields):
    return http(f"{NHLE}/{layer}/query", params={
        "where": "1=1", "geometry": f"{b['w']},{b['s']},{b['e']},{b['n']}",
        "geometryType": "esriGeometryEnvelope", "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
        "outFields": fields, "outSR": "4326", "returnGeometry": "true", "resultRecordCount": "2000", "f": "geojson",
    })


def main(city_id):
    b = city(city_id)["bbox"]
    log("s00 Historic England: listed buildings")
    listed = []
    for f in query(LISTED, b, "ListEntry,Name,Grade,hyperlink").get("features", []):
        g = f.get("geometry") or {}
        pts = [g["coordinates"]] if g.get("type") == "Point" else g.get("coordinates", []) if g.get("type") == "MultiPoint" else []
        listed += [{"x": c[0], "y": c[1], **f["properties"]} for c in pts]
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
