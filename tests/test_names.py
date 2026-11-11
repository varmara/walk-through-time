"""Names: the rules (common.py, s06_names.py) on made-up tags, and the titles of known buildings in the last build.

The second part reads the build's work files (work/<city>/names.json); it is skipped when they are not there.
Add a row to tests/expected/<city>-names.md whenever a name is fixed, so it cannot quietly break again.
"""
import json
import unittest
from pathlib import Path

from pipeline.common import building_name, marker, other_names, tidy_listing
from pipeline.s06_names import full_title
from pipeline.stories_md import table

ROOT = Path(__file__).resolve().parent.parent


class Rules(unittest.TestCase):
    def test_listing_tidied(self):
        self.assertEqual(tidy_listing("NEWCASTLE HOUSE AND ATTACHED BOUNDARY WALL"), "Newcastle House")
        self.assertEqual(tidy_listing("THE BELL INN"), "The Bell Inn")
        self.assertEqual(tidy_listing("11 PELHAM STREET, FORMERLY THE NOTTINGHAM AND NOTTS BANK"), "Nottingham and Notts Bank")
        self.assertEqual(tidy_listing("STANFORD HOUSE, NOTTINGHAM"), "Stanford House")

    def test_listing_that_names_no_building(self):
        self.assertIsNone(tidy_listing("3 AND 5, HOUNDS GATE"))
        self.assertIsNone(tidy_listing("RAILINGS TO NUMBER 12"))
        self.assertEqual(building_name({}, listing_name="RAILINGS AND GATES TO ST MARY'S CHURCH"), (None, None))

    def test_occupier_is_today_not_the_name(self):
        name, today = building_name({"name": "Regus", "office": "coworking"}, listing_name="STANFORD HOUSE")
        self.assertEqual((name, today), ("Stanford House", "Regus"))

    def test_occupier_without_tags(self):
        # Historic England names a building, OpenStreetMap an unrelated business: the business is Today
        name, today = building_name({"name": "Jem Leisure"}, listing_name="FORMER MIDLAND BANK")
        self.assertEqual(today, "Jem Leisure")

    def test_own_name_kept(self):
        self.assertEqual(building_name({"name": "The Council House"}, listing_name="COUNCIL HOUSE"), ("The Council House", None))

    def test_pub_keeps_its_name(self):
        self.assertEqual(building_name({"name": "The Bell Inn", "amenity": "pub"}, listing_name="THE BELL INN")[0], "The Bell Inn")

    def test_numbers_become_an_address(self):
        name, _ = building_name({"addr:street": "Derby Road"}, label="Numbers 119 and 121")   # a Wikidata label
        self.assertEqual(name, "119 and 121 Derby Road")

    def test_shop_by_address(self):
        t = {"name": "Greggs", "shop": "bakery", "building": "retail", "addr:housenumber": "12", "addr:street": "Long Row"}
        self.assertEqual(building_name(t), ("12 Long Row", "Greggs"))

    def test_address_alone_is_no_name(self):
        self.assertEqual(building_name({"addr:housenumber": "4", "addr:street": "High Pavement"}), (None, None))

    def test_house_numbers(self):
        from pipeline.common import house_numbers
        self.assertEqual([house_numbers(n) for n in ("15;16", "3;5;7", "2-4", "12")], ["15 and 16", "3, 5 and 7", "2–4", "12"])

    def test_markers(self):
        self.assertTrue(marker({"amenity": "photo_booth", "name": "Photo-Me"}))
        self.assertTrue(marker({"historic": "memorial", "name": "Malt Cross"}))
        self.assertFalse(marker({"amenity": "pub", "name": "The Malt Cross"}))

    def test_then_and_now(self):
        self.assertEqual(full_title("Shire Hall", "National Justice Museum", None, [{}]), "Shire Hall · National Justice Museum")
        self.assertEqual(full_title("Nottingham station", None, ["Midland Railway Station"], [{"building": "train_station"}]),
                         "Midland Railway Station · Nottingham station")
        self.assertIsNone(full_title("12 Long Row", "Greggs", None, [{}]))          # an address: the Today row says it
        self.assertIsNone(full_title("St Mary's Church", "Church of St Mary", None, [{}]))   # one name twice

    def test_other_names(self):
        self.assertEqual(other_names({"old_name": "Kings Arms"}, "The Pitcher and Piano", None), ["Kings Arms"])


def title(n):
    """The card's title, as the page makes it (app/city/cards.js: placeName)."""
    if n.get("full") or n.get("name"):
        return n.get("full") or n["name"]
    w = n.get("where")
    return (w if w[0].isdigit() else f"A building on {w}") if w else "A building"


class KnownBuildings(unittest.TestCase):
    def test_titles(self):
        for f in sorted((ROOT / "tests" / "expected").glob("*-names.md")):
            city = f.name[:-len("-names.md")]
            work = ROOT / "work" / city
            if not (work / "names.json").exists() or not (work / "buildings.json").exists():
                self.skipTest(f"no work files for {city}: tools/fetch-built.sh work")
            names = json.loads((work / "names.json").read_text())
            index = {b["osm"]: str(i) for i, b in enumerate(json.loads((work / "buildings.json").read_text()))}
            wrong = []
            for r in table(f):
                k = index.get(r["outline"])
                got = title(names.get(k, {})) if k else "(outline not in the build)"
                if got != r["title"]:
                    wrong.append(f"{r['outline']}: {got!r}, expected {r['title']!r} ({r.get('note', '')})")
            self.assertFalse(wrong, f"{city}:\n  " + "\n  ".join(wrong))


if __name__ == "__main__":
    unittest.main()
