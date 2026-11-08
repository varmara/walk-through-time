"""Check hand-written stories against Wikipedia and place each one on a building.

Stories live in stories/<city>.py (see CONTRIBUTING.md). For every entry:
  1. The Wikipedia article is fetched. Every string in `facts` must appear in it (case-insensitive).
     If one is missing, the entry is dropped: if the article does not say it, the story should not either.
  2. The entry is placed on a building, trying in order:
       at="osm:way/123"          an explicit OpenStreetMap outline
       the article's Wikidata item, tagged on a building outline in OpenStreetMap
       the item's Historic England list entry (P1216), matched in step s02
       the article's coordinates, inside (or within 15 m of) a building outline
       at="name:..." or the entry's name, matching a building name or a named place inside one
     Entries that cannot be placed are dropped.

Writes curated.json: {layers: [...], entries: [{layer, group, b, name, story, source, how}], dropped: [...]}.
"""
import importlib.util
import time
from pathlib import Path
from urllib.parse import quote

from .common import building_at, http, load, log, save


def stories(city_id):
    path = Path(f"stories/{city_id}.py")
    if not path.exists():
        return []
    spec = importlib.util.spec_from_file_location(f"stories_{city_id}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.CURATED


_cache = {}


def article(ref):
    """'en:Title' -> {text, url, qid, coords} or None."""
    if ref in _cache:
        return _cache[ref]
    lang, title = ref.split(":", 1)
    r = http(f"https://{lang}.wikipedia.org/w/api.php", params={
        "action": "query", "prop": "extracts|info|pageprops|coordinates", "explaintext": 1, "inprop": "url",
        "ppprop": "wikibase_item", "coprimary": "primary", "redirects": 1, "format": "json", "titles": title})
    page = next(iter(r["query"]["pages"].values()))
    time.sleep(0.5)
    if "missing" in page:
        _cache[ref] = None
        return None
    co = (page.get("coordinates") or [None])[0]
    _cache[ref] = {
        "text": (page.get("extract") or "").lower(),
        "url": page.get("fullurl") or f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
        "title": page.get("title", title),
        "qid": page.get("pageprops", {}).get("wikibase_item"),
        "coords": (co["lon"], co["lat"]) if co else None,
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
            try:
                arts[e["source"]] = article(e["source"])
            except Exception as ex:  # noqa: BLE001
                arts[e["source"]] = None
                log(f"    {e['source']}: {ex}")
    nhle = nhle_of(sorted({a["qid"] for a in arts.values() if a and a["qid"]}))

    for L in layers:
        kept = 0
        for e in L["entries"]:
            a = arts.get(e["source"])
            why = None
            if a is None:
                why = "Wikipedia article not found"
            else:
                missing = [f for f in e.get("facts", ()) if f.lower() not in a["text"]]
                if missing:
                    why = "article does not mention: " + ", ".join(missing)
            b = how = None
            if not why:
                at = e.get("at", "")
                if at.startswith("osm:") and at[4:] in by_osm:
                    b, how = by_osm[at[4:]], "OpenStreetMap outline"
                if b is None and a["qid"] in by_qid:
                    b, how = by_qid[a["qid"]], "Wikidata tag on the outline"
                if b is None:
                    for n in nhle.get(a["qid"], []):
                        if n in by_nhle:
                            b, how = by_nhle[n], "Historic England list entry"
                            break
                if b is None and a["coords"]:
                    b = building_at(buildings, *a["coords"], near=15)
                    how = "article coordinates" if b is not None else None
                if b is None:
                    key = norm(at[5:] if at.startswith("name:") else e["name"])
                    if key in names:
                        b, how = names[key], "name in OpenStreetMap"
                if b is None:
                    why = "could not place it on a building"
            if why:
                dropped.append({"layer": L["id"], "name": e["name"], "why": why})
                continue
            kept += 1
            entries.append({"layer": L["id"], "group": e.get("group", L["id"]), "b": b, "name": e["name"],
                            "story": e["story"], "how": how,
                            "source": {"title": a["title"], "url": a["url"]}})
        log(f"s05 {L['id']}: {kept}/{len(L['entries'])} stories kept")
    for d in dropped:
        log(f"    dropped {d['layer']} / {d['name']}: {d['why']}")
    meta = [{k: L[k] for k in ("id", "title", "intro") if k in L} for L in layers]
    save(city_id, "curated", {"layers": meta, "entries": entries, "dropped": dropped})
