"""Resolve every layer to what it contains, grouped into the sections of the page's Layers sheet.

Story and people layers come from step s04, rule layers from pipeline/layers.py, nature areas from
step s00_fetch_nature. Each layer has one or more groups; each group is one tickbox on the page.

Writes layers.json:
  meta    [{id, title, section, kind, intro, source?, groups: [{key, title, count, items?}]}]
          items: [[name, [building indexes]]], one per person or story, in first-seen order
          kind: stories | people | rule (buildings) or areas (nature, drawn on the ground)
  member  {building index: [group keys]}
  stories {building index: [{layer, text, source, place?}]}
  pins    [{x, y, name, layer, group, text, source?, place?}]  places that are not buildings (bridges,
          grounds) and plaques not on a building; layer items refer to them as "p<index>"
"""
import re
import urllib.parse

from .common import building_at, load, log, save, work
from .layers import LAYERS, Context
from .s04_curated import PEOPLE_GROUPS, people_group
from .s05_dates import info_for

NATURE = [
    ("nnr", "National Nature Reserves"),
    ("lnr", "Local Nature Reserves"),
    ("sssi", "Sites of Special Scientific Interest"),
    ("ancient", "Ancient woodland"),
    ("reserve", "Other nature reserves"),
    ("lws", "Local Wildlife Sites"),
]


def grouped(pairs):
    """[[building, name], ...] -> [[name, [buildings]]]: one entry per name, with every building it has."""
    out = {}
    for b, name in pairs:
        bs = out.setdefault(name, [])
        if b not in bs:
            bs.append(b)
    return [[n, bs] for n, bs in out.items()]


def plaque_label(text):
    """A short name for a plaque to a place or an event: 'The Dungeon Club 1964-1968 spiritual home…' -> 'The Dungeon
    Club'; 'Ibuprofen. In recognition…' -> 'Ibuprofen'; 'This was the site of the Moot Hall…' -> 'Moot Hall'."""
    t = re.sub(r"\s+", " ", text).strip(" “”\"'")
    m = re.search(r"\b(?:site (?:off?|occupied by)|stood) (?:the |a )?([A-Z][\w'’&-]*(?: (?:of|and|the|[A-Z][\w'’&-]*))*)", t)
    if m and len(m[1]) <= 45:
        return m[1].strip(" .,;")
    m = re.match(r"([A-Z][\w'’&. -]{2,45}?)(?= was | is | \d|[,.;:/(]| - )", t)
    if m:
        return m[1].strip()
    return t[:40].rsplit(" ", 1)[0] + "…" if len(t) > 40 else t


def c_words(city_id):
    """Words that tie an article to the city: its name and its districts (as for well-known residents)."""
    from .s04_residents import PLACES
    from .common import city
    return [city(city_id)["name"].lower()] + PLACES.get(city_id, {}).get("words", [])


def full_text(title):
    """The whole plain text of a Wikipedia article (one per request, the API's limit for whole articles)."""
    from .common import http
    try:
        r = http("https://en.wikipedia.org/w/api.php", params={"action": "query", "prop": "extracts", "explaintext": "1",
                                                               "redirects": "1", "format": "json", "titles": title})
        return next(iter(r["query"]["pages"].values())).get("extract") or ""
    except Exception:  # noqa: BLE001
        return ""


def about_people(want, words):
    """{name: {"text": the article's first sentences, "url", "title"}} for the People layer.
    An article comes from the entry's own source, or the plaque's or architect's Wikidata item; for a plaque with
    only a name, from Wikidata's search, used only when exactly one person of that name has an English article
    that mentions the city (two Thomas Hines, one of them from Nottingham)."""
    from .common import http
    from .s06_summaries import extracts, trim
    WD = "https://www.wikidata.org/w/api.php"
    by_qid = {n: h["qid"] for n, h in want.items() if "title" not in h and h.get("qid")}
    titles = {n: h["title"] for n, h in want.items() if "title" in h}
    qids = sorted(set(by_qid.values()))
    links = {}
    for i in range(0, len(qids), 50):
        try:
            r = http(WD, params={"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]), "props": "sitelinks",
                                 "sitefilter": "enwiki", "format": "json"})
        except Exception as e:  # noqa: BLE001
            log(f"    Wikidata sitelinks failed: {e}")
            continue
        for q, ent in r.get("entities", {}).items():
            t = ent.get("sitelinks", {}).get("enwiki", {}).get("title")
            if t:
                links[q] = t
    for n, q in by_qid.items():
        if q in links:
            titles[n] = links[q]
    # names alone (a plaque's subject): the person of that name, or alias ("George Gordon Byron"), whose English
    # article mentions the city, and the years on the plaque if it gives any
    guess = {}
    for n in [n for n, h in want.items() if "title" not in h and "qid" not in h and n not in titles
              and len(n.split()) >= 2][:400]:
        try:
            r = http(WD, params={"action": "wbsearchentities", "search": n, "language": "en", "type": "item",
                                 "limit": "10", "format": "json"})
            ids = [x["id"] for x in r.get("search", [])
                   if n.lower() in (x.get("label", "").lower(), x.get("match", {}).get("text", "").lower())]
            if not ids:
                continue
            r = http(WD, params={"action": "wbgetentities", "ids": "|".join(ids), "props": "claims|sitelinks",
                                 "sitefilter": "enwiki", "format": "json"})
            humans = [ent["sitelinks"]["enwiki"]["title"] for ent in r.get("entities", {}).values()
                      if ent.get("sitelinks", {}).get("enwiki")
                      and any(c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") == "Q5"
                              for c in ent.get("claims", {}).get("P31", []))]
            if humans:
                guess[n] = humans
        except Exception as e:  # noqa: BLE001
            log(f"    Wikidata search failed for {n}: {e}")
    intro = extracts(list(titles.values()) + [t for ts in guess.values() for t in ts])
    for n, ts in guess.items():
        years = set(re.findall(r"\b1[0-9]{3}\b", want[n].get("ctx", "")))
        ok = []
        for t in ts:
            body = full_text(t).lower()
            if any(w in body for w in words) and (not years or years & set(re.findall(r"\b1[0-9]{3}\b", body))):
                ok.append(t)
        if len(ok) == 1:
            titles[n] = ok[0]
    out = {}
    for n, t in titles.items():
        text = trim(intro.get(t) or "")
        if len(text) > 40:
            out[n] = {"text": text, "title": t,
                      "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(t.replace(" ", "_"))}
    return out


def main(city_id):
    ctx = Context(load(city_id, "buildings"), load(city_id, "listing"), load(city_id, "places"),
                  load(city_id, "monuments"))
    cur = load(city_id, "curated")
    meta, member, stories, pins = [], {}, {}, []

    def pin(x, y, name, layer_id, group, text, source=None, place=None, who=None, on=None):
        pins.append({"x": round(x, 6), "y": round(y, 6), "name": name, "layer": layer_id, "group": group, "text": text,
                     **({"source": source} if source else {}), **({"place": place} if place else {}),
                     **({"who": who} if who else {}), **({"on": on} if on is not None else {})})
        return f"p{len(pins) - 1}"

    def add(i, group, layer_id, story=None, source=None, place=None, who=None, pin_ref=None):
        member.setdefault(str(i), [])
        if group not in member[str(i)]:
            member[str(i)].append(group)
        if pin_ref:          # a plaque on this building: its words are stored once, on the plaque's pin
            stories.setdefault(str(i), []).append({"layer": layer_id, "pin": pin_ref, **({"who": who} if who else {})})
        elif story:
            stories.setdefault(str(i), []).append({"layer": layer_id, "text": story,
                                                   **({"source": source} if source else {}),
                                                   **({"place": place} if place else {}),
                                                   **({"who": who} if who else {}),
                                                   **({"pin": pin_ref} if pin_ref else {})})

    want = {}       # person's name -> what may find their Wikipedia article: {"title"} or {"qid"} or {} (by name)

    named = cur.get("wikipedia", {})       # the stories file names some people's articles itself

    def wiki_hint(name, source=None, qid=None, ctx=None):
        if not name:
            return
        h = want.setdefault(name, {})
        if name in named:
            h["title"] = named[name]
        if ctx:
            h["ctx"] = (h.get("ctx", "") + " " + ctx).strip()
        url = (source or {}).get("url") or ""
        if "wikipedia.org/wiki/" in url and "title" not in h:
            h["title"] = urllib.parse.unquote(url.rsplit("/wiki/", 1)[1]).replace("_", " ")
        elif qid and "qid" not in h:
            h["qid"] = qid

    for L in cur["layers"]:
        if L.get("kind") == "facts":    # 'Did you know' facts go on the cards (s07), not into a layer
            continue
        es = [e for e in cur["entries"] if e["layer"] == L["id"]]
        people = L.get("kind") == "people"
        for e in es:
            who = e["name"] if people else None
            if who:
                wiki_hint(who, e["source"])
            if e["b"] is None:   # not a building: a pin
                e["b"] = pin(*e["pin"], e["name"], L["id"], e["group"], e["story"], e["source"], e.get("place"), who)
            else:
                add(e["b"], e["group"], L["id"], e["story"], e["source"], e.get("place"), who)
        groups = L.get("groups") or [[L["id"], L["title"]]]
        meta.append({"id": L["id"], "title": L["title"], "intro": L.get("intro", ""),
                     "section": "People" if people else "Stories", "kind": "people" if people else "stories",
                     "groups": [{"key": k, "title": t,
                                 "count": len({e["b"] for e in es if e["group"] == k}),
                                 "items": [[e["b"], e["name"]] for e in es if e["group"] == k]} for k, t in groups]})
        if not people:
            for g in meta[-1]["groups"]:
                g["items"] = grouped(g["items"])

    # ---- People: hand-written entries (above), plus plaques and Wikidata architects, in the same groups
    people = next((m for m in meta if m["kind"] == "people"), None)
    if people is None:
        people = {"id": "people", "title": "People", "section": "People", "kind": "people", "groups": [],
                  "intro": "People connected with buildings on the map."}
        meta.append(people)
    people["intro"] = ("People connected with buildings on the map: who designed them, who lived, worked or played "
                       "in them, and who is remembered on their walls. Entries come from commemorative plaques "
                       "(Open Plaques), architects recorded in Wikidata, and hand-written entries checked against "
                       "Wikipedia and Historic England.")
    titles = {k: t for k, t, _ in PEOPLE_GROUPS} | {"events": "Plaques to events and places"}
    pg = {g["key"]: g for g in people["groups"]}

    def person(b, key, name, story, source, xy=None, qid=None, who=True, on=None):
        k = "people-" + key
        if k not in pg:
            pg[k] = {"key": k, "title": titles.get(key, key), "count": 0, "items": []}
        who = name if who else None
        if who:
            wiki_hint(name, source, qid, story)
        if b is None:   # a plaque: a pin where it hangs; on a building, the building is in the layer too and its card
            b = pin(*xy, name, "people", k, story, source, who=who, on=on)     # quotes the plaque
            if on is not None:
                add(on, k, "people", story, source, who=who, pin_ref=b)
        else:
            add(b, k, "people", story, source, who=who)
        pg[k]["items"].append([b, name])

    plaques = load(city_id, "plaques") if work(city_id, "plaques").exists() else []
    plaque_fix = cur.get("plaques", {})          # the stories file's corrections, by inscription or subject
    placed, names = 0, {}
    for p in plaques:
        b = building_at(ctx.buildings, p["x"], p["y"], near=12)
        if b is not None:
            placed += 1
        if b is not None and p.get("address") and (p.get("type") or "").lower() in ("man", "woman", "person"):
            names.setdefault(str(b), p["address"])     # a plaque to a place names that place, not this building
        text = (p.get("inscription") or p.get("title") or "").strip()
        fix = next((v for k2, v in plaque_fix.items() if text.lower().startswith(k2.lower())
                    or (p.get("subject") or "").lower() == k2.lower()), {})
        subject = fix.get("subject", p.get("subject"))
        if not subject and re.fullmatch(r"[A-Z][a-z]+(?: [A-Z][a-z]+){1,2}", text):
            subject = text                    # an inscription that is only a name: "Jesse Boot"
        kind = (fix.get("type") or p.get("type") or ("person" if subject else "thing")).lower()
        roles = [r.strip(' "').lower() for r in (p.get("roles") or "").split(",") if r.strip(' "')
                 and "order of" not in r.lower()]    # an OBE is not a military rank
        primary = (p.get("primary") or "").strip(' "').lower()
        # the primary role first (Bendigo was a prize-fighter before he was an evangelist), then the other roles,
        # then the plaque's own words
        key = fix.get("group") or ((people_group([primary]) if primary else None) or people_group(roles)
                                   or people_group([text.lower()]) or "other") \
            if kind in ("person", "man", "woman") else "events"
        if isinstance(p.get("year"), float):
            p["year"] = int(p["year"])
        story = f"{(p.get('colour') or '').capitalize() + ' p' if p.get('colour') else 'P'}laque" \
                f"{' put up in ' + str(p['year']) if p.get('year') else ''}{' by ' + p['org'] if p.get('org') else ''}: “{text}”"
        url = f"https://openplaques.org/plaques/{p['id']}" if p.get("id") else "https://openplaques.org/"
        src = {"title": "Open Plaques", "url": url, "kind": "Open Plaques"}
        if p.get("osm") and not p.get("id"):
            src = {"title": "OpenStreetMap", "url": f"https://www.openstreetmap.org/node/{p['osm']}", "kind": "Plaque mapped in"}
        label = fix.get("label") or subject or plaque_label(text) or "Plaque"
        # every plaque is a pin where it hangs, linked both ways to the building it is on (if any)
        person(None, key, label, story, src, xy=(p["x"], p["y"]), qid=p.get("qid"),
               who=bool(subject) and key != "events", on=b)
    log(f"s06 plaques: {len(plaques)} shown as pins ({placed} on or by a building)")

    # well-known residents found in their Wikipedia articles (s04_residents)
    residents = load(city_id, "residents") if work(city_id, "residents").exists() else []
    for r in residents:
        person(r["b"], r["group"], r["name"],
               f"Lived or worked at {r['address']}, according to Wikipedia: “{r['sentence']}” "
               f"(House numbers have sometimes changed since.)",
               {"title": r["title"], "url": r["url"], "kind": "Wikipedia"})
    log(f"s06 residents: {len(residents)} addresses of well-known people")

    wd = load(city_id, "wikidata")
    told = {(int(i), s2["source"]["title"]) for i, ss in stories.items() for s2 in ss if s2.get("source")}
    arch = 0
    for i, b in enumerate(ctx.buildings):
        info = info_for(b, i, wd, ctx.listing)
        if not info or not info.get("architect"):
            continue
        name = info["architect"]
        if any(t == name or name in t for (j, t) in told if j == i):
            continue   # a hand-written entry already tells this
        url = info.get("architectArticle") or (f"https://www.wikidata.org/wiki/{info['architectQid']}" if info.get("architectQid") else None)
        person(i, "architects", name, f"Designed by {name}, according to Wikidata.",
               {"title": name, "url": url, "kind": "Wikipedia" if info.get("architectArticle") else "Wikidata"} if url else None,
               qid=info.get("architectQid"))
        arch += 1
    log(f"s06 architects from Wikidata: {arch} buildings")
    order = [f"people-{k}" for k, _, _ in PEOPLE_GROUPS] + ["people-events"]
    for g in pg.values():
        g["count"] = len({b for b, _ in g["items"]})
        g["items"] = grouped(g["items"])
    people["groups"] = sorted(pg.values(), key=lambda g: order.index(g["key"]) if g["key"] in order else 99)

    inside = {}
    for p in ctx.places:   # a named place inside an unnamed outline names it (a pub, a shop)
        if p["b"] is not None and p["name"]:
            inside.setdefault(p["b"], p["name"])

    def bname(i):
        t = ctx.buildings[i]["tags"]
        return t.get("name") or inside.get(i) or names.get(str(i)) or t.get("addr:street") and \
            f"{t.get('addr:housenumber', '')} {t['addr:street']}".strip() or "Unnamed building"

    for L in LAYERS:
        res = L["fn"](ctx)
        for i, v in res.items():
            group, extra = v if isinstance(v, tuple) else (v, {})
            add(i, group, L["id"], extra.get("story"))
        groups = []
        for k, t in L["groups"]:
            members = [i for i, v in res.items() if (v[0] if isinstance(v, tuple) else v) == k]
            g = {"key": k, "title": t, "count": len(members)}
            if L.get("list"):   # names to tap in the Layers sheet, A to Z
                g["items"] = sorted(grouped([[i, bname(i)] for i in members]), key=lambda it: it[0].lower())
            groups.append(g)
        src = L.get("source")
        meta.append({"id": L["id"], "title": L["title"], "intro": L["intro"], "section": L.get("section", "Heritage"),
                     "kind": "rule", "groups": groups,
                     **({"source": {"title": src[0], "url": src[1]}} if src else {})})
        log(f"s06 {L['id']}: {len(res)} buildings")

    nature = load(city_id, "nature") if work(city_id, "nature").exists() else []
    groups = [{"key": k, "title": t, "count": sum(1 for f in nature if f["properties"]["t"] == k)} for k, t in NATURE]
    meta.append({"id": "nature", "title": "Nature", "section": "Nature", "kind": "areas",
                 "intro": "Protected and managed nature areas. National and Local Nature Reserves, Sites of Special "
                          "Scientific Interest and ancient woodland come from Natural England; other reserves from "
                          "OpenStreetMap. Local Wildlife Sites, places of local importance for wildlife such as stream "
                          "corridors and old railway lines, come from Nottingham City Council's map data "
                          "(© Nottingham City Council; contains Ordnance Survey data © Crown copyright).",
                 "source": {"title": "Natural England open data", "url": "https://naturalengland-defra.opendata.arcgis.com/"},
                 "groups": [g for g in groups if g["count"]]})
    log(f"s06 nature: {len(nature)} areas")

    # conservation areas follow the nature areas in the packaged areas collection: items refer to them as a<index>
    cons = load(city_id, "conservation") if work(city_id, "conservation").exists() else []
    if cons:
        meta.append({"id": "conservation", "title": "Conservation areas", "section": "Heritage", "kind": "areas",
                     "intro": "Areas of special architectural or historic interest, where the council manages change "
                              "to protect their character. The outlines are indicative; the council's own maps are "
                              "definitive.",
                     "source": {"title": "Historic England, conservation areas", "url": "https://historicengland.org.uk/listing/what-is-designation/local/conservation-areas/"},
                     "groups": [{"key": "conservation", "title": "Conservation areas", "count": len(cons),
                                 "items": sorted([[f["properties"]["name"], [f"a{len(nature) + j}"]] for j, f in enumerate(cons)],
                                                key=lambda x: x[0].lower())}]})
    log(f"s06 conservation areas: {len(cons)}")


    about = about_people(want, c_words(city_id))
    log(f"s06 people: Wikipedia articles for {len(about)} of {len(want)} people")
    save(city_id, "layers", {"meta": meta, "member": member, "stories": stories, "names": names, "pins": pins,
                             "people": about})
