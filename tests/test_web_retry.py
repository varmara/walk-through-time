import io
import unittest
import urllib.error
from unittest import mock

from pipeline import web


def refused(code):
    return urllib.error.HTTPError("https://example.org/", code, "no", {}, io.BytesIO(b""))


class Retries(unittest.TestCase):
    def test_a_refused_page_is_asked_for_once(self):
        # Historic England refuses the build's requests (403): asking three times only waited half a minute a build
        with mock.patch.object(web, "_open", side_effect=refused(403)) as o, mock.patch.object(web.time, "sleep") as z, \
                mock.patch.object(web, "cached", return_value=None):
            with self.assertRaises(RuntimeError):
                web.http_text("https://example.org/")
        self.assertEqual(o.call_count, 1)
        z.assert_not_called()

    def test_a_busy_server_is_asked_again(self):
        with mock.patch.object(web, "_open", side_effect=refused(503)) as o, mock.patch.object(web.time, "sleep") as z, \
                mock.patch.object(web, "cached", return_value=None):
            with self.assertRaises(RuntimeError):
                web.http_text("https://example.org/", tries=3)
        self.assertEqual(o.call_count, 3)
        self.assertEqual(z.call_count, 2)          # no wait after the last try


class RingTest(unittest.TestCase):
    def test_same_answers_as_point_in_ring(self):
        # ring_test (bounds first, numpy for long rings) must answer exactly as the plain loop does
        import math
        import random
        from pipeline.geo import point_in_ring, ring_test
        rnd = random.Random(1)
        for n in (8, 500):
            ring = [[math.cos(2 * math.pi * k / n) * (1 + 0.3 * rnd.random()),
                     math.sin(2 * math.pi * k / n) * (1 + 0.3 * rnd.random())] for k in range(n)]
            ring.append(ring[0])
            t = ring_test(ring)
            pts = [(rnd.uniform(-1.5, 1.5), rnd.uniform(-1.5, 1.5)) for _ in range(3000)] + [tuple(p) for p in ring]
            self.assertEqual([t(x, y) for x, y in pts], [point_in_ring(x, y, ring) for x, y in pts])
