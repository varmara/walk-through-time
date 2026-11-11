"""Download Mapping Museums: every museum open in the UK at some time from 1960 to 2020, including the small ones
and those that have closed since, with the years they opened and closed.

Mapping Museums Data, September 2021. Birkbeck, University of London; Poulovassilis, Candlin, Ballatore, Katerinchuk,
Larkin, Larson and Liebenrood. https://doi.org/10.18743/DATA.00171. Licence: Creative Commons Attribution 4.0.

Years are given as a range when the exact year is not known ("1960:1975"); a museum still open has 9999 as its
closing year. Locations are the museum's address, so a point can stand a little off its building.

Writes work/<city>/museums.json: [{x, y, name, opened, closed, subject, governance, accreditation, size}].
"""
import csv
import io

from .common import city, log, save
from .geo import point_in_ring
from .web import http_bytes

CSV = "https://researchdata.bbk.ac.uk/id/eprint/171/1/MappingMuseumsData2021_09_30.csv"
DATASET = "https://doi.org/10.18743/DATA.00171"


def years(v):
    """'1972:1972' -> '1972'; '1960:1975' -> 'between 1960 and 1975'; 9999 (still open) -> None."""
    v = (v or "").strip()
    if not v or v.startswith("9999"):
        return None
    a, _, b = v.partition(":")
    b = b or a
    return a if a == b else f"between {a} and {b}"


def column(fields, *words):
    """The first column whose name has every word (case ignored), e.g. column(f, 'year', 'opened')."""
    return next((f for f in fields if all(w in f.lower() for w in words)), None)


def main(city_id):
    c = city(city_id)
    b, poly = c["bbox"], c.get("polygon")
    try:
        raw = http_bytes(CSV).decode("utf-8-sig", "replace")
    except Exception as e:  # noqa: BLE001 - optional: the map works without it
        log(f"s00 Mapping Museums: failed, continuing without it ({e})")
        save(city_id, "museums", [])
        return
    rows = list(csv.DictReader(io.StringIO(raw)))
    f = list(rows[0].keys()) if rows else []
    col = {"name": column(f, "name"), "lat": column(f, "lat"), "lon": column(f, "lon"),
           "opened": column(f, "year", "open"), "closed": column(f, "year", "clos"), "subject": column(f, "subject"),
           "governance": column(f, "governance"), "accreditation": column(f, "accredit"), "size": column(f, "size")}
    if not (col["name"] and col["lat"] and col["lon"]):
        log(f"s00 Mapping Museums: no name or coordinates among the columns ({f[:20]}); skipped")
        save(city_id, "museums", [])
        return
    out = []
    for r in rows:
        try:
            x, y = float(r[col["lon"]]), float(r[col["lat"]])
        except (TypeError, ValueError):
            continue
        if not (b["w"] <= x <= b["e"] and b["s"] <= y <= b["n"]) or (poly and not point_in_ring(x, y, poly)):
            continue
        get = lambda k: (r.get(col[k]) or "").strip() if col[k] else ""  # noqa: E731
        sub = get("subject").replace("_", " ").replace("-", ": ", 1)
        out.append({"x": round(x, 6), "y": round(y, 6), "name": get("name"), "opened": years(get("opened")),
                    "closed": years(get("closed")), "subject": sub or None, "governance": get("governance") or None,
                    "accreditation": get("accreditation") or None, "size": get("size") or None})
    log(f"s00 Mapping Museums: {len(out)} museums in the area, {sum(1 for m in out if m['closed'])} of them closed "
        f"(columns used: {col})")
    save(city_id, "museums", out)
