"""A place stays a place: a statue of a person is "Statue of …" (pipeline/visitorlayers.py), a plaque is "Plaque to
…" or the place it marks, and who each plaque remembers comes from stories/<city>/plaque-people.md."""
import unittest
from pathlib import Path

from pipeline import stories_md
from pipeline.visitorlayers import name_of

ROOT = Path(__file__).resolve().parent.parent


class Sets(unittest.TestCase):
    def test_same_name_places_stay_apart(self):
        from pipeline.layerdata import grouped
        at = {1: (-1.15, 52.95), 2: (-1.15005, 52.95003), 3: (-1.20, 52.90), "p4": (-1.10, 52.97)}
        got = grouped([[1, "Red Lion"], [2, "Red Lion"], [3, "Red Lion"], ["p4", "In this house"]], at.get)
        self.assertEqual(got, [["Red Lion", [1, 2]], ["Red Lion", [3]], ["In this house", ["p4"]]])
        # a person is the same person anywhere
        self.assertEqual(grouped([[1, "Watson Fothergill"], [3, "Watson Fothergill"]]), [["Watson Fothergill", [1, 3]]])

    def test_source_titles(self):
        from pipeline.s06_people import source_title
        self.assertEqual(source_title("Site of SWISS MILLS 1886-1984"), "Site of Swiss Mills")
        self.assertEqual(source_title("Chilwell Hall / Charlton Family"), "Chilwell Hall")
        self.assertEqual(source_title("T.H. Barton OBE 1866-1946"), "T.H. Barton OBE")


class Titles(unittest.TestCase):
    def test_statues(self):
        art = lambda n, k: name_of({"cat": "art", "tags": {"name": n, "artwork_type": k}})  # noqa: E731
        self.assertEqual(art("Brian Clough", "statue"), "Statue of Brian Clough")
        self.assertEqual(art("Jesse Boot", "bust"), "Bust of Jesse Boot")
        self.assertEqual(art("Spirit of Nottingham", "sculpture"), "Spirit of Nottingham")
        self.assertEqual(art("Statue of Robin Hood", "statue"), "Statue of Robin Hood")

    def test_plaque_tables(self):
        for folder in sorted(p for p in (ROOT / "stories").iterdir() if p.is_dir()):
            d = stories_md.load(folder)
            for start, v in d["PLAQUE_PEOPLE"].items():
                self.assertTrue(v["people"], start)
                self.assertIn(v.get("group", "other"), {"architects", "writers", "science", "industry", "sport", "arts",
                                                        "faith", "military", "public", "other"}, start)
            for name, a in d["ABOUT"].items():
                self.assertTrue(a["url"].startswith("http"), name)
                self.assertRegex(a["read"] or "", r"^\d{4}-\d{2}-\d{2}$", f"{name}: the date it was read")


if __name__ == "__main__":
    unittest.main()
