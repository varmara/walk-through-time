"""A story written by hand from another site's page (web:https://…): the build does not read the site
(pipeline/s04_curated.py: written_by_hand); it is cited with the site's name and the date it was read, and needs
that date and its own place."""
import unittest
from unittest import mock

from pipeline import s04_curated as C


class WrittenByHand(unittest.TestCase):
    def test_citation(self):
        e = {"name": "Helen Watts", "source": "web:https://map.mappingwomenssuffrage.org.uk/items/show/256",
             "title": "Helen Watts", "read": "2026-11-14"}
        with mock.patch.object(C, "http_text", side_effect=AssertionError("the site must not be read")):
            a = C.written_by_hand(e)
        self.assertEqual((a["kind"], a["title"], a["read"]), ("Mapping Women's Suffrage", "Helen Watts", "2026-11-14"))
        self.assertEqual(a["url"], "https://map.mappingwomenssuffrage.org.uk/items/show/256")

    def test_unknown_site_named_by_its_host(self):
        a = C.written_by_hand({"name": "X", "source": "web:https://www.example.org/p", "read": "2026-11-14"})
        self.assertEqual((a["kind"], a["title"]), ("example.org", "X"))


class Files(unittest.TestCase):
    def test_every_hand_story_has_a_date_and_a_place(self):
        import re
        from pathlib import Path
        from pipeline import stories_md
        root = Path(__file__).resolve().parent.parent / "stories"
        for folder in sorted(p for p in root.iterdir() if p.is_dir()):
            for L in stories_md.load(folder)["CURATED"]:
                for e in L["entries"]:
                    if e["source"].startswith("web:"):
                        where = f"{folder.name} / {L['id']} / {e['name']}"
                        self.assertRegex(e.get("read", ""), r"^\d{4}-\d{2}-\d{2}$", f"{where}: read: date")
                        self.assertTrue(e.get("unplaced") or re.match(r"(pin:-?\d|osm:|name:|nhle:)", e.get("at", "")), f"{where}: at:")
                        self.assertNotIn("facts", e, f"{where}: written by hand, so no check words")


if __name__ == "__main__":
    unittest.main()
