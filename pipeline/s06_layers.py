"""Resolve every layer to the buildings it contains.

Rule layers come from pipeline/layers.py, story layers from step s04. Writes layers.json:
  meta    [{id, title, intro, kind, groups, source?, count}]  in display order: stories first, then rules
  member  {building index: [group keys]}
  stories {building index: [{layer, text, source}]}
"""
from .common import load, log, save
from .layers import LAYERS, Context


def main(city_id):
    ctx = Context(load(city_id, "buildings"), load(city_id, "listing"), load(city_id, "places"),
                  load(city_id, "monuments"))
    cur = load(city_id, "curated")
    meta, member, stories = [], {}, {}

    def add(i, group, layer_id, story=None, source=None):
        member.setdefault(str(i), [])
        if group not in member[str(i)]:
            member[str(i)].append(group)
        if story:
            stories.setdefault(str(i), []).append({"layer": layer_id, "text": story, **({"source": source} if source else {})})

    for L in cur["layers"]:
        es = [e for e in cur["entries"] if e["layer"] == L["id"]]
        for e in es:
            add(e["b"], e["group"], L["id"], e["story"], e["source"])
        meta.append({**L, "kind": "stories", "groups": [[L["id"], L["title"]]],
                     "count": len({e["b"] for e in es}),
                     "items": [[e["b"], e["name"]] for e in es]})

    for L in LAYERS:
        res = L["fn"](ctx)
        for i, v in res.items():
            group, extra = v if isinstance(v, tuple) else (v, {})
            add(i, group, L["id"], extra.get("story"))
        src = L.get("source")
        meta.append({"id": L["id"], "title": L["title"], "intro": L["intro"], "kind": "rule",
                     "groups": [list(g) for g in L["groups"]], "count": len(res),
                     **({"source": {"title": src[0], "url": src[1]}} if src else {})})
        log(f"s06 {L['id']}: {len(res)} buildings")

    save(city_id, "layers", {"meta": meta, "member": member, "stories": stories})
