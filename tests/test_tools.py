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
            (Path(d) / "01-x.md").write_text("# Things\nid: x\n\nIntro\non two lines.\n\n## A place\n- source: en:A\n"
                                             "- quote: one\n- quote: two\n- names: no\n- check: a | b\n- note: ignored\n\n"
                                             "The story\ncontinues.\n")
            L = stories_md.load(d)["CURATED"][0]
        self.assertEqual(L["intro"], "Intro on two lines.")
        e = L["entries"][0]
        self.assertEqual(e, {"name": "A place", "source": "en:A", "quote": ["one", "two"], "names": False,
                             "facts": ("a", "b"), "story": "The story continues.", "links": [], "weblinks": []})


if __name__ == "__main__":
    unittest.main()
