"""Resolve every layer to what it contains, grouped into the sections of the page's Layers sheet.

Story layers come from step s04, the People layer from s06_people, rule layers from pipeline/layers.py, nature
areas from step s00_fetch_nature. Each layer has one or more groups; each group is one tickbox on the page.

Writes layers.json:
  meta    [{id, title, section, kind, intro, source?, groups: [{key, title, count, items?}]}]
          items: [[name, [building indexes]]], one per person or story, in first-seen order
          kind: stories | people | rule (buildings) or areas (nature, drawn on the ground)
  member  {building index: [group keys]}
  stories {building index: [{layer, text, source, place?}]}
  pins    [{x, y, name, layer, group, text, source?, place?}]  places that are not buildings (bridges,
          grounds) and plaques not on a building; layer items refer to them as "p<index>"
"""
from .common import city, load, log, save, work
from .layerdata import Collector, grouped
from .layers import LAYERS, Context

NATURE = [
    ("nnr", "National Nature Reserves"),
    ("lnr", "Local Nature Reserves"),
    ("sssi", "Sites of Special Scientific Interest"),
    ("ancient", "Ancient woodland"),
    ("reserve", "Other nature reserves"),
    ("lws", "Local Wildlife Sites"),
]


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

    # ---- story layers (stories/<city>/NN-*.md); the People layer, from s06_people, where the stories put it
    for L in cur["layers"]:
        if L.get("kind") == "facts":    # 'Did you know' facts go on the cards (s07), not into a layer
            continue
        if L.get("kind") == "people":
            meta.append(ppl["meta"])
            continue
        es = [e for e in cur["entries"] if e["layer"] == L["id"]]
        for e in es:
            if e["b"] is None:   # not a building: a pin
                e["b"] = out.pin(*e["pin"], e["name"], L["id"], e["group"], e["story"], e["source"], e.get("place"))
            else:
                out.add(e["b"], e["group"], L["id"], e["story"], e["source"], e.get("place"))
        groups = L.get("groups") or [[L["id"], L["title"]]]
        meta.append({"id": L["id"], "title": L["title"], "intro": L.get("intro", ""), "section": "Stories",
                     "kind": "stories",
                     "groups": [{"key": k, "title": t, "count": len({e["b"] for e in es if e["group"] == k}),
                                 "items": grouped([[e["b"], e["name"]] for e in es if e["group"] == k])}
                                for k, t in groups]})
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

    for L in LAYERS:
        res = L["fn"](ctx)
        for i, v in res.items():
            group, extra = v if isinstance(v, tuple) else (v, {})
            out.add(i, group, L["id"], extra.get("story"), tpl=extra.get("tpl"), of=extra.get("of"))
        groups = []
        for k, t in L["groups"]:
            members = [i for i, v in res.items() if (v[0] if isinstance(v, tuple) else v) == k]
            g = {"key": k, "title": t, "count": len(members)}
            if L.get("list"):   # names to tap in the Layers sheet, A to Z
                g["items"] = sorted(grouped([[i, bname(i)] for i in members]), key=lambda it: it[0].lower())
            groups.append(g)
        src = L.get("source")
        if L.get("settings"):       # the source named in the city's settings (several councils: the first one's)
            ss = settings.get("sources", {}).get(L["settings"]) or []
            src = (ss[0].get("title") or ss[0]["publisher"], ss[0].get("page") or ss[0]["url"]) if ss else None
        meta.append({"id": L["id"], "title": L["title"], "intro": L["intro"], "section": L.get("section", "Heritage"),
                     "kind": "rule", "groups": groups,
                     **({"source": {"title": src[0], "url": src[1]}} if src else {})})
        log(f"s06 {L['id']}: {len(res)} buildings")

    nature = load(city_id, "nature") if work(city_id, "nature").exists() else []
    wild = [w for w in settings.get("sources", {}).get("wildlife", []) if w.get("credit")]
    groups = [{"key": k, "title": t, "count": sum(1 for f in nature if f["properties"]["t"] == k)} for k, t in NATURE]
    meta.append({"id": "nature", "title": "Nature", "section": "Nature", "kind": "areas",
                 "intro": "Protected and managed nature areas. National and Local Nature Reserves, Sites of Special "
                          "Scientific Interest and ancient woodland come from Natural England; other reserves from "
                          "OpenStreetMap. Local Wildlife Sites, places of local importance for wildlife such as stream "
                          "corridors and old railway lines, come from "
                          + (" and ".join(f"{w['publisher']}'s map data ({w['credit']})" for w in wild) or "councils' map data")
                          + ".",
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

    save(city_id, "layers", {"meta": meta, **out.json(), "names": names, "people": ppl["about"]})
