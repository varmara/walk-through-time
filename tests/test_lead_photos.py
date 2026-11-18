"""A Wikipedia article's lead photo is a building's photo only when it is a photograph near the building
(pipeline/s06_summaries.py: why_not), and the table that names an article for a building is read."""
import unittest

from pipeline.s06_summaries import why_not
from pipeline.stories_md import load


class LeadPhotos(unittest.TestCase):
    OK = {"file": "A.jpg", "licence": "CC BY-SA 2.0", "author": "X", "year": 2009}

    def test_a_photograph_nearby_is_used(self):
        self.assertIsNone(why_not("A.jpg", self.OK, (-1.1500, 52.9500), (-1.1501, 52.9501)))
        self.assertIsNone(why_not("A.JPEG", self.OK, None, (-1.15, 52.95)))        # no position on Commons: no test

    def test_crests_logos_and_maps_are_not(self):
        for f in ("Crest.png", "Logo.svg", "Plan.gif"):
            self.assertIn("not a photograph", why_not(f, self.OK, None, (-1.15, 52.95)))

    def test_a_file_far_away_or_without_licence_is_not(self):
        self.assertIn("m away", why_not("A.jpg", self.OK, (-1.2951, 52.9767), (-1.2826, 52.9015)))   # Ilkeston's mill, 3.6 km off
        self.assertIn("licence", why_not("A.jpg", {**self.OK, "licence": ""}, None, None))
        self.assertIn("licence", why_not("A.jpg", None, None, None))

    def test_the_stories_table_is_read(self):
        got = load("stories/nottingham")["PHOTO_ARTICLES"]
        self.assertEqual(got.get("way/100083900"), "Rock City (venue)")
        self.assertTrue(all(k.startswith(("way/", "relation/")) for k in got))


if __name__ == "__main__":
    unittest.main()
