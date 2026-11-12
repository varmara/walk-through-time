"""The People layer: who designed the buildings, who lived, worked or played in them, and who is remembered on
their walls.

From the hand-written People entries (stories/<city>/NN-people.md), commemorative plaques (s00_fetch_plaques: each
a pin where it hangs, linked both ways with the building it is on), well-known residents found in Wikipedia
(s04_residents) and architects recorded in Wikidata. Each person's card says who they were, from the opening of
their Wikipedia article.

Writes people.json: member, stories and pins (as layerdata.Collector holds them), meta (the People layer, with its
groups), names (addresses that person plaques give their building) and about ({name: {text, title, url}}).
s06_layers carries on from it.
"""
import re
import urllib.parse

from .common import city, load, log, save, work
from .geo import building_at
from .layerdata import Collector, grouped
from .texts import TEMPLATES
from .s04_curated import PEOPLE_GROUPS, people_group
from .s05_dates import info_for
from .architect_lists import architect_lists
from .s04_residents import wikitexts


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


def person_like(name):
    """A name that may be one person's: not "Mr Hallam", "W. Smith" or a firm ("CBP Architects", "Royston & Lund")."""
    if re.search(r"\b(?:Ltd|Limited|Architects?|Partners(?:hip)?|Associates|Group|Council|Practice)\b|&|\band\b", name):
        return False
    words = name.replace(".", ". ").split()
    full = [w for w in words if len(w.strip(".")) > 1 and w not in ("Mr.", "Mr", "Mrs", "Mrs.", "Sir", "JP")]
    return len(full) >= 2 or (len(full) == 1 and len(words) >= 2 and not re.match(r"Mrs?\.?$", words[0]) and
                                 sum(1 for w in words if len(w.strip(".")) == 1) >= 2)


def c_words(city_id):
    """Words that tie an article to the city: its name and its districts (as for well-known residents)."""
    c = city(city_id)
    return [c["name"].lower()] + c.get("residents", {}).get("words", [])


def full_text(title):
    """The whole plain text of a Wikipedia article (one per request, the API's limit for whole articles)."""
    from .web import http
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
    from .web import http
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
    buildings, listing = load(city_id, "buildings"), load(city_id, "listing")
    cur = load(city_id, "curated")
    out = Collector()
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

    # ---- hand-written entries (stories/<city>/NN-people.md)
    L = next((x for x in cur["layers"] if x.get("kind") == "people"), None)
    people = {"id": "people", "title": "People", "section": "People", "kind": "people", "groups": []}
    if L:
        es = [e for e in cur["entries"] if e["layer"] == L["id"]]
        for e in es:
            wiki_hint(e["name"], e["source"])
            if e["b"] is None:   # not a building: a pin
                e["b"] = out.pin(*e["pin"], e["name"], L["id"], e["group"], e["story"], e["source"], e.get("place"), e["name"])
            else:
                out.add(e["b"], e["group"], L["id"], e["story"], e["source"], e.get("place"), e["name"])
        groups = L.get("groups") or [[L["id"], L["title"]]]
        people = {"id": L["id"], "title": L["title"], "section": "People", "kind": "people",
                  "groups": [{"key": k, "title": t, "count": len({e["b"] for e in es if e["group"] == k}),
                              "items": [[e["b"], e["name"]] for e in es if e["group"] == k]} for k, t in groups]}
    people["intro"] = ("People connected with buildings on the map: who designed them, who lived, worked or played "
                       "in them, and who is remembered on their walls. Entries come from commemorative plaques "
                       "(Open Plaques), architects recorded in Wikidata, and hand-written entries checked against "
                       "Wikipedia and Historic England.")
    titles = {k: t for k, t, _ in PEOPLE_GROUPS} | {"events": "Plaques to events and places"}
    pg = {g["key"]: g for g in people["groups"]}

    def person(b, key, name, story, source, xy=None, qid=None, who=True, on=None, tpl=None):
        k = "people-" + key
        if k not in pg:
            pg[k] = {"key": k, "title": titles.get(key, key), "count": 0, "items": []}
        who = name if who else None
        if who:
            wiki_hint(name, source, qid, story)
        if b is None:   # a plaque: a pin where it hangs; on a building, the building is in the layer too and its card
            b = out.pin(*xy, name, "people", k, story, source, who=who, on=on)     # quotes the plaque
            if on is not None:
                out.add(on, k, "people", story, source, who=who, pin_ref=b)
        else:
            out.add(b, k, "people", story, source, who=who or (name if tpl else None), tpl=tpl)
        pg[k]["items"].append([b, name])

    plaques = load(city_id, "plaques") if work(city_id, "plaques").exists() else []
    plaque_fix = cur.get("plaques", {})          # the stories file's corrections, by inscription or subject
    placed, names = 0, {}
    for p in plaques:
        b = building_at(buildings, p["x"], p["y"], near=12)
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

    # ---- architects: from Wikidata (P84), from a story's `architect:` line, from a Wikipedia article's table of an
    # estate's houses (architect_lists.py), or from OpenStreetMap's architect tag, in that order; each building's are saved for its card (s07), and they join the People layer, so their names
    # link to their other buildings
    wd = load(city_id, "wikidata")
    # a hand-written entry, a resident's article or another story already telling who designed it
    told = {(int(i), s2["source"]["title"]) for i, ss in out.stories.items() for s2 in ss if s2.get("source")}
    told |= {(e["b"], e["source"]["title"]) for e in cur["entries"]
             if isinstance(e.get("b"), int) and e.get("source") and e["layer"] != "facts"}
    fixes = cur.get("architects", {})            # stories/<city>/architects.md: OpenStreetMap's names, made plain
    # an architect with no article: a page about them that is not Wikipedia, by either name (Wikidata's too)
    links = {n: f["source"] for raw, f in fixes.items() if f.get("source") for n in (raw, f.get("name") or raw)}

    def plain(raw):
        fix = fixes.get(raw, {})
        name = fix.get("name") or raw
        if fix.get("article"):
            named.setdefault(name, fix["article"])
        return name, bool(fix)
    listed = architect_lists(city(city_id), buildings, load(city_id, "conservation"), wikitexts)
    by_story = {}
    for e in cur["entries"]:
        for name, title in e.get("architect", []):
            src = {"title": title, "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
                   "kind": "Wikipedia"} if title else None
            wiki_hint(name, src)               # on a pin too: the story's words then link to the article
            if isinstance(e.get("b"), int) and name not in by_story.get(e["b"], []):
                by_story.setdefault(e["b"], []).append(name)
    arch, counts = {}, {"wikidata": 0, "story": 0, "list": 0, "osm": 0}
    for i, b in enumerate(buildings):
        info = info_for(b, i, wd, listing) or {}
        if info.get("architect"):
            name = info["architect"]
            arch[str(i)] = [[name, 0]]
            counts["wikidata"] += 1
            if any(t == name or name in t for (j, t) in told if j == i):
                continue   # a hand-written entry already tells this
            url = info.get("architectArticle") or (f"https://www.wikidata.org/wiki/{info['architectQid']}" if info.get("architectQid") else None)
            person(i, "architects", name, TEMPLATES["architect"].format(who=name), tpl="architect", source=
                   {"title": name, "url": url, "kind": "Wikipedia" if info.get("architectArticle") else "Wikidata"} if url else None,
                   qid=info.get("architectQid"))
        elif i in by_story:
            arch[str(i)] = [[n, 0] for n in by_story[i]]
            counts["story"] += 1
            for name in by_story[i]:             # the story tells it: in the layer, with no words of its own
                out.add(i, "people-architects", "people")
                pg.setdefault("people-architects", {"key": "people-architects", "title": titles["architects"],
                                                    "count": 0, "items": []})["items"].append([i, name])
        elif i in listed:
            arch[str(i)] = []
            counts["list"] += 1
            for raw, unsure, article in listed[i]:
                name, fixed = plain(raw)
                arch[str(i)].append([name, int(unsure)])
                if not person_like(name) and not fixed:
                    continue
                url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(article.replace(" ", "_"))
                tpl = "architect-list-unsure" if unsure else "architect-list"
                person(i, "architects", name, TEMPLATES[tpl].format(who=name), tpl=tpl, source={"title": article, "url": url, "kind": "Wikipedia"})
        elif b["tags"].get("architect"):
            t = b["tags"]
            qids = [q.strip() for q in (t.get("architect:wikidata") or "").split(";")]
            found = []
            for k, raw in enumerate(x.strip() for x in t["architect"].split(";")):
                if not raw:
                    continue
                name, fixed = plain(raw)
                found.append([name, 0])
                if not person_like(name) and not fixed:
                    continue                     # "Mr Hallam", "CBP Architects": on the card, not in the layer
                qid = qids[k] if k < len(qids) and re.fullmatch(r"Q\d+", qids[k]) else None
                person(i, "architects", name, TEMPLATES["architect-osm"].format(who=name), tpl="architect-osm", qid=qid,
                       source={"title": "OpenStreetMap", "url": f"https://www.openstreetmap.org/{b['osm']}", "kind": "OpenStreetMap"})
            if found:
                arch[str(i)] = found
                counts["osm"] += 1
    log(f"s06 architects: {counts['wikidata']} buildings from Wikidata, {counts['story']} from the stories, "
        f"{counts['list']} from Wikipedia's lists, {counts['osm']} from OpenStreetMap")
    order = [f"people-{k}" for k, _, _ in PEOPLE_GROUPS] + ["people-events"]
    for g in pg.values():
        g["count"] = len({b for b, _ in g["items"]})
        g["items"] = grouped(g["items"])
    people["groups"] = sorted(pg.values(), key=lambda g: order.index(g["key"]) if g["key"] in order else 99)

    about = about_people(want, c_words(city_id))
    log(f"s06 people: Wikipedia articles for {len(about)} of {len(want)} people")
    missing = sorted({n for ns in arch.values() for n, _ in ns if n not in about and n not in links and person_like(n)})
    if missing:
        log(f"    architects with no Wikipedia article found: {', '.join(missing)}")
    save(city_id, "people", {**out.json(), "meta": people, "names": names, "about": about, "architects": arch,
                            "architectLinks": links})
