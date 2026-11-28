import os
import tempfile
import unittest
from unittest import mock

from pipeline import s00_fetch_visitor as v


class FailedRoutes(unittest.TestCase):
    def test_a_route_every_server_failed_on_is_not_asked_for_again(self):
        # the Mallard Route timed out on all three servers in every full build: ten minutes each time
        c = {"bbox": {"s": 52.9, "w": -1.2, "n": 53.0, "e": -1.1}}
        rel = [{"id": 1, "tags": {"name": "Long Route"}}]
        asked = []

        def overpass(q, **kw):
            asked.append(q)
            if "relation[" in q:
                return rel
            raise RuntimeError("All Overpass servers failed")
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"WTT_CACHE": d}), \
                mock.patch.dict(os.environ, {}, clear=False), mock.patch.object(v, "overpass", overpass):
            os.environ.pop("WTT_MAX_AGE_DAYS", None)
            self.assertEqual(v.routes(c), [])
            self.assertEqual(v.routes(c), [])
        self.assertEqual(sum("rel(1)" in q for q in asked), 1)
