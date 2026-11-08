"""Resolve every layer to what it contains, grouped into the sections of the page's Layers sheet.

Story and people layers come from step s04, rule layers from pipeline/layers.py, nature areas from
step s00_fetch_nature. Each layer has one or more groups; each group is one tickbox on the page.

Writes layers.json:
  meta    [{id, title, section, kind, intro, source?, groups: [{key, title, count, items?}]}]
          kind: stories | people | rule (buildings) or areas (nature, drawn on the ground)
  member  {building index: [group keys]}
  stories {building index: [{layer, text, source, place?}]}
"""
from .common import load, log, save, work
from .layers import LAYERS, Context

NATURE = [
    ("nnr", "National Nature Reserves"),
    ("lnr", "Local Nature Reserves"),
    ("sssi", "Sites of Special Scientific Interest"),
    ("ancient", "Ancient woodland"),
    ("reserve", "Other nature reserves"),
]


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

    save(city_id, "layers", {"meta": meta, "member": member, "stories": stories})
