"""Architects from a Wikipedia article's table of buildings: an estate's article that lists its houses with their
street and number and who designed them (The Park Estate's "Significant properties"). The table is found by its
headings (a column for the architect, and one for the street and number or the address); each row is matched to
a building by its OpenStreetMap address, inside the area named for it, or by its name where it has no number.
An architect marked "?" in the table (an uncertain attribution) is kept as uncertain.

The city names its articles in cities/<city>.json: "architect_lists": [{"article": "The Park Estate",
"within": "The Park"}] (within: a conservation area; addresses outside it are not matched, as many towns have a
South Road). Wikipedia text is CC BY-SA; only the facts are kept, with a link to the article.
"""
import re

from .common import log
from .geo import point_in_ring

NUM = re.compile(r"^(\d+)([a-z]?)$", re.I)


def unlink(t, targets=False):
    """Wiki markup out of a cell: files, references, templates, links (to the words shown, or with targets to the
    article linked: a piped [[Thomas Chambers Hine|T. C. Hine]] is Thomas Chambers Hine), bold, tags."""
    t = re.sub(r"<ref[^>/]*/>", "", t)
    t = re.sub(r"<ref[^>]*>.*?</ref>", "", t, flags=re.S)
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    for _ in range(4):
        t = re.sub(r"\{\{[^{}]*\}\}", "", t)
    t = re.sub(r"\[\[(?:File|Image):(?:[^\[\]]|\[\[[^\]]*\]\])*\]\]", "", t)
    t = re.sub(r"\[\[([^\]|]*)\|([^\]]*)\]\]", r"\1" if targets else r"\2", t)
    t = re.sub(r"\[\[([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[https?://\S+\s([^\]]*)\]", r"\1", t)
    t = re.sub(r"'{2,}|<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip()


def cells(line):
    """One row's cells, still in wiki markup; a cell's leading 'style="…" |' dropped."""
    line = re.sub(r"\[\[(?:File|Image):(?:[^\[\]]|\[\[[^\]]*\]\])*\]\]", "", line)
    out = []
    for c in re.split(r"\|\||!!|\n[|!]", "\n" + line)[1:] if line.startswith(("|", "!")) else []:
        c = re.sub(r"^\s*[a-z-]+=\"[^\"]*\"[^|]*\|(?!\|)", "", c)
        out.append(c)
    return out


def tables(wikitext):
    """[[header cells], [row cells], ...] for each wikitable."""
    out = []
    for body in re.findall(r"\{\|.*?\n\|\}", wikitext, flags=re.S):
        rows = []
        for chunk in re.split(r"\n\|-[^\n]*", body)[1:]:
            chunk = chunk.strip("\n")
            if chunk.startswith("|}"):
                continue
            chunk = re.sub(r"\n\|\}$", "", chunk)
            rows.append(cells(chunk.replace("\n|", "||").replace("\n!", "!!")))
        first = re.search(r"\n!([^\n]*(?:\n![^\n]*)*)", body)
        head = [unlink(h) for h in cells("!" + first.group(1).replace("\n!", "!!"))] if first else []
        if head and rows and [unlink(c) for c in rows[0]] == head:
            rows = rows[1:]
        out.append([head] + rows)
    return out


def numbers(s):
    """'1–7' -> 1..7; '1, 3' -> 1, 3; '7a' -> 7a; '18 and 20' -> 18, 20."""
    out = []
    for part in re.split(r",|&|\band\b", s):
        part = part.strip()
        m = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", part)
        if m and int(m[1]) < int(m[2]) <= int(m[1]) + 40:
            out += [str(n) for n in range(int(m[1]), int(m[2]) + 1)]
        elif NUM.match(part):
            out.append(part.lower())
    return out


def names_in(cell):
    """'Thomas Chambers Hine?' -> [('Thomas Chambers Hine', True)]; 'A; B (tower)' -> both."""
    out = []
    for part in re.split(r";|/|\band\b|,(?!\s*JP)", re.sub(r"\([^)]*\)", "", cell)):
        part = part.strip(" .")
        unsure = "?" in part
        part = re.sub(r"\?|^(?:attributed to|probably|possibly)\s+", "", part, flags=re.I).strip(" .")
        if len(part) > 3 and re.match(r"[A-Z]", part) and not re.search(r"unknown|not known", part, re.I):
            out.append((part, unsure))
    return out


def architect_lists(cfg, buildings, areas, wikitexts):
    """{building index: [(name, unsure, article title)]} from the city's articles."""
    found = {}
    lists = cfg.get("architect_lists") or []
    if not lists:
        return found
    texts = wikitexts([x["article"] for x in lists])
    for spec in lists:
        text = texts.get(spec["article"])
        if not text:
            log(f"    architect list {spec['article']}: article not read")
            continue
        rings = [r for a in areas if (a.get("properties") or {}).get("name") == spec.get("within")
                 for r in ([a["geometry"]["coordinates"][0]] if a["geometry"]["type"] == "Polygon"
                           else [p[0] for p in a["geometry"]["coordinates"]])]

        def inside(b):
            if not rings:
                return True
            x, y = (b["bb"][0] + b["bb"][2]) / 2, (b["bb"][1] + b["bb"][3]) / 2
            return any(point_in_ring(x, y, r) for r in rings)

        addr, named = {}, {}
        for i, b in enumerate(buildings):
            if not inside(b):
                continue
            t = b["tags"]
            if t.get("addr:street") and t.get("addr:housenumber"):
                for n in numbers(t["addr:housenumber"].replace(";", ",")):
                    addr.setdefault((n, t["addr:street"].lower()), []).append(i)
            if t.get("name"):
                named.setdefault(t["name"].lower(), []).append(i)
        rows = matched = 0
        for tab in tables(text):
            head = [h.lower() for h in tab[0]]
            a_col = next((k for k, h in enumerate(head) if "architect" in h), None)
            s_col = next((k for k, h in enumerate(head) if "street" in h or "address" in h), None)
            n_col = next((k for k, h in enumerate(head) if h == "name"), None)
            if a_col is None or s_col is None:
                continue
            for row in tab[1:]:
                if len(row) <= max(a_col, s_col):
                    continue
                who = names_in(unlink(row[a_col], targets=True))
                if not who:
                    continue
                rows += 1
                place, name = unlink(row[s_col]), unlink(row[n_col]) if n_col is not None else ""
                street, _, num = place.rpartition(",")
                street, num = (street.strip(), num.strip()) if street else (place.strip(), "")
                hits = {i for n in numbers(num) for i in addr.get((n, street.lower()), [])}
                if not hits and name and len(named.get(name.lower(), [])) == 1:      # no number: by its name, if one building has it
                    hits = set(named[name.lower()])
                for i in hits:
                    for name, unsure in who:
                        if all(name != w[0] for w in found.get(i, [])):
                            found.setdefault(i, []).append((name, unsure, spec["article"]))
                matched += bool(hits)
        log(f"    architect list {spec['article']}: {rows} rows with an architect, {matched} matched to buildings")
    return found
