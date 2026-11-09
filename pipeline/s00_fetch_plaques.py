"""Download commemorative plaques.

Source: Open Plaques, the community record of plaques (public domain), as republished with locations by
Nottingham City Council ("Commemorative Plaques" layer). Each plaque names its lead subject, the subject's
type (person, place, thing...) and roles, which decide the People group it goes into.
Only Nottingham has such a layer so far; other cities simply get none. Places the council layer does not
cover (West Bridgford is in Rushcliffe, not the city) come from plaques mapped in OpenStreetMap (ODbL),
many of them linked to Open Plaques by an openplaques:id tag.

Writes work/<city>/plaques.json: [{x, y, title, inscription, address, year, photo, colour, org,
subject, type, roles, primary}].
"""
from .common import city, http, log, point_in_ring, save

SOURCES = {
    "nottingham": "https://maps164.nottinghamcity.gov.uk/server/rest/services/Core_services/Housing_and_Property/MapServer/34/query",
}
FIELDS = {"PLAQUE_ID": "id", "TITLE": "title", "INSCRIPTION": "inscription", "ADDRESS": "address", "YEAR_ERECTED": "year",
          "PHOTOGRAPH": "photo", "COLOUR": "colour", "ORGANISATION": "org", "LEAD_SUBJECT_NAME": "subject",
          "LEAD_SUBJECT_TYPE": "type", "LEAD_SUBJECT_ROLES": "roles", "LEAD_SUBJECT_PRIMARY_ROLE": "primary"}


def main(city_id):
    url = SOURCES.get(city_id)
    if not url:
        save(city_id, "plaques", [])
        return
    c = city(city_id)
    poly = c.get("polygon")
    try:
        r = http(url, params={"where": "1=1", "outFields": ",".join(FIELDS), "outSR": "4326",
                              "returnGeometry": "true", "f": "json"})
    except Exception as e:  # noqa: BLE001 - plaques are optional
        log(f"s00 plaques: failed, continuing without them ({e})")
        save(city_id, "plaques", [])
        return
    out = []
    for f in r.get("features", []):
        g = f.get("geometry") or {}
        x, y = g.get("x"), g.get("y")
        if x is None or (poly and not point_in_ring(x, y, poly)):
            continue
        a = f.get("attributes", {})
        p = {"x": x, "y": y}
        for k, v in FIELDS.items():
            val = a.get(k)
            p[v] = val.strip() if isinstance(val, str) else val
        out.append(p)
    log(f"s00 plaques: {len(out)} in the area from the council layer (of {len(r.get('features', []))})")
    out += osm_plaques(city_id, c["bbox"], poly, out)
    save(city_id, "plaques", out)


def osm_plaques(city_id, b, poly, have):
    """Plaques mapped in OpenStreetMap (memorial=plaque / blue_plaque), skipping any within 15 m of one we have.
    One small query for plaque nodes only; it does not touch the saved building download."""
    from .common import metres
    from .s00_fetch_osm import OVERPASS
    q = (f'[out:json][timeout:120];(node["memorial"~"^(plaque|blue_plaque)$"]({b["s"]},{b["w"]},{b["n"]},{b["e"]});'
         f'node["openplaques:id"]({b["s"]},{b["w"]},{b["n"]},{b["e"]}););out;')
    data = None
    for url in OVERPASS:
        try:
            data = http(url, data={"data": q}, tries=2, timeout=180)
            break
        except Exception as e:  # noqa: BLE001
            log(f"    OSM plaques via {url.split('/')[2]}: {e}")
    if data is None:
        return []
    extra = []
    for el in data.get("elements", []):
        x, y, t = el.get("lon"), el.get("lat"), el.get("tags", {})
        if x is None or (poly and not point_in_ring(x, y, poly)):
            continue
        if any(metres([x, y], [h["x"], h["y"]]) < 15 for h in have + extra):
            continue
        text = t.get("inscription") or t.get("description")
        # Only plaques that are recorded by Open Plaques or name their subject in Wikidata: OpenStreetMap also maps
        # private memorials, tree plantings and opening stones, which do not belong in a history map.
        if not (text or t.get("name")) or not (t.get("openplaques:id") or t.get("subject:wikidata")):
            continue
        extra.append({"x": x, "y": y, "id": t.get("openplaques:id"), "title": t.get("name"), "inscription": text,
                      "address": None, "year": (t.get("start_date") or "")[:4] or None, "photo": None,
                      "colour": t.get("colour"), "org": t.get("operator"),
                      "subject": t.get("subject") or t.get("subject:name"), "type": "person" if (t.get("subject:wikidata") or t.get("subject")) else "thing",
                      "roles": None, "primary": None, "osm": el["id"]})
    log(f"s00 plaques: {len(extra)} more from OpenStreetMap (of {len(data.get('elements', []))} plaque nodes)")
    return extra
