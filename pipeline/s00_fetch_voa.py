"""Download Council Tax build periods per small area, with the areas' boundaries.

Valuation Office Agency, "Council Tax: stock of properties", table CTSOP 4.1: the number of homes in each
Lower layer Super Output Area (LSOA, a few hundred homes) by build period (before 1900, 1900-1918, ...).
Boundaries: ONS, LSOAs December 2021 (super generalised). Both Open Government Licence.

These are counts for an area, not dates for a building; step s05 turns them into a clearly marked
estimate for homes with no other date, only where one period clearly dominates the area.

Writes work/<city>/voa.json: [{code, name, rings, periods: [[label, start, end, count]], known}].
"""
import csv
import io
import re
import time
import urllib.request
import zipfile

from .common import UA, city, http, log, point_in_ring, save

CTSOP = "https://assets.publishing.service.gov.uk/media/648affc9b32b9e0012a96867/CTSOP4_1_2020-2023_03_31.zip"
LSOA = ("https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
        "Lower_layer_Super_Output_Areas_December_2021_Boundaries_EW_BSC_V4/FeatureServer/0/query")

# Build periods as the estimate uses them: single years from 2009 are summed into one period.
PERIODS = [("before 1900", 1800, 1899), ("1900–1918", 1900, 1918), ("1919–1929", 1919, 1929),
           ("1930–1939", 1930, 1939), ("1945–1954", 1945, 1954), ("1955–1964", 1955, 1964),
           ("1965–1972", 1965, 1972), ("1973–1982", 1973, 1982), ("1983–1992", 1983, 1992),
           ("1993–1999", 1993, 1999), ("2000–2008", 2000, 2008), ("2009 or later", 2009, 2024)]


def period_of(col):
    """'bp_1930_1939' -> index into PERIODS; 'bp_pre_1900' -> 0; 'bp_2015' -> last; None if not a period."""
    c = col.lower()
    if "pre" in c and "1900" in c:
        return 0
    m = re.search(r"(\d{4})(?:\D+(\d{4}))?", c)
    if not m or not c.startswith("bp"):
        return None
    a = int(m[1])
    for i, (_, s, e) in enumerate(PERIODS):
        if s <= a <= e:
            return i
    return None


def count(v):
    v = (v or "").strip()
    if v in ("-", ".."):      # fewer than 5, suppressed
        return 2
    try:
        return int(float(v))
    except ValueError:
        return 0


def main(city_id):
    c = city(city_id)
    b, poly = c["bbox"], c.get("polygon")
    try:
        gj = http(LSOA, params={"where": "1=1", "geometry": f"{b['w']},{b['s']},{b['e']},{b['n']}",
                                "geometryType": "esriGeometryEnvelope", "inSR": "4326",
                                "spatialRel": "esriSpatialRelIntersects", "outFields": "LSOA21CD,LSOA21NM",
                                "outSR": "4326", "returnGeometry": "true", "geometryPrecision": "5", "f": "geojson"})
    except Exception as e:  # noqa: BLE001 - the estimate is optional
        log(f"s00 VOA: LSOA boundaries failed, no estimates this run ({e})")
        save(city_id, "voa", [])
        return
    areas = {}
    for f in gj.get("features", []):
        g, pr = f.get("geometry") or {}, f.get("properties") or {}
        rings = [g["coordinates"][0]] if g.get("type") == "Polygon" else [q[0] for q in g.get("coordinates", [])]
        pts = [p for r in rings for p in r]
        if not pts or (poly and not any(point_in_ring(x, y, poly) for x, y in pts[::3])):
            continue
        code = pr.get("LSOA21CD") or next((v for k, v in pr.items() if k.upper().endswith("CD")), None)
        areas[code] = {"code": code, "name": pr.get("LSOA21NM"), "rings": rings}
    log(f"s00 VOA: {len(areas)} small areas (LSOAs) in the city's area")

    try:
        req = urllib.request.Request(CTSOP, headers={"User-Agent": UA})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=300) as r:
                    raw = r.read()
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    raise
                log(f"    CTSOP download: {e}; retrying")
                time.sleep(15)
        z = zipfile.ZipFile(io.BytesIO(raw))
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        name = max(names, key=lambda n: max([int(y) for y in re.findall(r"(?<!\d)(20\d\d)(?!\d)", n)] or [0]))
        log(f"    CTSOP files: {names}; reading {name}")
        rows = csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8-sig"))
        cols = rows.fieldnames or []
        log(f"    columns: {cols[:40]}")
        code_col = next((k for k in cols if k.lower() in ("ecode", "lsoa21cd", "lsoa_code", "area_code")), None)
        band_col = next((k for k in cols if k.lower() in ("band", "council_tax_band")), None)
        year_col = next((k for k in cols if k.lower() in ("year", "date")), None)
        per_cols = {k: period_of(k) for k in cols if period_of(k) is not None}
        best_year = {}
        found = {}
        for row in rows:
            code = row.get(code_col)
            if code not in areas:
                continue
            if band_col and row.get(band_col, "").strip().lower() not in ("all", "all bands", "total"):
                continue
            yr = row.get(year_col, "") if year_col else ""
            if code in best_year and yr <= best_year[code]:
                continue
            best_year[code] = yr
            per = [0] * len(PERIODS)
            for k, i in per_cols.items():
                per[i] += count(row.get(k))
            found[code] = per
        out = []
        for code, per in found.items():
            a = areas[code]
            out.append({**a, "known": sum(per), "periods": [[PERIODS[i][0], PERIODS[i][1], PERIODS[i][2], n]
                                                             for i, n in enumerate(per)]})
        log(f"    build periods found for {len(out)}/{len(areas)} small areas (year {max(best_year.values(), default='?')})")
    except Exception as e:  # noqa: BLE001
        log(f"s00 VOA: CTSOP table failed, no estimates this run ({e})")
        out = []
    save(city_id, "voa", out)
