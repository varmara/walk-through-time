"""Well-known residents: people whose English Wikipedia article names the address they lived, worked or died at.

1. Wikidata: people born, died, lived or worked in the city (or a place inside it), with an English article.
2. Their article's wikitext is searched, sentence by sentence, for a house number and a street of the city
   ("lived at 12 Park Terrace"), in a sentence about living, moving, dying, working or a house, and naming the
   city or one of its districts in that sentence or the one before (many street names exist in every town).
3. The address is matched to a building through OpenStreetMap addresses (exact house number and street).
The sentence is kept as the quote; house numbers can have changed since the person lived there, so the card says so.

Writes work/<city>/residents.json: [{name, qid, title, url, sentence, address, b, group}].
"""
import re
import urllib.parse

from .common import http, load, log, save
from .s04_curated import occupations, people_group

WIKI = "https://en.wikipedia.org/w/api.php"
WDQS = "https://query.wikidata.org/sparql"
# per city: Wikidata items of the city (places inside them count too, through 'located in'), other place names,
# and words that place a sentence in the city
PLACES = {
    "nottingham": {"items": ["Q41262"], "labels": ["West Bridgford", "Wilford", "Clifton"],
                   "words": ["nottingham", "west bridgford", "wilford", "clifton", "sneinton", "the meadows",
                             "lace market", "the park estate", "the park, nottingham", "lenton", "radford", "hockley"]},
}
VERBS = re.compile(r"\b(lived|lives|living|born|died|home|house|resided|residence|moved|grew up|lodged|lodgings|"
                   r"rented|bought|stayed|settled|workshop|studio|practice|shop|premises|address)\b", re.I)
TYPES = (r"Street|Road|Gate|Lane|Place|Terrace|Square|Row|Avenue|Drive|Crescent|Walk|Hill|Grove|Park|Close|Way|"
         r"Pavement|Parade|Rise|Mount|Yard|Court|Gardens|Boulevard|Embankment|Side")
NOT_PLACES = {"england", "nottinghamshire", "uk", "united kingdom", "and", "where", "which", "in", "the", "he", "she",
              "they", "his", "her", "until", "before", "after", "from", "with", "near", "on", "at"}
ADDRESS = re.compile(r"\b(\d{1,3})[a-z]?(?:\s*(?:-|–|and|&)\s*\d{1,3}[a-z]?)?,?\s+((?:St\.?\s|[A-Z][a-z'’]+\s){0,3}(?:" + TYPES + r"))\b")


def strip_wikitext(t, keep_lists=False):
    t = re.sub(r"<ref[^>/]*/>", " ", t)
    t = re.sub(r"<ref[^>]*>.*?</ref>", " ", t, flags=re.S)
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    for _ in range(4):
        t = re.sub(r"\{\{[^{}]*\}\}", " ", t)
    t = re.sub(r"\[\[(?:File|Image|Category):[^\]]*\]\]", " ", t)
    t = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[\[([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[https?://\S+\s([^\]]*)\]", r"\1", t)
    t = re.sub(r"'{2,}", "", t)
    t = re.sub(r"<[^>]+>", " ", t)
    if keep_lists:          # "* Iremonger: ... landlord of the Ferry Inn until his death in 1958" -> its text
        t = re.sub(r"^[*#:;]+\s*", "", t, flags=re.M)
    t = re.sub(r"^[=*#:;|!{].*$", " ", t, flags=re.M)     # headings, lists, tables
    return re.sub(r"\s+", " ", t)


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"“])", text) if s.strip()]


def people(cfg):
    places = " ".join("wd:" + q for q in cfg["items"])
    labels = " ".join(f'"{x}"@en' for x in cfg["labels"])
    q = f"""SELECT DISTINCT ?item ?itemLabel ?article WHERE {{
      VALUES ?prop {{ wdt:P19 wdt:P20 wdt:P551 wdt:P937 }}
      {{ VALUES ?city {{ {places} }} ?place wdt:P131* ?city . }} UNION {{ VALUES ?l {{ {labels} }} ?place rdfs:label ?l . ?place wdt:P17 wd:Q145 . }}
      ?item ?prop ?place . ?item wdt:P31 wd:Q5 .
      ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }}"""
    rows = http(WDQS, {"format": "json", "query": q}, accept="application/sparql-results+json", timeout=300)["results"]["bindings"]
    out = {}
    for r in rows:
        qid = r["item"]["value"].rsplit("/", 1)[-1]
        title = urllib.parse.unquote(r["article"]["value"].rsplit("/wiki/", 1)[1]).replace("_", " ")
        out[qid] = {"qid": qid, "name": r.get("itemLabel", {}).get("value") or title, "title": title}
    return list(out.values())


def wikitexts(titles):
    got = {}
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        try:
            r = http(WIKI, params={"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
                                   "format": "json", "formatversion": "2", "redirects": "1", "titles": "|".join(chunk)})
        except Exception as e:  # noqa: BLE001
            log(f"    wikitext failed for {len(chunk)} articles: {e}")
            continue
        q = r.get("query", {})
        back = {}
        for n in q.get("normalized", []) + q.get("redirects", []):
            back[n["to"]] = back.get(n["from"], n["from"])
        for pg in q.get("pages", []):
            revs = pg.get("revisions") or []
            if revs:
                got[back.get(pg["title"], pg["title"])] = revs[0]["slots"]["main"]["content"]
    return got


def main(city_id):
    cfg = PLACES.get(city_id)
    if not cfg:
        save(city_id, "residents", [])
        return
    buildings, places = load(city_id, "buildings"), load(city_id, "places")
    # addresses on outlines, and on named points inside them
    addr = {}
    for i, b in enumerate(buildings):
        t = b["tags"]
        if t.get("addr:street") and t.get("addr:housenumber"):
            for n in re.split(r"[;,]|\s*-\s*", t["addr:housenumber"]):
                if n.strip():
                    addr.setdefault((n.strip().lower(), t["addr:street"].lower()), i)
    for p in places:
        t = p["tags"]
        if p["b"] is not None and t.get("addr:street") and t.get("addr:housenumber"):
            addr.setdefault((t["addr:housenumber"].strip().lower(), t["addr:street"].lower()), p["b"])
    streets = {s for _, s in addr}
    log(f"s04 residents: {len(addr)} addresses on {len({v for v in addr.values()})} buildings, {len(streets)} streets")

    try:
        ppl = people(cfg)
    except Exception as e:  # noqa: BLE001
        log(f"    Wikidata people query failed, no residents this run: {e}")
        save(city_id, "residents", [])
        return
    texts = wikitexts([p["title"] for p in ppl])
    log(f"    {len(ppl)} people tied to the city in Wikidata; {len(texts)} articles read")

    found = []
    for p in ppl:
        text = texts.get(p["title"])
        if not text:
            continue
        ss = sentences(strip_wikitext(text))
        seen = set()
        for k, s in enumerate(ss):
            if len(s) > 400 or not VERBS.search(s):
                continue
            here = (s + " " + (ss[k - 1] if k else "")).lower()
            if not any(w in here for w in cfg["words"]):
                continue
            for m in ADDRESS.finditer(s):
                num, street = m[1], m[2].replace("St. ", "St ").strip()
                key = (num.lower(), street.lower())
                after = re.match(r",?\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", s[m.end():])
                if after and after[1].lower() not in cfg["words"] and after[1].lower() not in NOT_PLACES:
                    continue       # "6 Lilac Grove, Beeston": the same street name in another town
                b = addr.get(key)
                if b is None and street.lower().startswith("st "):
                    b = addr.get((num.lower(), "saint " + street.lower()[3:]))
                if b is None or b in seen:
                    continue
                seen.add(b)
                found.append({"name": p["name"], "qid": p["qid"], "title": p["title"],
                              "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(p["title"].replace(" ", "_")),
                              "sentence": s, "address": f"{num} {street}", "b": b})
    try:
        occ = occupations(sorted({f["qid"] for f in found}))
    except Exception as e:  # noqa: BLE001
        log(f"    occupations failed: {e}")
        occ = {}
    for f in found:
        f["group"] = people_group(occ.get(f["qid"], [])) or "other"
    save(city_id, "residents", found)
    log(f"    {len(found)} addresses of {len({f['qid'] for f in found})} people matched to buildings")
    for f in found[:40]:
        log(f"      {f['name']} — {f['address']}: {f['sentence'][:110]}")
