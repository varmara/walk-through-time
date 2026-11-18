"""Which buildings and pins link to a collection of old pictures (pipeline/s07_package.py: collection_fits)."""
import unittest

from pipeline.s07_package import collection_fits
from pipeline.stories_md import load

LACE_MARKET = {"title": "The Lace Market", "url": "u", "areas": ["Lace Market"], "notLayers": ["hockley"]}


class Collections(unittest.TestCase):
    def test_a_place_in_the_area_gets_the_link(self):
        self.assertTrue(collection_fits(LACE_MARKET, "", ",lacemarket,", [], {"Lace Market"}))

    def test_a_layer_the_collection_is_not_for_does_not(self):
        # Hockley lies beside the Lace Market, partly inside its conservation area
        self.assertFalse(collection_fits(LACE_MARKET, "", ",hockley,", [], {"Lace Market"}))
        self.assertFalse(collection_fits(LACE_MARKET, "", ",lacemarket,hockley-x,", [], {"Lace Market"}))
        self.assertTrue(collection_fits(LACE_MARKET, "", ",hockleyfields,", [], {"Lace Market"}))   # only the whole key

    def test_names_layers_and_people(self):
        c = {"names": ["trent bridge"], "layers": ["wilford"], "who": ["Lord Byron"]}
        self.assertTrue(collection_fits(c, "trent bridge cricket ground", None, [], set()))
        self.assertTrue(collection_fits(c, "x", ",wilford-church,", [], set()))
        self.assertTrue(collection_fits(c, "x", None, ["Lord Byron"], set()))
        self.assertFalse(collection_fits(c, "x", ",castle,", ["Robin Hood"], {"Castle"}))

    def test_the_table_is_read(self):
        got = {c["title"]: c for c in load("stories/nottingham")["COLLECTIONS"]}
        self.assertEqual(got["The Lace Market"]["notLayers"], ["hockley"])
        self.assertNotIn("notLayers", got["Nottingham Castle"])


if __name__ == "__main__":
    unittest.main()
