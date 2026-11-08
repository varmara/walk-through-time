"""Download commemorative plaques.

Source: Open Plaques, the community record of plaques (public domain), as republished with locations by
Nottingham City Council ("Commemorative Plaques" layer). Each plaque names its lead subject, the subject's
type (person, place, thing...) and roles, which decide the People group it goes into.
Only Nottingham has such a layer so far; other cities simply get none.

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
    save(city_id, "plaques", out)
    log(f"s00 plaques: {len(out)} in the area (of {len(r.get('features', []))} in the source)")
