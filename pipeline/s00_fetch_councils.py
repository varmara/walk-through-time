"""Download the boundaries of the councils whose land the map covers, and their local heritage lists.

Councils: Local Authority District boundaries from the Office for National Statistics (Open Government Licence;
contains OS data © Crown copyright and database right), generalised to 20 m. The city's settings list the
councils it expects (cities/<city>.json, "councils", by ONS code); a council found in the area but not listed is
reported, so a wider map does not quietly leave one out. Each building gets its council (s07), so a card can say
whose planning rules apply, and each council's own sources (sources.* in the settings) say whose data it is.

Local heritage lists ("local lists"): buildings and places a council protects locally, which are not nationally
listed (sources.localList). Only the councils that publish one as map data are fetched; the rest have none here.

Writes work/<city>/councils.json: [{code, name, geometry}] and work/<city>/locallist.json: GeoJSON features with
{name, council, status}.
"""
from .common import city, http, log, save
from .s00_fetch_nature import reaches, rings_of, rnd

# tried in order: ONS republishes the boundaries every year, under a new name
ONS = ["https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/{}/FeatureServer/0/query".format(n) for n in (
    "Local_Authority_Districts_May_2024_Boundaries_UK_BGC",
    "Local_Authority_Districts_May_2023_UK_BGC_V2",
    "Local_Authority_Districts_May_2022_UK_BGC_V3",
    "Local_Authority_Districts_May_2021_UK_BGC_2022",
)]


def arcgis(url, b, fields="*"):
    return http(url, params={
        "where": "1=1", "geometry": f"{b['w']},{b['s']},{b['e']},{b['n']}", "geometryType": "esriGeometryEnvelope",
        "inSR": "4326", "spatialRel": "esriSpatialRelIntersects", "outFields": fields, "outSR": "4326",
        "returnGeometry": "true", "geometryPrecision": "5", "maxAllowableOffset": "0.0001", "f": "geojson"})


def councils(c):
    b, known = c["bbox"], {k: v for k, v in c.get("councils", {}).items() if not k.startswith("_")}
    for url in ONS:
        try:
            gj = arcgis(url, b)
        except Exception as e:  # noqa: BLE001 - try the next year's
            log(f"    ONS {url.split('/services/')[1].split('/')[0]}: {e}")
            continue
        feats = gj.get("features") or []
        if not feats:
            continue
        out = []
        for f in feats:
            pr = f["properties"]
            code = next((v for k, v in pr.items() if k.upper().endswith("CD") and isinstance(v, str)), None)
            name = next((v for k, v in pr.items() if k.upper().endswith("NM") and isinstance(v, str)), None)
            if not code or not f.get("geometry") or not rings_of(f["geometry"]):
                continue
            out.append({"code": code, "name": known.get(code) or name, "geometry": rnd(f["geometry"])})
        missing = [f"{o['name']} ({o['code']})" for o in out if o["code"] not in known]
        log(f"s00 councils: {', '.join(o['name'] for o in out)}"
            + (f"; not in the city's settings: {', '.join(missing)}" if missing else ""))
        return out
    log("s00 councils: no boundaries (ONS unreachable); buildings get no council")
    return []


def local_lists(c):
    b, poly = c["bbox"], c.get("polygon")
    feats = []
    for src in c.get("sources", {}).get("localList", []):
        try:
            gj = arcgis(src["url"] + "/query", b)
        except Exception as e:  # noqa: BLE001 - optional
            log(f"s00 {src.get('title') or src['publisher']}: failed, continuing without it ({e})")
            continue
        n, seen = 0, {}
        for f in gj.get("features", []):
            g, pr = f.get("geometry"), f.get("properties") or {}
            status = str(pr.get("STATUS") or "").strip()
            seen[status] = seen.get(status, 0) + 1
            if not g or not rings_of(g) or (poly and not reaches(g, poly)):
                continue
            if status and not status.isdigit() and "approv" not in status.lower():
                continue          # proposed, or turned down
            name = next((str(pr[k]).strip() for k in ("DESC_", "NAME", "BUILDING_NAME", "SITE_NAME")
                         if pr.get(k) and str(pr[k]).strip()), None)
            feats.append({"type": "Feature", "geometry": rnd(g),
                          "properties": {"name": name, "council": src.get("council"), "source": src["publisher"]}})
            n += 1
        log(f"s00 {src.get('title') or src['publisher']}: {n} entries in the area (statuses: {seen})")
    return feats


def main(city_id):
    c = city(city_id)
    save(city_id, "councils", councils(c))
    save(city_id, "locallist", local_lists(c))
