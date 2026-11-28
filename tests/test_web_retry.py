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
