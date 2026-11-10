from pipeline.common import city, http
from pipeline.s00_fetch_nature import centre
c = city("nottingham"); b = c["bbox"]
U = "https://maps164.nottinghamcity.gov.uk/server/rest/services/Core_services/Environment/MapServer/{}/query"
for lid in (7, 8, 9, 40):
    try:
        gj = http(U.format(lid), params={"where": "1=1", "geometry": f"{b['w']},{b['s']},{b['e']},{b['n']}",
            "geometryType": "esriGeometryEnvelope", "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*", "outSR": "4326", "returnGeometry": "true", "geometryPrecision": "5", "f": "geojson"})
    except Exception as e:
        print(lid, "failed", e); continue
    fs = gj.get("features", [])
    print("== layer", lid, len(fs))
    for f in fs:
        x, y = centre(f["geometry"]) if f.get("geometry") else (0, 0)
        print(lid, round(x, 4), round(y, 4), {k: v for k, v in f["properties"].items() if v and k not in ("OBJECTID", "SHAPE", "Shape_Area", "Shape_Length", "SHAPE.STArea()", "SHAPE.STLength()")})
r = http("https://maps164.nottinghamcity.gov.uk/server/rest/services/Core_services/Environment/MapServer/7", params={"f": "json"})
print("LWS layer:", {k: r.get(k) for k in ("name", "description", "copyrightText", "maxRecordCount")})
