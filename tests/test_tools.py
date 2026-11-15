"""The build's own tools: which step a push starts from, and the stories files' reader."""
import unittest
from pathlib import Path

from pipeline import plan, stories_md

ROOT = Path(__file__).resolve().parent.parent


class Plan(unittest.TestCase):
    def test_page_only(self):
        self.assertEqual([p for p in ["app/city/cards.js", "README.md"] if plan.needs_build(p)], [])

    def test_stories_start_at_curated(self):
        self.assertEqual(plan.start_for(["stories/nottingham/01-inns.md", "app/city.css"]), "s04_curated")

    def test_shared_code_runs_everything(self):
        self.assertEqual(plan.start_for(["pipeline/common.py"]), "all")

    def test_shared_module_starts_at_its_first_user(self):
        self.assertEqual(plan.start_for(["pipeline/notes.py"]), "s04_curated")       # read by stories_md, read by s04
        self.assertEqual(plan.start_for(["pipeline/layerdata.py"]), "s06_people")

    def test_pause_only_after_the_network(self):
        from unittest import mock
        from pipeline import web
        with mock.patch.object(web.time, "sleep") as sleep:
            web._asked[:] = [5, 5]
            web.pause(1)                     # every answer since the last pause was a saved one: no wait
            sleep.assert_not_called()
            web._asked[0] += 1               # one went to the network
            web.pause(1)
            sleep.assert_called_once_with(1)

    def test_earliest_step_wins(self):
        self.assertEqual(plan.start_for(["pipeline/s09_share.py", "pipeline/s05_dates.py"]), "s05_dates")


class Stories(unittest.TestCase):
    def test_every_city_reads(self):
        for folder in (ROOT / "stories").iterdir():
            if not folder.is_dir() or folder.name.startswith("_"):
                continue
            got = stories_md.load(folder)
            self.assertTrue(got["CURATED"], folder)
            for L in got["CURATED"]:
                self.assertTrue(L.get("id") and L.get("title"), L)
                for e in L["entries"]:
                    self.assertTrue(e["story"], f"{L['id']}: {e['name']} has no story")
                    if not e["source"].startswith("web:"):     # (another site's: checked by hand when read)
                        self.assertTrue(e.get("facts"), f"{L['id']}: {e['name']} has no check line")

    def test_entry_format(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "notes").mkdir()
            (Path(d) / "notes" / "Things.md").write_text("---\ntype: index\nid: x\n---\nIntro\non two lines.\n\n- [[A place]]\n")
            (Path(d) / "notes" / "A place.md").write_text(
                "---\ntype: story\nsource: en:A\nquote:\n  - one\n  - two\nnames: no\ncheck: a | b\nnote: ignored\nat:\n"
                "  - https://www.openstreetmap.org/way/1\n---\nThe story\ncontinues.\n")
            L = stories_md.load(d)["CURATED"][0]
        self.assertEqual(L["intro"], "Intro on two lines.")
        e = L["entries"][0]
        self.assertEqual(e, {"name": "A place", "note": "A place", "source": "en:A", "quote": ["one", "two"], "names": False,
                             "facts": ("a", "b"), "story": "The story continues.", "type": "story", "at": "osm:way/1"})


if __name__ == "__main__":
    unittest.main()
