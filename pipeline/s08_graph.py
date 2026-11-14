"""The graph (data/<city>-graph.json): people and story themes, linked to the places where a checked text ties them.

Nodes: people (from the People layer, by kind: architects, writers...), story themes (each story layer) and places
(buildings "b<i>", pins "p<i>", areas "a<i>", as the map numbers them, so the map can open them).
Links keep their evidence, the story text and its source. A person named in another place's story (Thomas Adams in
the Lace Market story of a warehouse Hine designed) is linked there too, as in a note that mentions another note.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

from .common import load, log
from .texts import story_text


def main(city_id):
    data = load(city_id, "package")
    feats, pins, areas = data["buildings"]["features"], data["pins"]["features"], data["nature"]["features"]

    def ref(x):
        return f"b{x}" if isinstance(x, int) else x

    def place_info(r):
        if r[0] == "b":
            p = feats[int(r[1:])]["properties"]
            return {"label": p.get("name") or p.get("listName") or "Unnamed building", "year": p.get("y"), "f": p.get("f")}, \
                [story_text(st, pins, data.get("templates")) for st in p.get("stories") or []]
        if r[0] == "p":
            p = pins[int(r[1:])]["properties"]
            return {"label": p["name"]}, [{"layer": p.get("layer"), "text": p.get("text"), "source": p.get("source"),
                                           "links": p.get("links")}]
        p = areas[int(r[1:])]["properties"]
        return {"label": p.get("name")}, []

    nodes, links, seen = {}, [], set()

    def link(a, b, text=None, src=None, how="story"):
        key = (a, b)
        if key in seen:
            return
        seen.add(key)
        text = re.sub(r"\[\^[\w-]+\]", "", text) if text else text      # (a note's footnote marks)
        links.append({"s": a, "t": b, "text": text, "src": src, "how": how})

    people = []   # (node id, name)
    topic_people = []   # (topic node, person node): a person in a topic
    for L in data["layers"]:
        if L.get("kind") in ("stories", "topics") and L["id"] != "people":
            # a story layer or a topic: linked to its places, and a topic to the people in it
            tid = f"t:{L['id']}"
            nodes[tid] = {"id": tid, "label": L["title"], "type": "theme"}
            for g in L["groups"]:
                for name, refs, *hint in g["items"]:
                    hint = hint[0] if hint else {}
                    if hint.get("person"):
                        topic_people.append((tid, f"e:{name}"))
                        continue
                    for x in refs:
                        r = ref(x)
                        info, stories = place_info(r)
                        nodes.setdefault(r, {"id": r, "type": "place", **info})
                        want = hint.get("layer") or L["id"]
                        st = next((s for s in stories if s.get("layer") == want), None) or \
                            (next((s for s in stories if s.get("text")), None) if L["kind"] == "topics" else None)
                        link(tid, r, st and st.get("text"), st and st.get("source"))
        if L["id"] == "people":
            for g in L["groups"]:
                for name, refs in g["items"]:
                    eid = f"e:{name}"
                    nodes.setdefault(eid, {"id": eid, "label": name, "type": g["key"].replace("people-", ""),
                                           **({"about": brief(data["people"][name])} if name in data.get("people", {}) else {})})
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
                        link(eid, r, st and st.get("text"), st and st.get("source"))

    # people with a note but no place of their own (W. G. Grace in the first Test): a point, for their links
    for name, info in (data.get("people") or {}).items():
        if info.get("linked") and f"e:{name}" not in nodes:
            nodes[f"e:{name}"] = {"id": f"e:{name}", "label": name, "type": "other", "about": brief(info)}
    for tid, eid in topic_people:
        if eid in nodes:
            link(tid, eid, how="topic")

    # [[links]] in stories and events (pipeline/notes.py): the person, to the place where the story is told
    for r, n in list(nodes.items()):
        if n["type"] != "place":
            continue
        for s in place_info(r)[1]:
            for t in s.get("links") or []:
                if f"e:{t}" in nodes:
                    link(f"e:{t}", r, s.get("text"), s.get("source"), how="link")

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
    lay_out(f"data/{city_id}-graph.json")
    kinds = {}
    for n in nodes.values():
        kinds[n["type"]] = kinds.get(n["type"], 0) + 1
    log(f"s08 graph: {len(nodes)} nodes {kinds}, {len(links)} links "
        f"({sum(l['how'] == 'mention' for l in links)} from mentions)")


def brief(info):
    """What the graph shows of a person: who they were (Wikipedia's opening, or their note's own text) and when."""
    out = {k: info[k] for k in ("text", "title", "url", "life") if info.get(k)}
    if not out.get("text") and (info.get("own") or {}).get("story"):
        out["text"] = re.sub(r"\[\^[\w-]+\]", "", info["own"]["story"].split("\n\n")[0])
    return out


def lay_out(path):
    """Where the points settle with the default settings, worked out here (pipeline/graph_layout.mjs, with the
    page's own layout code) so a phone starts from it. Without Node the page works it out itself."""
    node = shutil.which("node")
    if not node:
        log("    graph layout skipped: no Node (the page lays the graph out itself)")
        return
    try:
        subprocess.run([node, str(Path(__file__).with_name("graph_layout.mjs")), path], check=True, timeout=300)
    except (subprocess.SubprocessError, OSError) as e:
        log(f"    graph layout skipped: {e} (the page lays the graph out itself)")
