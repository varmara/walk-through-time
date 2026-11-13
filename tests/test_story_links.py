"""Story files' groups and cross-links (stories/<city>/*.md: groups:, - group:, - see:): every group an entry
names is one its layer declares, every declared group is used, and every "see" finds exactly one other story;
and the build turns a "see" into a link to where that story is (pipeline/s06_layers.py: cross_links)."""
import unittest
from pathlib import Path

from pipeline import stories_md
from pipeline.s06_layers import cross_links

ROOT = Path(__file__).resolve().parent.parent


class Files(unittest.TestCase):
    def test_every_city(self):
        for folder in sorted((ROOT / "stories").iterdir()):
            if not folder.is_dir():
                continue
            layers = [L for L in stories_md.load(folder)["CURATED"] if L.get("kind") not in ("people", "facts")]
            by_name, by_full = {}, {}
            for L in layers:
                for e in L["entries"]:
                    by_name.setdefault(e["name"].lower(), []).append(e)
                    by_full[f"{L['id']}/{e['name']}".lower()] = e
            for L in layers:
                keys = [k for k, _ in L.get("groups", [])]
                used = set()
                for e in L["entries"]:
                    where = f"{folder.name} / {L['id']} / {e['name']}"
                    if keys:
                        self.assertIn(e.get("group"), keys, f"{where}: its group is not one the layer declares")
                        used.add(e.get("group"))
                    for name in e.get("see", []):
                        hits = [by_full[name.lower()]] if name.lower() in by_full else by_name.get(name.lower(), [])
                        self.assertEqual(len([h for h in hits if h is not e]), 1,
                                         f"{where}: see {name!r} must find exactly one other story (layer/heading if two share it)")
                self.assertEqual(set(keys) - used, set(), f"{folder.name} / {L['id']}: groups no story uses")


class Parse(unittest.TestCase):
    def test_groups_and_see(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "01-x.md"
            p.write_text("# X\nid: x\ngroups: x-a = First | x-b = Second\n\nIntro.\n\n## One\n- source: en:One\n"
                         "- group: x-b\n- see: Two | x/Three\n\nText.\n")
            L = stories_md.layer(p)
        self.assertEqual(L["groups"], [["x-a", "First"], ["x-b", "Second"]])
        self.assertEqual(L["entries"][0]["group"], "x-b")
        self.assertEqual(L["entries"][0]["see"], ["Two", "x/Three"])
        self.assertEqual(L["intro"], "Intro.")

    def test_links_resolve(self):
        pin, story = {"name": "Two"}, {"text": "One's story"}
        es = [{"layer": "x", "name": "One", "b": 12, "see": ["Two", "Nowhere"], "_story": story},
              {"layer": "y", "name": "Two", "b": "p3", "_story": pin},
              {"layer": "y", "name": "Three", "b": 12, "see": ["One"], "_story": {}}]
        cross_links(es, {"x", "y"})
        self.assertEqual(story["see"], [["Two", "p3"]])
        self.assertNotIn("see", pin)
        self.assertNotIn("see", es[2])          # the same building: already on its card
        self.assertTrue(all("_story" not in e for e in es))


if __name__ == "__main__":
    unittest.main()
