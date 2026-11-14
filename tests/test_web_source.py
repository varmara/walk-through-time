"""A story resting on another site's page (web:https://…, pipeline/s04_curated.py: article): fetched as text,
its site named in the citation, and its check words looked for in it."""
import unittest
from unittest import mock

from pipeline import s04_curated as C


class WebSource(unittest.TestCase):
    def test_page(self):
        C._cache.clear()
        page = {"title": "Helen Watts", "text": "Daughter of the vicar of Lenton. Arrested at the Albert Hall."}
        with mock.patch.object(C, "http_text", return_value=page), mock.patch.object(C.time, "sleep"):
            a = C.article("web:https://map.mappingwomenssuffrage.org.uk/items/show/256")
        self.assertEqual(a["kind"], "Mapping Women's Suffrage")
        self.assertEqual(a["title"], "Helen Watts")
        self.assertIn("albert hall", a["text"])
        self.assertIsNone(a["qid"])

    def test_unknown_site_named_by_its_host(self):
        C._cache.clear()
        with mock.patch.object(C, "http_text", return_value={"title": "https://www.example.org/p", "text": "x"}), \
                mock.patch.object(C.time, "sleep"):
            a = C.article("web:https://www.example.org/p")
        self.assertEqual((a["kind"], a["title"]), ("example.org", "example.org"))


if __name__ == "__main__":
    unittest.main()
