"""Web requests, and saved answers from web services (the cache GitHub Actions keeps between builds)."""
import gzip
import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .common import log

UA = "walk-through-time/1.0 (+https://github.com/varmara/walk-through-time)"


# ---------------------------------------------------------------- saved answers from web services
# With $WTT_CACHE set to a folder, every successful answer from a web service (Wikipedia, Wikidata, Commons,
# Historic England's and Natural England's map services, Overpass…) is saved there, and the same request later
# is answered from the folder instead of the network. GitHub Actions keeps the folder between builds, so a build
# after a code or story change asks only for what is new; the scheduled builds start with an empty folder and
# so fetch everything fresh. Without $WTT_CACHE (e.g. on a laptop) nothing is saved.
def _cache_file(*parts):
    root = os.environ.get("WTT_CACHE")
    if not root:
        return None
    key = hashlib.sha1("\n".join(str(p) for p in parts).encode()).hexdigest()
    d = Path(root) / key[:2]
    d.mkdir(parents=True, exist_ok=True)
    return d / (key + ".gz")


def cached(kind, url, body=None):
    f = _cache_file(kind, url, body)
    if f and f.exists():
        try:
            return gzip.decompress(f.read_bytes())
        except (OSError, EOFError):
            f.unlink(missing_ok=True)
    return None


def keep(kind, url, body, raw):
    f = _cache_file(kind, url, body)
    if f:
        tmp = f.with_suffix(".tmp")
        tmp.write_bytes(gzip.compress(raw, 6))
        tmp.replace(f)


def http(url, data=None, params=None, accept="application/json", tries=4, timeout=180):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    body = urllib.parse.urlencode(data).encode() if data else None
    hit = cached(accept, url, body)
    if hit is not None:
        return json.loads(hit.decode("utf-8"))
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers={
                "User-Agent": UA, "Accept": accept,
                **({"Content-Type": "application/x-www-form-urlencoded"} if body else {}),
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            out = json.loads(raw.decode("utf-8"))
            failed = isinstance(out, dict) and ("error" in out or "error" in str(out.get("remark", "")).lower())
            if not failed:              # an API's error or Overpass's timeout remark is not worth keeping
                keep(accept, url, body, raw)
            return out
        except Exception as e:  # noqa: BLE001 - retry any network or server error
            last = e
            if attempt < tries - 1:
                wait = 10 * (attempt + 1)
                log(f"  {url.split('/')[2]}: {e}; retrying in {wait}s")
                time.sleep(wait)
    raise RuntimeError(f"{url.split('?')[0]}: {last}")


def http_bytes(url, tries=3, timeout=180):
    """A file as it is (a CSV, say), saved like the other answers."""
    hit = cached("bytes", url)
    if hit is not None:
        return hit
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            keep("bytes", url, None, raw)
            return raw
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"{url}: {last}")


def http_text(url, tries=3, timeout=60):
    """A web page as plain text (tags removed), for checking facts against it."""
    import html as _html
    last = None
    for attempt in range(tries):
        try:
            hit = cached("text/html", url)
            if hit is None:
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    hit = r.read()
                keep("text/html", url, None, hit)
            raw = hit.decode("utf-8", "replace")
            title = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.S)
            body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S)
            body = _html.unescape(re.sub(r"<[^>]+>", " ", body))
            return {"title": _html.unescape(re.sub(r"<[^>]+>", "", title[1])).strip() if title else url,
                    "text": " ".join(body.split())}
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"{url}: {last}")
