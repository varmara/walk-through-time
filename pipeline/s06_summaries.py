"""A short summary (one to three sentences) for each named or listed building.

Two kinds, and the card says which:
  - from Wikipedia: the first sentences of the building's own article (CC BY-SA), when it has one;
  - from the map's data: written from facts already in the data (what the building is used as today and its
    street from OpenStreetMap, its date and source, its listing from Historic England, its architect from
    Wikidata). Nothing is added that the data does not say.

Writes work/<city>/summaries.json: {building index: {"text", "src": {title, url, kind}}}.

It also asks Wikipedia for each article's lead photo (prop=pageimages, free files only), for buildings that have no
image on Wikidata: work/<city>/pageimages.json, {building index: {"photo": {file, year, author, licence}, "article"}}.
s07_package uses it last, after Wikidata's image and a geotagged Commons photo (s06_photos). A building with no
article of its own can be given one for its photo in stories/<city>/photo-articles.md. A lead photo is used only
when it is a photograph (JPEG, not a crest, logo or map) and, if Commons gives it a position, was taken within
MAX_PHOTO_M metres of the building.
"""
import re
import urllib.parse

from .common import load, log, save, work
from .web import http
from .names import marker, tidy_listing
from .geo import centroid, metres
from .s05_dates import info_for, osm_article
from .s06_photos import metadata

WIKI = "https://en.wikipedia.org/w/api.php"
COMMONS = "https://commons.wikimedia.org/w/api.php"
SENTENCES = 3
MAX_CHARS = 480
MAX_PHOTO_M = 300

# What a building is used as, from OpenStreetMap tags (on the outline or on a named point inside it).
AMENITY = {
    "pub": "pub", "bar": "bar", "restaurant": "restaurant", "cafe": "café", "fast_food": "takeaway",
    "bank": "bank", "place_of_worship": "place of worship", "library": "library", "theatre": "theatre",
    "cinema": "cinema", "school": "school", "college": "college", "university": "university building",
    "hospital": "hospital", "clinic": "clinic", "doctors": "doctors' surgery", "dentist": "dental practice",
    "pharmacy": "pharmacy", "community_centre": "community centre", "townhall": "town hall",
    "police": "police station", "fire_station": "fire station", "arts_centre": "arts centre",
    "nightclub": "nightclub", "post_office": "post office", "courthouse": "court", "events_venue": "events venue",
    "music_venue": "music venue", "social_club": "social club", "kindergarten": "nursery", "marketplace": "market",
}
TOURISM = {"museum": "museum", "hotel": "hotel", "gallery": "gallery", "guest_house": "guest house",
           "hostel": "hostel", "attraction": "visitor attraction"}
HISTORIC = {"castle": "castle", "monument": "monument", "memorial": "memorial", "ruins": "ruin", "church": "church"}
SHOP = {"books": "bookshop", "clothes": "clothes shop", "supermarket": "supermarket", "convenience": "convenience store",
        "department_store": "department store", "bakery": "bakery", "butcher": "butcher's", "hairdresser": "hairdresser's",
        "jewelry": "jeweller's", "optician": "optician's", "charity": "charity shop", "florist": "florist's",
        "mall": "shopping centre", "furniture": "furniture shop", "shoes": "shoe shop", "music": "music shop"}
BUILDING = {
    "church": "church", "cathedral": "cathedral", "chapel": "chapel", "mosque": "mosque", "synagogue": "synagogue",
    "temple": "temple", "house": "house", "terrace": "terrace of houses", "detached": "detached house",
    "semidetached_house": "semi-detached house", "bungalow": "bungalow", "apartments": "block of flats",
    "residential": "residential building", "commercial": "commercial building", "retail": "shop building",
    "office": "office building", "industrial": "industrial building", "warehouse": "warehouse",
    "school": "school", "university": "university building", "college": "college building", "hospital": "hospital",
    "hotel": "hotel", "train_station": "railway station", "civic": "civic building", "public": "public building",
    "government": "government building", "castle": "castle", "bridge": "bridge", "stadium": "stadium",
    "museum": "museum", "pub": "pub", "dormitory": "student residence", "garage": None, "garages": None,
    "shed": None, "roof": None, "yes": None, "construction": None,
}
ARTICLE = lambda w: "an" if w[:1].lower() in "aeiou" else "a"  # noqa: E731


def use_of(tags_list, name):
    """(phrase, is_occupant) or (None, False). Occupant: a shop or office in the building, not the building itself."""
    lname = (name or "").lower()
    for t in tags_list:
        if "building society" in lname and (t.get("amenity") == "bank" or t.get("office") or t.get("shop")):
            return "building society branch", True
        if t.get("amenity") in AMENITY:
            kind = AMENITY[t["amenity"]]
            if kind == "place of worship" and t.get("religion") == "christian":
                kind = "church"
            return kind, t["amenity"] in ("bank", "restaurant", "cafe", "fast_food", "pharmacy", "bar", "nightclub",
                                         "doctors", "dentist", "post_office")
        if t.get("tourism") in TOURISM:
            return TOURISM[t["tourism"]], False
        if t.get("historic") in HISTORIC:
            return HISTORIC[t["historic"]], False
        if t.get("shop"):
            return SHOP.get(t["shop"], "shop"), True
        if t.get("office"):
            return "office", True
    for t in tags_list:
        b = t.get("building")
        if b in BUILDING and BUILDING[b]:
            return BUILDING[b], False
    return None, False


def street_of(tags_list):
    for t in tags_list:
        if t.get("addr:street"):
            return t["addr:street"]
    return None


def tidy(listing_name):
    """Historic England names are often in capitals: ' 3 AND 5, HOUNDS GATE' -> '3 and 5, Hounds Gate'."""
    n = listing_name.strip()
    if n.isupper():
        n = n.title()
    return re.sub(r"\b(And|Of|The|At|To|On|In)\b", lambda m: m[1].lower(), n).replace("'S ", "'s ")


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def date_sentence(d):
    if not d or d.get("f") == "area" or d.get("y") is None:
        return None
    y, f, src = d["y"], d["f"], d.get("src")
    when = (f"was built in {y}" if f == "exact" else f"dates from about {y}" if f == "approx"
            else f"dates from the {ordinal(y // 100 + 1)} century")
    s = f"The building {when}, according to {src}"
    if d.get("alts"):
        s += ", though other sources give a different date"
    return s + "."


def written(name, tags_list, d, listing, architect, address=False, today=None):
    use, occupant = use_of(tags_list, today or name)
    street = street_of(tags_list)
    on = f" on {street}" if street else ""
    out = []
    if today:                # "Newcastle House, on Castle Boulevard. Today it houses Gala Coral Group, an office."
        out.append(f"{name}{',' + on if on else ''}. Today it houses {today}"
                   + (f", {ARTICLE(use)} {use}." if use and occupant else "."))
    elif address and use:      # the only name is the listing's address: "A shop at 3 and 5, Hounds Gate."
        out.append(f"{ARTICLE(use).capitalize()} {use} at {name}.")
    elif address:
        pass
    elif name and use:
        out.append(f"{name}: {ARTICLE(use)} {use}{on}." if occupant else f"{name} is {ARTICLE(use)} {use}{on}.")
    elif name and street:
        out.append(f"{name}, on {street}.")
    ds = date_sentence(d)
    if ds:
        out.append(ds)
    bits = []
    if listing:
        g = listing.get("Grade")
        ln = (listing.get("Name") or "").strip()
        he = tidy_listing(ln) or ""
        as_ = f" as {tidy(ln)}" if ln and not address and name and he.lower() != name.lower() and ln.lower() not in name.lower() and name.lower() not in ln.lower() else ""
        if g:
            bits.append(f"it is Grade {g} listed{as_}")
    if architect:
        bits.append(f"{'it ' if not bits else ''}was designed by {architect}")
    if bits:
        out.append(" and ".join(bits)[0].upper() + " and ".join(bits)[1:] + ".")
    if len(out) < 2 and not (use and name):   # a lone date or name says no more than the card's own rows
        return None
    return " ".join(out)


def trim(text):
    text = re.sub(r"\s*\([^()]*\)", "", text)            # pronunciations, dates in brackets
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    out = ""
    for p in parts[:SENTENCES]:
        if out and len(out) + len(p) > MAX_CHARS:
            break
        out = (out + " " + p).strip()
    return out


def extracts(titles):
    """{title: intro text} for Wikipedia titles, 20 per request (the API's limit for intros)."""
    got, titles = {}, list(dict.fromkeys(titles))
    for i in range(0, len(titles), 20):
        chunk = titles[i:i + 20]
        try:
            r = http(WIKI, params={"action": "query", "prop": "extracts", "exintro": "1", "explaintext": "1",
                                   "exlimit": "20", "redirects": "1", "format": "json", "titles": "|".join(chunk)})
        except Exception as e:  # noqa: BLE001
            log(f"    Wikipedia intros failed for {len(chunk)} titles: {e}")
            continue
        q = r.get("query", {})
        back = {}
        for n in q.get("normalized", []) + q.get("redirects", []):
            back[n["to"]] = back.get(n["from"], n["from"])
        for pg in q.get("pages", {}).values():
            if pg.get("extract"):
                got[back.get(pg["title"], pg["title"])] = pg["extract"]
                got[pg["title"]] = pg["extract"]
    return got


def lead_images(titles):
    """{title: file name} for Wikipedia titles: each article's lead photo, free files only (PageImages' own default,
    asked for here so it stays so), 50 titles to a request. An article with no free lead image is left out."""
    got, titles = {}, list(dict.fromkeys(titles))
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        try:
            r = http(WIKI, params={"action": "query", "prop": "pageimages", "piprop": "name", "pilicense": "free",
                                   "pilimit": "50", "redirects": "1", "format": "json", "titles": "|".join(chunk)})
        except Exception as e:  # noqa: BLE001
            log(f"    Wikipedia lead images failed for {len(chunk)} titles: {e}")
            continue
        q = r.get("query", {})
        back = {}
        for n in q.get("normalized", []) + q.get("redirects", []):
            back[n["to"]] = back.get(n["from"], n["from"])
        for pg in q.get("pages", {}).values():
            if pg.get("pageimage"):
                got[back.get(pg["title"], pg["title"])] = pg["pageimage"].replace("_", " ")
                got[pg["title"]] = pg["pageimage"].replace("_", " ")
    return got


def geotags(files):
    """{file name: (lon, lat)} for those Commons files that have a position."""
    out = {}
    for i in range(0, len(files), 50):
        try:
            r = http(COMMONS, params={"action": "query", "prop": "coordinates", "colimit": "50", "format": "json",
                                      "formatversion": "2", "titles": "|".join("File:" + f for f in files[i:i + 50])})
        except Exception as e:  # noqa: BLE001
            log(f"    Commons positions failed: {e}")
            continue
        for pg in r.get("query", {}).get("pages", []):
            if pg.get("coordinates"):
                out[pg["title"][5:]] = (pg["coordinates"][0]["lon"], pg["coordinates"][0]["lat"])
    return out


def why_not(file, facts, xy, building_xy):
    """None when the file may be a building's photo; else why not. `facts` is Commons' record of it (file, licence,
    author, year) or None, `xy` its position or None."""
    if not file.lower().endswith((".jpg", ".jpeg")):
        return "not a photograph (a crest, logo, map or drawing)"
    if not facts or not facts.get("licence"):
        return "no licence on Commons"
    if xy and building_xy and metres(building_xy, xy) > MAX_PHOTO_M:
        return f"taken {metres(building_xy, xy):.0f} m away"
    return None


def same_name(title, name):
    """An article and a pin of the same name: "Black Boy Hotel", "The Black Boy Hotel"; "Edwalton railway station",
    "Edwalton station"."""
    def norm(s):
        s = re.sub(r"\s*\(.*?\)", "", s.lower())
        s = re.sub(r"^the ", "", s).replace(" railway ", " ")
        return re.sub(r"[^a-z0-9]+", " ", s).strip()
    return norm(title) == norm(name)


def lead_photos(city_id, buildings, titles, wd, listing):
    """Lead photos for buildings with no Wikidata image: their article's, or the one stories/<city>/photo-articles.md
    names. Saves work/<city>/pageimages.json."""
    ask = {}
    for i, t in titles.items():
        if not (info_for(buildings[i], i, wd, listing) or {}).get("image"):
            ask[i] = t
    by_osm = {b["osm"]: i for i, b in enumerate(buildings)}
    for osm, article in (load(city_id, "curated").get("photo_articles") or {}).items():
        if osm not in by_osm:
            log(f"    photo-articles.md: {osm} is not a building outline")
        elif not (info_for(buildings[by_osm[osm]], by_osm[osm], wd, listing) or {}).get("image"):
            ask[by_osm[osm]] = article
    # a story's pin (not a building: Papplewick Pumping Station, beyond the map's buildings) told from a Wikipedia
    # article about it, the article named as the pin is: that article's lead photo, by the pin ("p<index>"), under the
    # same checks, and taken within 300 m of the pin (with no outline to go by, a photo with no position is not used:
    # a portrait, a drawing or a view of the town is not of the place)
    pins = load(city_id, "layers").get("pins", []) if work(city_id, "layers").exists() else []
    pin_ask = {}
    for k, pn in enumerate(pins):
        url = (pn.get("source") or {}).get("url", "") if isinstance(pn.get("source"), dict) else ""
        title = urllib.parse.unquote(url.split("/wiki/", 1)[1]).replace("_", " ") if "en.wikipedia.org/wiki/" in url else ""
        if pn.get("layer") != "people" and title and same_name(title, pn.get("name") or ""):
            pin_ask[f"p{k}"] = title
    leads = lead_images([*ask.values(), *pin_ask.values()])
    files = sorted({leads[t] for t in [*ask.values(), *pin_ask.values()] if t in leads})
    facts = {m["file"]: m for m in metadata(["File:" + f for f in files]).values()}
    xy = geotags(files)
    out = {}
    for i, t in ask.items():
        f = leads.get(t)
        if not f:
            continue
        no = why_not(f, facts.get(f), xy.get(f), centroid(buildings[i]["rings"][0]))
        if no:
            log(f"    lead photo of {t} not used for building {i}: {f} is {no}")
            continue
        out[str(i)] = {"photo": facts[f], "article": t}
    for k, t in pin_ask.items():
        f = leads.get(t)
        if not f:
            continue
        pn = pins[int(k[1:])]
        no = why_not(f, facts.get(f), xy.get(f), (pn["x"], pn["y"])) or (None if xy.get(f) else "without a position on Commons")
        if no:
            log(f"    lead photo of {t} not used for pin {pn['name']}: {f} is {no}")
            continue
        out[k] = {"photo": facts[f], "article": t}
    save(city_id, "pageimages", out)
    log(f"s06 lead photos: {len(out)} of {len(ask) + len(pin_ask)} articles give a usable free lead photo (for buildings with no Wikidata image, and story pins)")


def main(city_id):
    buildings = load(city_id, "buildings")
    wd, listing, dates = load(city_id, "wikidata"), load(city_id, "listing"), load(city_id, "dates")
    inside = {}
    for pl in load(city_id, "places"):
        if pl["b"] is not None:
            inside.setdefault(pl["b"], []).append(pl["tags"])
    names = load(city_id, "names")          # s06_names

    titles = {}
    for i, b in enumerate(buildings):
        info = info_for(b, i, wd, listing) or {}
        url = info.get("article")
        if url:
            titles[i] = urllib.parse.unquote(url.rsplit("/wiki/", 1)[1]).replace("_", " ")
        elif osm_article(b["tags"]):
            titles[i] = osm_article(b["tags"])
    intros = extracts(titles.values()) if titles else {}

    out, n_wiki, n_data = {}, 0, 0
    for i, b in enumerate(buildings):
        k, t = str(i), b["tags"]
        tl = intros.get(titles.get(i, ""))
        if tl:
            text = trim(tl)
            if len(text) > 40:
                out[k] = {"text": text, "src": {"title": titles[i], "kind": "Wikipedia",
                                                "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(titles[i].replace(" ", "_"))}}
                n_wiki += 1
                continue
        best = (listing.get(k) or [None])[0]
        tags_list = [t] + [pt for pt in inside.get(i, []) if not marker(pt)]   # a war memorial inside is not its use
        # the place the building is named after first, so "X: a …" says what X is, not what its neighbour is
        own = (names.get(k, {}).get("today") or names.get(k, {}).get("name") or "").strip().lower()
        tags_list.sort(key=lambda x: 0 if x is t else 1 if (x.get("name") or "").strip().lower() == own else 2)
        info = info_for(b, i, wd, listing) or {}
        nm = names.get(k, {})
        name, today = nm.get("name"), nm.get("today")
        if best and name == best.get("Name"):       # only Historic England's own words: written as an address
            name = None
        if not name and not best:
            continue
        address = not name
        text = written(name or tidy((best or {}).get("Name", "")), tags_list, dates.get(k), best,
                       info.get("architect") or t.get("architect"), address=address, today=today)
        if text:
            srcs = ["OpenStreetMap"] + (["Historic England"] if best else []) + (["Wikidata"] if info.get("architect") else [])
            out[k] = {"text": text, "src": {"title": " · ".join(srcs), "kind": "Written from the map's data"}}
            n_data += 1
    save(city_id, "summaries", out)
    lead_photos(city_id, buildings, titles, wd, listing)
    log(f"s06 summaries: {n_wiki} from Wikipedia ({len(titles)} buildings have an article), {n_data} written from the data")
