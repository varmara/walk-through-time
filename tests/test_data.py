"""The published data holds together: every reference points at something that exists.

Reads what the page loads (data/<city>.json, data/<city>/cards/, osm.json, tiles, share pages, the graph). Skipped
for a city whose data is not here (tools/fetch-built.sh data fetches the last published data).
A broken reference here is a dead tap on the map: a layer item that opens nothing, a plaque whose building is
missing, a story with no words.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CITIES = sorted(p.stem for p in (ROOT / "cities").glob("*.json"))


def load(city):
    d = ROOT / "data"
    if not (d / f"{city}.json").exists() or not (d / city / "cards").is_dir():
        return None
    index = json.loads((d / f"{city}.json").read_text())
    cards = {}
    for f in (d / city / "cards").glob("*.json"):
        for k, v in json.loads(f.read_text()).items():
            cards[int(k)] = (int(f.stem), v)
    return index, cards, json.loads((d / city / "osm.json").read_text())


class Data(unittest.TestCase):
    def setUp(self):
        self.cities = {c: x for c in CITIES if (x := load(c))}
        if not self.cities:
            self.skipTest("no built data here: tools/fetch-built.sh data")

    def each(self):
        return [(city, *x) for city, x in self.cities.items()]

    def test_every_building_has_a_card_in_its_file(self):
        for city, index, cards, osm in self.each():
            n, chunk = index["index"]["n"], index["tiles"]["chunk"]
            self.assertEqual(len(osm), n, "osm.json has one id per building")
            self.assertEqual(sorted(cards), list(range(n)), "every building is in a card file")
            wrong = [i for i, (f, _) in cards.items() if f != i // chunk]
            self.assertFalse(wrong[:5], "buildings in the wrong card file")
            self.assertFalse([i for i, (_, c) in cards.items() if len(c.get("xy") or []) != 2][:5], "buildings with no centre")

    def test_counts(self):
        for city, index, cards, osm in self.each():
            ix = index["index"]
            self.assertEqual(sum(c for _, c in ix["hist"]) + ix["undated"], ix["n"], "buildings per year add up")

    def test_references(self):
        for city, index, cards, osm in self.each():
            n, pins, areas, routes = index["index"]["n"], index["pins"]["features"], index.get("areas", []), index.get("routes", [])

            def ok(r):
                if isinstance(r, int):
                    return 0 <= r < n
                return ((r[0] == "p" and int(r[1:]) < len(pins)) or (r[0] == "a" and int(r[1:]) < len(areas) and areas[int(r[1:])] is not None)
                        or (r[0] == "r" and int(r[1:]) < len(routes)))
            bad = []
            for L in index["layers"]:
                for g in L["groups"]:
                    for it in g.get("items") or []:
                        refs = [it[0]] if isinstance(it[0], int) else it[1]
                        bad += [f"{L['id']}/{g['key']}: {it}" for r in refs if not ok(r)]
            for f in pins:
                on = f["properties"].get("on")
                if on is not None and not 0 <= on < n:
                    bad.append(f"pin {f['properties'].get('name')}: on {on}")
            for a in areas:
                if a is None:        # only in the tiles (tree preservation orders)
                    continue
                bb = a.get("bb") or []
                if len(bb) != 4 or not (bb[0] <= bb[2] and bb[1] <= bb[3]):
                    bad.append(f"area {a.get('name')}: bounds {bb}")
            self.assertFalse(bad[:10], f"{len(bad)} references to nothing")

    def test_every_story_has_words(self):
        for city, index, cards, osm in self.each():
            pins, templates = index["pins"]["features"], index.get("templates", {})
            bad = []
            for i, (_, c) in cards.items():
                for s in c.get("stories") or []:
                    if s.get("text"):
                        continue
                    if s.get("pin"):
                        k = int(s["pin"][1:])
                        if k >= len(pins) or not pins[k]["properties"].get("text"):
                            bad.append(f"building {i} ({osm[i]}): plaque {s['pin']} has no words")
                    elif s.get("tpl") not in templates:
                        bad.append(f"building {i} ({osm[i]}): story with no words in {s.get('layer')}")
            for f in pins:
                if not f["properties"].get("text"):
                    bad.append(f"pin {f['properties'].get('name')}: no words")
            self.assertFalse(bad[:10], f"{len(bad)} stories with no words")

    def test_index_and_cards_agree(self):
        for city, index, cards, osm in self.each():
            bad = [k for k, p in index["index"]["props"].items()
                   if p.get("stories") and len(p["stories"]) != len(cards[int(k)][1].get("stories") or [])]
            self.assertFalse(bad[:5], "the index and the card file list different stories")

    def test_tiles_and_pages(self):
        for city, index, cards, osm in self.each():
            d = ROOT / "data"
            tiles = list((d / city / "tiles").rglob("*.pbf"))
            self.assertTrue(tiles, "no map tiles")
            zs = {int(t.relative_to(d / city / "tiles").parts[0]) for t in tiles}
            self.assertEqual(zs, set(range(index["tiles"]["minzoom"], index["tiles"]["maxzoom"] + 1)), "a zoom level has no tiles")
            share = d / "share" / city
            missing = [osm[int(k)] for k, p in index["index"]["props"].items()
                       if p.get("name") and osm[int(k)] and not (share / (osm[int(k)].replace("/", "-") + ".html")).exists()]
            self.assertFalse(missing[:5], f"{len(missing)} named buildings with no share page")
            for L in index["layers"]:
                if L["kind"] in ("stories", "people"):
                    self.assertTrue((share / f"layer-{L['id']}.html").exists(), f"no page for layer {L['id']}")

    def test_graph(self):
        for city, index, cards, osm in self.each():
            f = ROOT / "data" / f"{city}-graph.json"
            if not f.exists():
                continue
            g = json.loads(f.read_text())
            ids = {n["id"] for n in g["nodes"]}
            bad = [f"{x['s']} → {x['t']}" for x in g["links"] if x["s"] not in ids or x["t"] not in ids]
            self.assertFalse(bad[:5], f"{len(bad)} graph links to missing points")


if __name__ == "__main__":
    unittest.main()
