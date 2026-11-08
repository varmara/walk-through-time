"""Names, dates, architects, photos and Wikipedia links from Wikidata.

Items are found two ways: the building's OpenStreetMap `wikidata` tag, and the Historic England
list entry number (Wikidata property P1216). Writes wikidata.json: {"Q123": info, "nhle:1234567": info}.
Licence: CC0.
"""
import re
import time

from .common import http, load, log, save

WDQS = "https://query.wikidata.org/sparql"
FIELDS = """
  OPTIONAL { ?item p:P571/psv:P571 ?iv . ?iv wikibase:timeValue ?inception ; wikibase:timePrecision ?prec . }
  OPTIONAL { ?item wdt:P18 ?image }
  OPTIONAL { ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> }
  OPTIONAL { ?item wdt:P84 ?architect . ?architect rdfs:label ?architectLabel . FILTER(LANG(?architectLabel) = "en")
             OPTIONAL { ?architectArticle schema:about ?architect ; schema:isPartOf <https://en.wikipedia.org/> } }
  OPTIONAL { ?item rdfs:label ?label . FILTER(LANG(?label) = "en") }"""


def sparql(q):
    return http(WDQS, {"query": q, "format": "json"}, accept="application/sparql-results+json")["results"]["bindings"]


def main(city_id):
    buildings = load(city_id, "buildings")
    listing = load(city_id, "listing")
    qids = sorted({b["tags"]["wikidata"] for b in buildings if re.match(r"^Q\d+$", b["tags"].get("wikidata", ""))})
    nhle = sorted({str(e["ListEntry"]) for es in listing.values() for e in es})
    out = {}

    def take(rows, key):
        for r in rows:
            k = key(r)
            prev = out.get(k, {})
            info = {
                "qid": r["item"]["value"].rsplit("/", 1)[-1],
                "label": prev.get("label") or r.get("label", {}).get("value"),
                "image": prev.get("image") or r.get("image", {}).get("value"),
                "article": prev.get("article") or r.get("article", {}).get("value"),
                "architect": prev.get("architect") or r.get("architectLabel", {}).get("value"),
                "architectQid": prev.get("architectQid") or (r["architect"]["value"].rsplit("/", 1)[-1] if "architect" in r else None),
                "architectArticle": prev.get("architectArticle") or r.get("architectArticle", {}).get("value"),
                "inception": prev.get("inception"), "prec": prev.get("prec"),
            }
            if "inception" in r and int(r["prec"]["value"]) > (prev.get("prec") or 0):
                info["inception"], info["prec"] = r["inception"]["value"], int(r["prec"]["value"])
            out[k] = info

    log(f"s03 Wikidata: {len(qids)} items by OSM tag, {len(nhle)} by list entry")
    try:
        for i in range(0, len(qids), 200):
            c = qids[i:i + 200]
            take(sparql(f"SELECT ?item ?inception ?prec ?image ?article ?architect ?architectLabel ?architectArticle ?label WHERE {{ "
                        f"VALUES ?item {{ {' '.join('wd:' + q for q in c)} }} {FIELDS} }}"),
                 lambda r: r["item"]["value"].rsplit("/", 1)[-1])
            time.sleep(1)
        for i in range(0, len(nhle), 200):
            c = nhle[i:i + 200]
            take(sparql(f"SELECT ?item ?nhle ?inception ?prec ?image ?article ?architect ?architectLabel ?architectArticle ?label WHERE {{ "
                        f"VALUES ?nhle {{ {' '.join(chr(34) + n + chr(34) for n in c)} }} ?item wdt:P1216 ?nhle . {FIELDS} }}"),
                 lambda r: "nhle:" + r["nhle"]["value"])
            time.sleep(1)
    except Exception as e:  # noqa: BLE001 - Wikidata is optional
        log(f"    Wikidata failed, continuing with what we have: {e}")
    save(city_id, "wikidata", out)
    log(f"    {len(out)} items")
