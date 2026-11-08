"""Download listed buildings and scheduled monuments from Historic England (NHLE).

Writes work/<city>/listed.json (points) and work/<city>/monuments.json (polygons).
Licence: Open Government Licence, © Historic England.
"""
from .common import city, http, log, point_in_ring, save

NHLE = ("https://services-eu1.arcgis.com/ZOdPfBS3aqqDYPUQ/arcgis/rest/services/"
        "National_Heritage_List_for_England_NHLE_v02_VIEW/FeatureServer")
LISTED, SCHEDULED = 0, 6   # layer ids in the NHLE service


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
