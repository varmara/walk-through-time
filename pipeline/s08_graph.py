"""The graph (data/<city>-graph.json): people and story themes, linked to the places where a checked text ties them.

Nodes: people (from the People layer, by kind: architects, writers...), story themes (each story layer) and places
(buildings "b<i>", pins "p<i>", areas "a<i>", as the map numbers them, so the map can open them).
Links keep their evidence, the story text and its source. A person named in another place's story (Thomas Adams in
the Lace Market story of a warehouse Hine designed) is linked there too, as in a note that mentions another note.
"""
import json
from pathlib import Path

from .common import log


def main(city_id):
    data = json.loads(Path(f"data/{city_id}.json").read_text())
    feats, pins, areas = data["buildings"]["features"], data["pins"]["features"], data["nature"]["features"]

    def ref(x):
        return f"b{x}" if isinstance(x, int) else x

    def place_info(r):
        if r[0] == "b":
            p = feats[int(r[1:])]["properties"]
            return {"label": p.get("name") or p.get("listName") or "Unnamed building", "year": p.get("y"), "f": p.get("f")}, p.get("stories") or []
        if r[0] == "p":
            p = pins[int(r[1:])]["properties"]
            return {"label": p["name"]}, [{"layer": p.get("layer"), "text": p.get("text"), "source": p.get("source")}]
        p = areas[int(r[1:])]["properties"]
        return {"label": p.get("name")}, []

    nodes, links, seen = {}, [], set()

    def link(a, b, text=None, src=None, how="story"):
        key = (a, b)
        if key in seen:
            return
        seen.add(key)
        links.append({"s": a, "t": b, "text": text, "src": src, "how": how})

    people = []   # (node id, name)
    for L in data["layers"]:
        if L.get("kind") == "stories" and L["id"] != "people":
            tid = f"t:{L['id']}"
            nodes[tid] = {"id": tid, "label": L["title"], "type": "theme"}
            for g in L["groups"]:
                for name, refs in g["items"]:
                    for x in refs:
                        r = ref(x)
                        info, stories = place_info(r)
                        nodes.setdefault(r, {"id": r, "type": "place", **info})
                        st = next((s for s in stories if s.get("layer") == L["id"]), None)
                        link(tid, r, st and st["text"], st and st.get("source"))
        if L["id"] == "people":
            for g in L["groups"]:
                for name, refs in g["items"]:
                    eid = f"e:{name}"
                    nodes.setdefault(eid, {"id": eid, "label": name, "type": g["key"].replace("people-", "")})
                    people.append((eid, name))
                    last = name.split()[-1].lower()
                    for x in refs:
                        r = ref(x)
                        info, stories = place_info(r)
                        nodes.setdefault(r, {"id": r, "type": "place", **info})
                        ps = [s for s in stories if s.get("layer") in ("people", None) or str(s.get("layer", "")).startswith("people")]
                        st = (next((s for s in ps if name.lower() in (s.get("text") or "").lower()
                                    or name.lower() in ((s.get("source") or {}).get("title") or "").lower()), None)
                              or next((s for s in ps if last in (s.get("text") or "").lower()), None))
                        link(eid, r, st and st["text"], st and st.get("source"))

    # mentions: a person's full name in the story of a place they are not yet linked to
    texts = []
    for r, n in nodes.items():
        if n["type"] == "place":
            texts += [(r, s) for s in place_info(r)[1] if s.get("text")]
    for eid, name in people:
        if len(name.split()) < 2:
            continue
        for r, s in texts:
            if name in s["text"]:
                link(eid, r, s["text"], s.get("source"), how="mention")

    out = {"nodes": list(nodes.values()), "links": links}
    Path(f"data/{city_id}-graph.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    kinds = {}
    for n in nodes.values():
        kinds[n["type"]] = kinds.get(n["type"], 0) + 1
    log(f"s08 graph: {len(nodes)} nodes {kinds}, {len(links)} links "
        f"({sum(l['how'] == 'mention' for l in links)} from mentions)")
