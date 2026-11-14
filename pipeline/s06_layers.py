"""Resolve every layer to what it contains, grouped into the sections of the page's Layers sheet.

Story layers come from step s04, the People layer from s06_people, the land's layers from s06_land, rule layers from pipeline/layers.py, nature
areas from step s00_fetch_nature, the layers for visitors and the lists (Mapping Museums, CAMRA) from
visitorlayers.py, and the other areas (conservation areas, parks and gardens, Article 4 areas, tree preservation
orders) from the s00 steps, in the order of layerdata.AREAS. Each layer has one or more groups; each group is one tickbox on the page.

Writes layers.json, and routes.json and basics.json (GeoJSON features for s07):
  meta    [{id, title, section, kind, intro, source?, groups: [{key, title, count, items?}]}]
          items: [[name, [building indexes]]], one per person or story, in first-seen order
          kind: stories | people | rule (buildings, and pins) | pins (pins only) | areas (drawn on the ground)
                | routes (lines, items r<index>) | points (drawn close up from the tiles)
  member  {building index: [group keys]}
  stories {building index: [{layer, text, source, place?}]}
  pins    [{x, y, name, layer, group, text, source?, place?}]  places that are not buildings (bridges,
          grounds) and plaques not on a building; layer items refer to them as "p<index>"
"""
from .common import city, load, log, save, sources, work
from .layerdata import AREAS, Collector, grouped, in_date_order, more_of, place_of
from .layers import LAYERS, Context
from .stories_md import slug
from .visitorlayers import museums, pub_heritage, visitor

NATURE = [
    ("nnr", "National Nature Reserves"),
    ("lnr", "Local Nature Reserves"),
    ("sssi", "Sites of Special Scientific Interest"),
    ("ancient", "Ancient woodland"),
    ("reserve", "Other nature reserves"),
    ("lws", "Local Wildlife Sites"),
]


AREA_LAYERS = {
    "conservation": {"id": "conservation", "title": "Conservation areas", "section": "Heritage",
                     "intro": "Areas of special architectural or historic interest, where the council manages change "
                              "to protect their character. The outlines are indicative; the council's own maps are "
                              "definitive.",
                     "source": {"title": "Historic England, conservation areas", "url": "https://historicengland.org.uk/listing/what-is-designation/local/conservation-areas/"}},
    "parks": {"id": "parkgarden", "title": "Registered parks and gardens", "section": "Heritage",
              "intro": "Designed landscapes of special historic interest on Historic England's Register of Parks and "
                       "Gardens: public parks, cemeteries and the grounds of great houses. Registration is a material "
                       "consideration in planning, as listing is for buildings.",
              "source": {"title": "Historic England, National Heritage List for England", "url": "https://historicengland.org.uk/listing/what-is-designation/registered-parks-and-gardens/"}},
    "article4": {"id": "article4", "title": "Article 4 areas", "section": "Heritage", "settings": "article4",
                 "intro": "Areas where the council has withdrawn some of the changes a householder could otherwise make "
                          "without planning permission, such as replacing windows and doors or removing front walls, to "
                          "keep the character of the streets. Only councils that publish them as map data are shown."},
    "tpo": {"id": "tpo", "title": "Tree preservation orders", "section": "Nature", "settings": "tpo",
            "intro": "Trees and groups of trees the council protects: cutting them down, topping or lopping them needs "
                     "its consent. Only councils that publish them as map data are shown."},
}


def main(city_id):
    ctx = Context(load(city_id, "buildings"), load(city_id, "listing"), load(city_id, "places"),
                  load(city_id, "monuments"),
                  load(city_id, "locallist") if work(city_id, "locallist").exists() else [])
    settings = city(city_id)
    cur = load(city_id, "curated")
    ppl = load(city_id, "people")            # s06_people: the People layer, its stories and plaque pins
    names = ppl["names"]
    out = Collector({"pins": ppl["pins"]})   # this step's pins follow the plaques'
    meta = []
    visitor_meta, routes, basics = visitor(city_id, ctx, out)

    # ---- story layers (stories/<city>/NN-*.md); the People layer, from s06_people, where the stories put it
    for L in cur["layers"]:
        if L.get("kind") == "facts":    # 'Did you know' facts go on the cards (s07), not into a layer
            continue
        if L.get("kind") == "people":
            meta.append(ppl["meta"])
            continue
        es = [e for e in cur["entries"] if e["layer"] == L["id"]]
        for e in es:
            if e["b"] is None:   # not a building: a pin (named for the place it marks, when the note gives one)
                e["b"] = out.pin(*e["pin"], e.get("where") or e["name"], L["id"], e["group"], e["story"], e["source"],
                                 e.get("place"), extra=more_of(e))
                e["_story"] = out.pins[-1]
            else:
                out.add(e["b"], e["group"], L["id"], e["story"], e["source"], e.get("place"), more=more_of(e))
                e["_story"] = out.stories[str(e["b"])][-1]
        groups = L.get("groups") or [[L["id"], L["title"]]]
        meta.append({"id": L["id"], "title": L["title"], "intro": L.get("intro", ""), "section": "Stories",
                     "kind": "stories",
                     "groups": [{"key": k, "title": t, "count": len({e["b"] for e in es if e["group"] == k}),
                                 "items": grouped([[e["b"], e["name"]] for e in es if e["group"] == k])}
                                for k, t in groups]})
    # a note's [[links]] to other stories are its "see also", as see: in a story file; to people, they stay links
    persons = {n for g in ppl["meta"]["groups"] if g["key"] != "people-events" for n, _ in g["items"]}
    persons |= set((cur.get("notes") or {}).get("people", {}))
    for e in cur["entries"]:
        more = [t for t in e.get("links", []) if t not in persons and t != e["name"] and t not in e.get("see", [])]
        if more:
            e["see"] = e.get("see", []) + more
    cross_links(cur["entries"], {L["id"] for L in cur["layers"] if L.get("kind") not in ("facts", "people")}, persons)
    link_people(cur, ppl)
    if not any(m["kind"] == "people" for m in meta):
        meta.append(ppl["meta"])
    # on a building's card, the story layers' stories first, then the People layer's, then the rest
    for i, ss in ppl["stories"].items():
        out.stories.setdefault(i, []).extend(ss)
    for i, gs in ppl["member"].items():
        mine = out.member.setdefault(i, [])
        mine += [g for g in gs if g not in mine]

    inside = {}
    for p in ctx.places:   # a named place inside an unnamed outline names it (a pub, a shop)
        if p["b"] is not None and p["name"]:
            inside.setdefault(p["b"], p["name"])

    def bname(i):
        t = ctx.buildings[i]["tags"]
        return t.get("name") or inside.get(i) or names.get(str(i)) or t.get("addr:street") and \
            f"{t.get('addr:housenumber', '')} {t['addr:street']}".strip() or "Unnamed building"

    # ---- topics (stories/<city>/topics/*.md): stories, people, plaques and buildings from any layer, on one subject
    topic_meta = topic_layers(cur.get("topics") or [], cur["entries"], ppl["meta"], out, ctx.buildings, bname,
                              {L["id"] for L in cur["layers"] if L.get("kind") not in ("facts", "people")})
    meta += topic_meta

    for L in LAYERS:
        if L.get("settings") and not sources(settings, L["settings"]):
            continue        # its council source is switched off, or the city has none
        res = L["fn"](ctx)
        for i, v in res.items():
            group, extra = v if isinstance(v, tuple) else (v, {})
            out.add(i, group, L["id"], extra.get("story"), tpl=extra.get("tpl"), of=extra.get("of"))
        groups = []
        for k, t in L["groups"]:
            members = [i for i, v in res.items() if (v[0] if isinstance(v, tuple) else v) == k]
            g = {"key": k, "title": t, "count": len(members)}
            if L.get("list"):   # names to tap in the Layers sheet, A to Z
                g["items"] = sorted(grouped([[i, bname(i)] for i in members], place_of(ctx.buildings, out.pins)),
                                    key=lambda it: it[0].lower())
            groups.append(g)
        src = L.get("source")
        if L.get("settings"):       # the source named in the city's settings (several councils: the first one's)
            ss = sources(settings, L["settings"])
            src = (ss[0].get("title") or ss[0]["publisher"], ss[0].get("page") or ss[0]["url"]) if ss else None
        meta.append({"id": L["id"], "title": L["title"], "intro": L["intro"], "section": L.get("section", "Heritage"),
                     "kind": "rule", "groups": groups,
                     **({"source": {"title": src[0], "url": src[1]}} if src else {})})
        log(f"s06 {L['id']}: {len(res)} buildings")

    nature = load(city_id, "nature") if work(city_id, "nature").exists() else []
    wild = [w for w in sources(settings, "wildlife") if w.get("credit")]
    groups = [{"key": k, "title": t, "count": sum(1 for f in nature if f["properties"]["t"] == k)} for k, t in NATURE]
    meta.append({"id": "nature", "title": "Nature", "section": "Nature", "kind": "areas",
                 "intro": "Protected and managed nature areas. National and Local Nature Reserves, Sites of Special "
                          "Scientific Interest and ancient woodland come from Natural England; other reserves from "
                          "OpenStreetMap."
                          + (" Local Wildlife Sites, places of local importance for wildlife such as stream corridors "
                             "and old railway lines, come from "
                             + " and ".join(f"{w['publisher']}'s map data ({w['credit']})" for w in wild) + "." if wild else ""),
                 "source": {"title": "Natural England open data", "url": "https://naturalengland-defra.opendata.arcgis.com/"},
                 "groups": [g for g in groups if g["count"]]})
    log(f"s06 nature: {len(nature)} areas")
    if work(city_id, "land").exists():     # brooks, woods, old railways and canals, historic sites… (s06_land)
        meta += load(city_id, "land")["meta"]

    # the other areas follow the nature areas in the packaged areas collection (layerdata.AREAS): items refer to
    # them as a<index>
    offset = {}
    n = 0
    for name in AREAS:
        offset[name] = n
        n += len(load(city_id, name)) if work(city_id, name).exists() else 0
    for name, L in AREA_LAYERS.items():
        feats = load(city_id, name) if work(city_id, name).exists() else []
        if not feats:
            continue
        items = sorted([[f["properties"]["name"], [f"a{offset[name] + j}"]] for j, f in enumerate(feats)], key=lambda x: x[0].lower())
        src = L.get("source")
        if L.get("settings"):
            ss = sources(settings, L["settings"])
            src = {"title": ss[0]["publisher"], "url": ss[0].get("page") or ss[0]["url"]} if ss else None
        meta.append({"id": L["id"], "title": L["title"], "section": L["section"], "kind": "areas", "intro": L["intro"],
                     **({"source": src} if src else {}),
                     "groups": [{"key": L["id"], "title": L["title"], "count": len(feats),
                                 **({"items": items} if len(items) <= 400 else {})}]})
        log(f"s06 {L['title'].lower()}: {len(feats)}")

    meta += visitor_meta + museums(city_id, ctx, out) + pub_heritage(city_id, ctx, out)
    dates = load(city_id, "dates") if work(city_id, "dates").exists() else {}
    in_date_order(meta, out.stories, out.pins, dates, ppl["about"])
    save(city_id, "routes", routes)
    save(city_id, "basics", basics)
    save(city_id, "layers", {"meta": meta, **out.json(), "names": names, "people": ppl["about"],
                             "unnamedPlaques": ppl.get("unnamed", []),
                             "architects": ppl.get("architects", {}),
                             "architectLinks": ppl.get("architectLinks", {})})


def cross_links(entries, story_layers, persons=()):
    """A story's "see also" (stories/<city>/*.md: see): each named story, found by its heading, or layer/heading,
    becomes [heading, where it is] on the story ("123" a building, "p4" a pin), which the card links to; a person
    (persons: the People layer's and person notes' names) becomes [name, "who"], opening their card."""
    placed = [e for e in entries if e["layer"] in story_layers and "_story" in e]
    by_name, by_full = {}, {}
    for e in placed:
        by_name.setdefault(e["name"].lower(), []).append(e)
        by_full[f"{e['layer']}/{e['name']}".lower()] = e
    for e in placed:
        see = []
        for name in e.get("see", []):
            hits = [by_full[name.lower()]] if name.lower() in by_full else by_name.get(name.lower(), [])
            hits = [h for h in hits if h is not e]
            if not hits and name in persons:
                see.append([name, "who"])
                continue
            if len(hits) != 1:
                log(f"    {e['layer']} / {e['name']}: see {name!r}: " + ("no such story" if not hits else
                    "more than one story of that name: write it as layer/heading"))
                continue
            ref = str(hits[0]["b"])
            if ref != str(e["b"]):          # another story on the same building is on the same card already
                see.append([hits[0]["name"], ref])
        if see:
            e["_story"]["see"] = see
    for e in entries:
        e.pop("_story", None)


def topic_layers(topics, entries, people, out, buildings, bname, story_layers):
    """The Topics section's layers: each topic's members found where the map has them (stories by heading, people
    by name, plaques by title, buildings by OpenStreetMap id), as items [name, [places], hint] (hint: the story's
    layer, or that it is a person, a plaque or a building, so a card shows the right story). Each building and
    pin is marked with the topic's groups, so ticking a topic shows them. Raises on a line that finds nothing or
    more than one thing, naming the file and line."""
    by_name, by_full = {}, {}
    for e in entries:
        if e["layer"] in story_layers and e.get("b") is not None:
            by_name.setdefault(e["name"].lower(), []).append(e)
            by_full.setdefault(f"{e['layer']}/{e['name']}".lower(), []).append(e)
    persons = {}
    for g in people["groups"]:
        if g["key"] == "people-events":
            continue
        for name, refs in g["items"]:
            rs = persons.setdefault(name.lower(), [name, []])[1]
            rs += [r for r in refs if r not in rs]
    plaques, osm = {}, {}
    for k, p in enumerate(out.pins):
        if p.get("layer") == "people":
            plaques.setdefault(p["name"].lower(), []).append(f"p{k}")
    for i, b in enumerate(buildings):
        osm[b["osm"]] = i
    problems, meta = [], []
    for T in topics:
        tid = T["id"]
        keys = {g: f"{tid}-{slug(g)}" for g in T["groups"]}
        items = {}
        for m in T["members"]:
            kind, name, where = m["kind"], m["name"], m["line"]
            if kind == "story":
                hits = by_full.get(name.lower()) or by_name.get(name.lower(), [])
                if len({e["layer"] for e in hits}) > 1:
                    problems.append(f"{where}: story {name!r} is in more than one layer "
                                    f"({', '.join(sorted({e['layer'] for e in hits}))}): write it as layer/heading")
                    continue
                if not hits:
                    problems.append(f"{where}: no story with the heading {name!r}")
                    continue
                item = [hits[0]["name"], list(dict.fromkeys(e["b"] for e in hits)), {"layer": hits[0]["layer"]}]
            elif kind == "person":
                hit = persons.get(name.lower())
                if not hit:
                    problems.append(f"{where}: no one called {name!r} in the People layer")
                    continue
                item = [hit[0], list(hit[1]), {"person": 1}]
            elif kind == "plaque":
                hits = plaques.get(name.lower(), [])
                if len(hits) != 1:
                    problems.append(f"{where}: " + (f"no plaque titled {name!r}" if not hits else
                                    f"{len(hits)} plaques are titled {name!r}: name the person instead (person:)"))
                    continue
                item = [out.pins[int(hits[0][1:])]["name"], hits, {"plaque": 1}]
            else:
                i = osm.get(name if "/" in name else "way/" + name)
                if i is None:
                    problems.append(f"{where}: no building {name!r} on the map (write it as way/123 or relation/123)")
                    continue
                item = [bname(i), [i], {"building": 1}]
            key = keys.get(m["group"], tid)
            items.setdefault(key, []).append(item)
            for r in item[1]:
                if isinstance(r, int):
                    mine = out.member.setdefault(str(r), [])
                    if key not in mine:
                        mine.append(key)
                elif isinstance(r, str) and r.startswith("p"):
                    p = out.pins[int(r[1:])]
                    p["T"] = (p.get("T") or ",") + key + "," if f",{key}," not in (p.get("T") or "") else p["T"]
        groups = [[keys[g], g] for g in T["groups"]] or [[tid, T["title"]]]
        if tid in items and T["groups"]:
            groups.insert(0, [tid, "Other"])
        meta.append({"id": tid, "title": T["title"], "intro": T.get("intro", ""), "section": "Topics", "kind": "topics",
                     "groups": [{"key": k, "title": t, "count": len({r for it in items.get(k, []) for r in it[1]}),
                                 "items": items.get(k, [])} for k, t in groups]})
        log(f"s06 topic {tid}: {sum(len(v) for v in items.values())} members")
    if problems:
        raise SystemExit("Topics (stories/<city>/topics/): fix these lines:\n  " + "\n  ".join(problems))
    return meta


def link_people(cur, ppl):
    """[[Links]] in stories and notes (pipeline/notes.py): each must name a note or someone in the People layer.
    A person linked from a story or event lists it on their card ("In these stories and events": about[name]
    ["linked"]: [[title, place ref or None, layer]]), and the story keeps the people it links (its "links"),
    which the graph draws. Raises naming the story and the link that finds nothing."""
    notes = set((cur.get("notes") or {}).get("names", []))
    persons = {n for g in ppl["meta"]["groups"] if g["key"] != "people-events" for n, _ in g["items"]}
    persons |= set((cur.get("notes") or {}).get("people", {}))
    known = notes | persons | set(ppl["about"]) | {e["name"] for e in cur["entries"]} \
        | {f"{e['layer']}/{e['name']}" for e in cur["entries"]}
    problems, about = [], ppl["about"]
    for e in cur["entries"]:
        for t in e.get("links", []):
            if t not in known:
                problems.append(f"{e['layer']} / {e['name']}: [[{t}]] is neither a note nor a person on the map")
            elif t in persons and t != e["name"]:
                ref = e.get("b") if e["layer"] != "people" else None
                row = [e["name"], ref, e["layer"]]
                mine = about.setdefault(t, {"title": t}).setdefault("linked", [])
                if row not in mine:
                    mine.append(row)
    if problems:
        raise SystemExit("Links that find nothing (write the note, or the name as the People layer has it):\n  "
                         + "\n  ".join(problems))
