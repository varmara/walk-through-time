"""Check hand-written stories against Wikipedia and place each one on a building.

Stories live in stories/<city>.py (see CONTRIBUTING.md). A source is a Wikipedia article ("en:Title") or a
Historic England list entry ("he:1254566"), whose official description is checked the same way. For every entry:
  1. The Wikipedia article is fetched. Every string in `facts` must appear in it (case-insensitive).
     If one is missing, the entry is dropped: if the article does not say it, the story should not either.
  2. The entry is placed on a building, trying in order:
       at="osm:way/123"          an explicit OpenStreetMap outline
       at="nhle:1271444"         a Historic England list entry: its building, or a pin at its point (a monument)
       the article's Wikidata item, tagged on a building outline in OpenStreetMap
       the item's Historic England list entry (P1216), matched in step s02
       the article's coordinates, inside (or within 15 m of) a building outline
       at="name:..." or the entry's name, matching a building name or a named place inside one
       at="near:120"             the building nearest the article's coordinates within that many metres
                                 (for grounds and parks, whose coordinates fall on open space)
     An entry that matches no building but whose article has coordinates becomes a pin on the map
     (bridges, grounds, squares). Entries with neither are dropped.
  People layers (kind="people") pair a person's article (`source`) with a place's article (`place`).
     The facts must appear in the two articles together, the place's article decides the building, and
     the person's occupations on Wikidata (P106) decide the group: architects, writers, sport and so on.
     An entry can set `group` itself when Wikidata has no occupation (a duo, a team).
  Historic England blocks automated requests, so an entry using a list entry ("he:1254566") also gives `quote`:
     short passages copied from the entry. If the page cannot be fetched, the facts are checked against them.
  3. An entry may give the building's `year` ("1855", "c. 1420", "1841..1844"). Its digits must appear in the
     article too. Step s05 uses it as a date source ("Wikipedia") alongside OpenStreetMap and Wikidata.

Writes curated.json: {layers: [...], entries: [{layer, group, b, name, story, source, how, year?}], dropped: [...]}.
"""
import importlib.util
import re
import time
from pathlib import Path
from urllib.parse import quote

from .common import building_at, http, http_text, load, log, parse_year, save


def stories(city_id):
    path = Path(f"stories/{city_id}.py")
    if not path.exists():
        return []
    spec = importlib.util.spec_from_file_location(f"stories_{city_id}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _wiki[city_id] = getattr(mod, "WIKIPEDIA", {})
    _plaques[city_id] = getattr(mod, "PLAQUES", {})
    _collections[city_id] = getattr(mod, "COLLECTIONS", [])
    return mod.CURATED


_collections = {}   # per city: picture collections linked, not copied (their pictures are not openly licensed)
_plaques = {}   # per city: corrections to plaques, by the start of their inscription or their subject
_wiki = {}      # per city: {person's name as a plaque or Wikidata gives it: their English Wikipedia article}


_cache = {}


def article(ref):
    """'en:Title' (Wikipedia) or 'he:1254566' (Historic England list entry) -> {text, url, title, qid, coords, nhle}."""
    if ref in _cache:
        return _cache[ref]
    lang, title = ref.split(":", 1)
    if lang == "he":
        url = f"https://historicengland.org.uk/listing/the-list/list-entry/{title}"
        page = http_text(url)
        time.sleep(1)
        _cache[ref] = {"text": page["text"].lower(), "url": url, "title": page["title"] or f"List entry {title}",
                       "qid": None, "coords": None, "nhle": [title], "kind": "Historic England"}
        return _cache[ref]
    r = http(f"https://{lang}.wikipedia.org/w/api.php", params={
        "action": "query", "prop": "extracts|info|pageprops|coordinates", "explaintext": 1, "inprop": "url",
        "ppprop": "wikibase_item", "coprimary": "primary", "redirects": 1, "format": "json", "titles": title})
    page = next(iter(r["query"]["pages"].values()))
    time.sleep(0.5)
    if "missing" in page:
        _cache[ref] = None
        return None
    co = (page.get("coordinates") or [None])[0]
    # the plain-text extract leaves out bulleted lists ("Notable families", "Notable residents"), so their text
    # is added from the page's wikitext
    lists = ""
    try:
        w = http(f"https://{lang}.wikipedia.org/w/api.php", params={
            "action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "redirects": 1,
            "format": "json", "formatversion": "2", "titles": page.get("title", title)})
        wt = w["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
        from .s04_residents import strip_wikitext      # (imported here: that step imports this one)
        items = re.findall(r"^[*#]+.*$", wt, flags=re.M)
        lists = strip_wikitext("\n".join(items), keep_lists=True)
    except Exception:  # noqa: BLE001 - the extract alone still works
        pass
    _cache[ref] = {
        "text": ((page.get("extract") or "") + "\n" + lists).lower(),
        "url": page.get("fullurl") or f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
        "title": page.get("title", title),
        "qid": page.get("pageprops", {}).get("wikibase_item"),
        "coords": (co["lon"], co["lat"]) if co else None,
        "nhle": [], "kind": "Wikipedia",
    }
    return _cache[ref]


def nhle_of(qids):
    if not qids:
        return {}
    rows = http("https://query.wikidata.org/sparql", {"format": "json", "query":
                f"SELECT ?item ?nhle WHERE {{ VALUES ?item {{ {' '.join('wd:' + q for q in qids)} }} ?item wdt:P1216 ?nhle }}"},
                accept="application/sparql-results+json")["results"]["bindings"]
    out = {}
    for r in rows:
        out.setdefault(r["item"]["value"].rsplit("/", 1)[-1], []).append(r["nhle"]["value"])
    return out


PEOPLE_GROUPS = [
    # key, title, words that may appear in an occupation's English label (first match wins)
    ("architects", "Architects", ["architect"]),
    ("writers", "Writers and journalists", ["writer", "novelist", "poet", "journalist", "playwright", "author"]),
    ("science", "Scientists and engineers", ["mathematician", "physicist", "scientist", "engineer", "inventor", "chemist"]),
    ("industry", "Industry and trade", ["businessperson", "manufacturer", "industrialist", "merchant", "entrepreneur"]),
    ("sport", "Sport", ["football", "cricket", "coach", "skater", "ice dancer", "athlete", "sportsperson", "boxer",
                        "prize fighter", "pugilist", "jockey", "cyclist"]),
    ("arts", "Arts and performance", ["actor", "musician", "singer", "painter", "dancer", "artist", "designer", "composer"]),
    ("faith", "Faith and charity", ["preacher", "evangelist", "minister", "priest", "clergy", "vicar", "bishop",
                                    "salvation army", "methodist", "missionary", "philanthropist", "charity"]),
    ("military", "Soldiers and the military", ["soldier", "general", "marshal", "colonel", "officer", "admiral", "governor"]),
    ("public", "Politics and public life", ["politician", "reformer", "activist", "mayor", "member of parliament"]),
    ("other", "Other people", []),
]


def occupations(qids):
    if not qids:
        return {}
    rows = http("https://query.wikidata.org/sparql", {"format": "json", "query":
                f"SELECT ?item ?label WHERE {{ VALUES ?item {{ {' '.join('wd:' + q for q in qids)} }} "
                f"?item wdt:P106 ?occ . ?occ rdfs:label ?label FILTER(LANG(?label) = \"en\") }}"},
                accept="application/sparql-results+json")["results"]["bindings"]
    out = {}
    for r in rows:
        out.setdefault(r["item"]["value"].rsplit("/", 1)[-1], []).append(r["label"]["value"].lower())
    return out


def people_group(labels):
    for key, _title, words in PEOPLE_GROUPS:
        if any(w in lab for lab in labels for w in words):
            return key
    return None


def norm(s):
    return " ".join(str(s or "").lower().replace("’", "'").split())


def main(city_id):
    layers = stories(city_id)
    buildings = load(city_id, "buildings")
    listing = load(city_id, "listing")
    places = load(city_id, "places")
    by_osm = {b["osm"]: i for i, b in enumerate(buildings)}
    by_qid = {b["tags"]["wikidata"]: i for i, b in enumerate(buildings) if b["tags"].get("wikidata")}
    by_nhle = {str(e["ListEntry"]): int(i) for i, es in listing.items() for e in es}
    listed_xy = {str(p["ListEntry"]): (p["x"], p["y"]) for p in load(city_id, "listed")}
    names = {}
    for i, b in enumerate(buildings):
        if b["tags"].get("name"):
            names.setdefault(norm(b["tags"]["name"]), i)
    for p in places:
        if p["b"] is not None and p["name"]:
            names.setdefault(norm(p["name"]), p["b"])

    entries, dropped = [], []
    arts = {}
    for L in layers:
        for e in L["entries"]:
            for ref in filter(None, (e["source"], e.get("place"))):
                if ref in arts:
                    continue
                try:
                    arts[ref] = article(ref)
                except Exception as ex:  # noqa: BLE001
                    arts[ref] = None
                    log(f"    {ref}: {ex}")
    for L in layers:   # list entries that could not be fetched: check against the quoted passages instead
        for e in L["entries"]:
            for ref in filter(None, (e["source"], e.get("place"))):
                if arts.get(ref) is None and ref.startswith("he:") and e.get("quote"):
                    num = ref[3:]
                    arts[ref] = {"text": " ".join(e["quote"]).lower(), "title": f"List entry {num}",
                                 "url": f"https://historicengland.org.uk/listing/the-list/list-entry/{num}",
                                 "qid": None, "coords": None, "nhle": [num], "kind": "Historic England"}
    nhle = nhle_of(sorted({a["qid"] for a in arts.values() if a and a["qid"]}))
    person_qids = sorted({arts[e["source"]]["qid"] for L in layers if L.get("kind") == "people"
                          for e in L["entries"] if arts.get(e["source"]) and arts[e["source"]]["qid"]})
    try:
        occ = occupations(person_qids)
    except Exception as ex:  # noqa: BLE001
        log(f"    occupations from Wikidata failed: {ex}")
        occ = {}

    for L in layers:
        kept = 0
        for e in L["entries"]:
            src = arts.get(e["source"])
            a = arts.get(e["place"]) if e.get("place") else src     # the article that places the entry
            why = None
            if src is None or (e.get("place") and a is None):
                why = "Wikipedia article not found"
            else:
                text = src["text"] + "\n" + (a["text"] if e.get("place") else "")
                facts = list(e.get("facts", ())) + re.findall(r"\d{4}", e.get("year", ""))
                missing = [f for f in dict.fromkeys(facts) if f.lower() not in text]
                if missing:
                    why = "articles do not mention: " + ", ".join(missing)
            b = how = None
            if not why:
                at = e.get("at", "")
                if at.startswith("pin:"):       # an explicit point "lon,lat", for places the article does not locate
                    a = {**a, "coords": tuple(float(v) for v in at[4:].split(","))}
                    at = "pinned"
                if at.startswith("nhle:"):
                    if at[5:] in by_nhle:
                        b, how = by_nhle[at[5:]], "Historic England list entry"
                    elif at[5:] in listed_xy:
                        a, at, how = {**a, "coords": listed_xy[at[5:]]}, "pinned", None
                        e = {**e, "_how": "pin at the Historic England list entry's point"}
                if at.startswith("name:") and norm(at[5:]) in names:
                    b, how = names[norm(at[5:])], "name in OpenStreetMap"
                if at == "pinned":
                    pass
                elif b is None and at.startswith("osm:") and at[4:] in by_osm:
                    b, how = by_osm[at[4:]], "OpenStreetMap outline"
                if b is None and at != "pinned" and a["qid"] in by_qid:
                    b, how = by_qid[a["qid"]], "Wikidata tag on the outline"
                if b is None and at != "pinned":
                    for n in a["nhle"] + nhle.get(a["qid"], []):
                        if n in by_nhle:
                            b, how = by_nhle[n], "Historic England list entry"
                            break
                if b is None and at != "pinned" and a["coords"]:
                    radius = int(at[5:]) if at.startswith("near:") and at[5:].isdigit() else 15
                    b = building_at(buildings, *a["coords"], near=radius)
                    how = f"article coordinates (within {radius} m)" if b is not None else None
                if b is None and at != "pinned":
                    key = norm(at[5:] if at.startswith("name:") else e["name"])
                    if key in names:
                        b, how = names[key], "name in OpenStreetMap"
                if b is None and a["coords"]:
                    how = e.get("_how") or "pin where the story file puts it" if at == "pinned" else "pin at the article's coordinates (no building there: a bridge, a ground, a square)"
                elif b is None:
                    why = "could not place it on a building, and the article has no coordinates"
            if why:
                dropped.append({"layer": L["id"], "name": e["name"], "why": why})
                continue
            group = e.get("group", L["id"])
            if L.get("kind") == "people":
                group = "people-" + (e.get("group") or people_group(occ.get(src["qid"], [])) or "other")
            kept += 1
            entries.append({"layer": L["id"], "group": group, "b": b, "name": e["name"],
                            **({"pin": list(a["coords"])} if b is None else {}),
                            "story": e["story"], "how": how,
                            "source": {"title": src["title"], "url": src["url"], "kind": src["kind"]},
                            **({"place": {"title": a["title"], "url": a["url"], "kind": a["kind"]}} if e.get("place") else {}),
                            **({"year": list(parse_year(e["year"]))} if e.get("year") and parse_year(e["year"]) else {}),
                            **({"names": False} if e.get("names") is False else {})})
        log(f"s04 {L['id']}: {kept}/{len(L['entries'])} stories kept")
    for d in dropped:
        log(f"    dropped {d['layer']} / {d['name']}: {d['why']}")
    meta = []
    for L in layers:
        m = {k: L[k] for k in ("id", "title", "intro", "kind") if k in L}
        if L.get("kind") == "people":
            used = {e["group"] for e in entries if e["layer"] == L["id"]}
            m["groups"] = [["people-" + k, t] for k, t, _ in PEOPLE_GROUPS if "people-" + k in used]
        meta.append(m)
    save(city_id, "curated", {"layers": meta, "entries": entries, "dropped": dropped,
                              "wikipedia": _wiki.get(city_id, {}), "plaques": _plaques.get(city_id, {}),
                              "collections": _collections.get(city_id, [])})
