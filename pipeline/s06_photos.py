"""Photos from Wikimedia Commons: a current photo for buildings with none, and old photographs ("archive").

Commons holds geotagged photos, among them over a hundred thousand imported from Geograph for this part of
England ("… - geograph.org.uk - 1234567.jpg"), and old photographs and postcards now in the public domain.
1. Walk the city in cells with the Commons geosearch (a cell that hits the 500 limit is split in four).
2. A file belongs to a building when its title names the building (its name, or its house number and street)
   and it was taken within MAX_M metres of it: geotags are where the photographer stood.
3. Each file's date, author and licence come from Commons (extmetadata). A file dated before ARCHIVE_BEFORE is
   an old photograph: per building up to SIX, one per decade, not older than the building itself (an older
   picture shows whatever stood there before). The newest other file is the building's current photo, used
   only where Wikidata has none.
4. Buildings with a Commons category on Wikidata: files there (and in its history or old-picture subcategories)
   whose title suggests an old picture are added too, as the category already says what they show.
The app shows files from Commons with their author and licence, and links to each file's page.

Writes work/<city>/photos.json: {building index: {"photo": file, "archive": [file, ...]}},
file = {"file": title, "year", "author", "licence"}.
"""
import html
import re
import time

from .common import city, load, log, save
from .web import http
from .geo import centroid, metres, point_in_ring
from .names import building_name, tidy_listing

API = "https://commons.wikimedia.org/w/api.php"
CELL_LAT, CELL_LON, RADIUS = 0.0040, 0.0065, 320
MAX_M = 160
ARCHIVE_BEFORE = 1970
SIX = 6
GENERIC = {"house", "the house", "church", "chapel", "school", "lodge", "the lodge", "hall", "cottage", "the cottage",
           "garage", "office", "offices", "shop", "flats", "the old school", "the vicarage", "the rectory", "pub",
           "warehouse", "the mill", "mill", "library", "bank", "hotel", "studio", "the studio", "barn", "stables"}


def norm(s):
    s = html.unescape(str(s)).lower().replace("’", "'").replace("_", " ")
    s = re.sub(r"\.(jpe?g|png|tiff?|gif|webp)$", "", s)
    s = re.sub(r"\s*-\s*geograph\.org\.uk\s*-\s*\d+", " ", s)
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return " " + " ".join(s.split()) + " "


def geosearch(lat, lon, radius, out, depth=0):
    r = http(API, params={"action": "query", "list": "geosearch", "gscoord": f"{lat}|{lon}", "gsradius": str(radius),
                          "gsnamespace": "6", "gslimit": "500", "gsprimary": "all", "format": "json"})
    got = r.get("query", {}).get("geosearch", [])
    for g in got:
        out[g["title"]] = (g["lon"], g["lat"])
    if len(got) >= 500 and depth < 3:     # a busy cell: four smaller ones
        d_lat, d_lon = radius / 2 / 110540, radius / 2 / 67000
        for a in (-1, 1):
            for b in (-1, 1):
                geosearch(lat + a * d_lat, lon + b * d_lon, radius // 2 + 20, out, depth + 1)


STREETISH = re.compile(r" (street|road|gate|lane|place|terrace|square|row|avenue|drive|crescent|walk|hill|grove|close|way|"
                       r"boulevard|yard|court|gardens|embankment|bay|park|estate) $")
NOT_BUILDING = re.compile(r" (close up|performing|concert|gig|choir|band|team|match|crowd|protest|parade|interior detail) ")
ARTWORK = re.compile(r"\(c?\.?\d{4}[-–]\d{4}|\bNCM\b|\(after\)|\bportrait of\b", re.I)   # paintings in a museum's collection
OLD_HINT = re.compile(r"(1[89]\d\d|19[0-6]\d)|postcard|photochrom|old |historic|victorian|edwardian|archive|lantern slide", re.I)
OLD_CAT = re.compile(r"histor|old |postcard|in the 1[89]th century|in the 1[89]\d0s|in the 19[0-6]0s|before 19|archive|photochrom", re.I)


def category_files(cat, depth=0):
    """Files in a Commons category, and in its subcategories about history or old pictures (one level down)."""
    files, cont = [], {}
    while True:
        r = http(API, params={"action": "query", "list": "categorymembers", "cmtitle": "Category:" + cat,
                              "cmtype": "file|subcat", "cmlimit": "500", "format": "json", **cont})
        for m in r.get("query", {}).get("categorymembers", []):
            if m["ns"] == 6:
                files.append(m["title"])
            elif m["ns"] == 14 and depth == 0 and OLD_CAT.search(m["title"]):
                files += category_files(m["title"][9:], 1)
        if "continue" not in r or len(files) > 3000:
            return files
        cont = {"cmcontinue": r["continue"]["cmcontinue"]}


def metadata(titles):
    info = {}
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        try:
            r = http(API, params={"action": "query", "prop": "imageinfo", "iiprop": "extmetadata|mime",
                                  "iiextmetadatafilter": "DateTimeOriginal|Artist|LicenseShortName",
                                  "titles": "|".join(chunk), "format": "json", "formatversion": "2"})
        except Exception as e:  # noqa: BLE001
            log(f"    Commons metadata failed for {len(chunk)} files: {e}")
            continue
        for pg in r.get("query", {}).get("pages", []):
            ii = (pg.get("imageinfo") or [{}])[0]
            if not str(ii.get("mime", "")).startswith("image/"):
                continue
            md = ii.get("extmetadata", {})
            text = lambda k: re.sub(r"<[^>]+>", "", html.unescape(md.get(k, {}).get("value", ""))).strip()  # noqa: E731
            y = re.search(r"(1[6-9]\d\d|20\d\d)", text("DateTimeOriginal"))
            info[pg["title"]] = {"file": pg["title"][5:], "year": int(y[1]) if y else None,
                                 "author": text("Artist")[:80] or None, "licence": text("LicenseShortName") or None}
    return info


def main(city_id):
    c = city(city_id)
    poly, b = c.get("polygon"), c["bbox"]
    files = {}
    n_cells = 0
    lat = b["s"] + CELL_LAT / 2
    while lat < b["n"]:
        lon = b["w"] + CELL_LON / 2
        while lon < b["e"]:
            near = not poly or any(point_in_ring(lon + dx * CELL_LON / 2, lat + dy * CELL_LAT / 2, poly)
                                   for dx in (-1, 0, 1) for dy in (-1, 0, 1))
            if near:
                try:
                    geosearch(lat, lon, RADIUS, files)
                except Exception as e:  # noqa: BLE001
                    log(f"    geosearch failed at {lat:.4f},{lon:.4f}: {e}")
                n_cells += 1
                time.sleep(0.1)
            lon += CELL_LON
        lat += CELL_LAT
    log(f"s06 photos: {len(files)} geotagged Commons files in {n_cells} cells")

    buildings, listing, wd = load(city_id, "buildings"), load(city_id, "listing"), load(city_id, "wikidata")
    from .s05_dates import info_for
    dates = load(city_id, "dates")
    # what each building can be recognised by in a file title
    streets = {norm(b["tags"]["addr:street"]).strip() for b in buildings if b["tags"].get("addr:street")}
    keys = []      # (phrase, building index)
    for i, bl in enumerate(buildings):
        t = bl["tags"]
        best = (listing.get(str(i)) or [None])[0] or {}
        info = info_for(bl, i, wd, listing) or {}
        name, today = building_name(t, None, info.get("label"), best.get("Name"))
        for n in {name, tidy_listing(best.get("Name")), t.get("name") if not today else None}:
            if not n:
                continue
            k = norm(re.sub(r",?\s*nottingham$", "", n, flags=re.I)).strip()
            if (len(k) >= 6 and k not in GENERIC and (" " in k or len(k) >= 9) and k not in streets
                    and not STREETISH.search(f" {k} ")):    # a street's or district's name is not a building's
                keys.append((f" {k} ", i))
        if t.get("addr:housenumber") and t.get("addr:street"):
            keys.append((norm(f"{t['addr:housenumber']} {t['addr:street']}"), i))
    centres = {}
    by_word = {}
    for k, i in keys:
        by_word.setdefault(k.split()[0] if not k.split()[0].isdigit() else k.split()[1] if len(k.split()) > 1 else k, []).append((k, i))

    matches = {}
    for title, (x, y) in files.items():
        nt = norm(title[5:])
        if NOT_BUILDING.search(nt):
            continue
        cand = set()
        for w in set(nt.split()):
            cand.update(by_word.get(w, ()))
        for k, i in cand:
            if k in nt:
                if i not in centres:
                    centres[i] = centroid(buildings[i]["rings"][0])
                if metres(centres[i], [x, y]) <= MAX_M:
                    matches.setdefault(title, set()).add(i)
    # a title that names many buildings is a street view, not a photo of one
    matches = {t: s for t, s in matches.items() if len(s) <= 2}
    log(f"    {len(matches)} files name a building near where they were taken")
    # old pictures in each building's own Commons category (from Wikidata): no geotag needed, the category says what it shows
    cats = {}
    for i, bl in enumerate(buildings):
        cat = (info_for(bl, i, wd, listing) or {}).get("commonscat")
        if cat:
            cats.setdefault(cat, set()).add(i)
    n_cat = 0
    for cat, bs in cats.items():
        try:
            fs = category_files(cat)
        except Exception as e:  # noqa: BLE001
            log(f"    Commons category {cat} failed: {e}")
            continue
        for f in fs:
            if OLD_HINT.search(f[5:]) and not ARTWORK.search(f[5:]) and not NOT_BUILDING.search(norm(f[5:])):
                matches.setdefault(f, set()).update(bs)
                n_cat += 1
        time.sleep(0.05)
    log(f"    {len(cats)} buildings' Commons categories read: {n_cat} files that look old")
    md = metadata(sorted(matches))

    out = {}
    for title, bs in matches.items():
        m = md.get(title)
        if not m:
            continue
        for i in bs:
            out.setdefault(str(i), []).append(m)
    result, n_photo, n_arch = {}, 0, 0
    for k, fs in out.items():
        d = dates.get(k) or {}
        built = d.get("y") if d.get("f") in ("exact", "approx") else None    # an area's estimate is too rough to rule out
        old = [f for f in fs if f["year"] and f["year"] < ARCHIVE_BEFORE and not (built and f["year"] < built)]
        decades = {}
        for f in sorted(old, key=lambda f: f["year"]):
            decades.setdefault(f["year"] // 10, f)
        arch = sorted(decades.values(), key=lambda f: f["year"])[:SIX]
        recent = sorted([f for f in fs if f not in old], key=lambda f: -(f["year"] or 0))
        r = {}
        if recent:
            r["photo"] = recent[0]
            n_photo += 1
        if arch:
            r["archive"] = arch
            n_arch += 1
        if r:
            result[k] = r
    save(city_id, "photos", result)
    log(f"    photos for {n_photo} buildings, old photographs for {n_arch}")
