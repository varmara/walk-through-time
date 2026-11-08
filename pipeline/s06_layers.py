"""Resolve every layer to what it contains, grouped into the sections of the page's Layers sheet.

Story and people layers come from step s04, rule layers from pipeline/layers.py, nature areas from
step s00_fetch_nature. Each layer has one or more groups; each group is one tickbox on the page.

Writes layers.json:
  meta    [{id, title, section, kind, intro, source?, groups: [{key, title, count, items?}]}]
          items: [[name, [building indexes]]], one per person or story, in first-seen order
          kind: stories | people | rule (buildings) or areas (nature, drawn on the ground)
  member  {building index: [group keys]}
  stories {building index: [{layer, text, source, place?}]}
"""
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
]


def grouped(pairs):
    """[[building, name], ...] -> [[name, [buildings]]]: one entry per name, with every building it has."""
    out = {}
    for b, name in pairs:
        bs = out.setdefault(name, [])
        if b not in bs:
            bs.append(b)
    return [[n, bs] for n, bs in out.items()]


def main(city_id):
    ctx = Context(load(city_id, "buildings"), load(city_id, "listing"), load(city_id, "places"),
                  load(city_id, "monuments"))
    cur = load(city_id, "curated")
    meta, member, stories = [], {}, {}

    def add(i, group, layer_id, story=None, source=None, place=None):
        member.setdefault(str(i), [])
        if group not in member[str(i)]:
            member[str(i)].append(group)
        if story:
            stories.setdefault(str(i), []).append({"layer": layer_id, "text": story,
                                                   **({"source": source} if source else {}),
                                                   **({"place": place} if place else {})})

    for L in cur["layers"]:
        es = [e for e in cur["entries"] if e["layer"] == L["id"]]
        for e in es:
            add(e["b"], e["group"], L["id"], e["story"], e["source"], e.get("place"))
        people = L.get("kind") == "people"
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

    def person(b, key, name, story, source):
        k = "people-" + key
        if k not in pg:
            pg[k] = {"key": k, "title": titles.get(key, key), "count": 0, "items": []}
        add(b, k, "people", story, source)
        pg[k]["items"].append([b, name])

    plaques = load(city_id, "plaques") if work(city_id, "plaques").exists() else []
    placed, names = 0, {}
    for p in plaques:
        b = building_at(ctx.buildings, p["x"], p["y"], near=12)
        if b is None:
            continue
        placed += 1
        if p.get("address"):
            names.setdefault(str(b), p["address"])
        kind = (p.get("type") or "person").lower()
        roles = [r.strip().lower() for r in (p.get("primary") or "").split(",") + (p.get("roles") or "").split(",") if r.strip()]
        # roles first; if they say nothing we recognise, the plaque's own words
        words = roles or []
        key = (people_group(words) or people_group([(p.get("inscription") or "").lower()]) or "other") \
            if kind in ("person", "man", "woman", "") else "events"
        text = (p.get("inscription") or p.get("title") or "").strip()
        if isinstance(p.get("year"), float):
            p["year"] = int(p["year"])
        story = f"{(p.get('colour') or '').capitalize() + ' p' if p.get('colour') else 'P'}laque" \
                f"{' put up in ' + str(p['year']) if p.get('year') else ''}{' by ' + p['org'] if p.get('org') else ''}: “{text}”"
        url = f"https://openplaques.org/plaques/{p['id']}" if p.get("id") else "https://openplaques.org/"
        label = p.get("subject") or (text[:40] + "…" if len(text) > 40 else text) or "Plaque"
        person(b, key, label, story,
               {"title": "Open Plaques", "url": url, "kind": "Open Plaques"})
    log(f"s06 plaques: {placed}/{len(plaques)} placed on a building")

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
               {"title": name, "url": url, "kind": "Wikipedia" if info.get("architectArticle") else "Wikidata"} if url else None)
        arch += 1
    log(f"s06 architects from Wikidata: {arch} buildings")
    order = [f"people-{k}" for k, _, _ in PEOPLE_GROUPS] + ["people-events"]
    for g in pg.values():
        g["count"] = len({b for b, _ in g["items"]})
        g["items"] = grouped(g["items"])
    people["groups"] = sorted(pg.values(), key=lambda g: order.index(g["key"]) if g["key"] in order else 99)

    for L in LAYERS:
        res = L["fn"](ctx)
        for i, v in res.items():
            group, extra = v if isinstance(v, tuple) else (v, {})
            add(i, group, L["id"], extra.get("story"))
        groups = []
        for k, t in L["groups"]:
            groups.append({"key": k, "title": t,
                           "count": sum(1 for v in res.values() if (v[0] if isinstance(v, tuple) else v) == k)})
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
                          "OpenStreetMap.",
                 "source": {"title": "Natural England open data", "url": "https://naturalengland-defra.opendata.arcgis.com/"},
                 "groups": [g for g in groups if g["count"]]})
    log(f"s06 nature: {len(nature)} areas")

    save(city_id, "layers", {"meta": meta, "member": member, "stories": stories, "names": names})
