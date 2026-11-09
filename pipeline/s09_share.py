"""Share pages: one tiny static page per named building, so a shared link shows a proper preview.

Twitter (X), Telegram, WhatsApp and others read Open Graph tags from the page at the link and do not run
JavaScript, so the map itself cannot describe a building. Each page carries the building's name, its summary
and its photo (or the site's picture) and sends a visitor straight on to the map at that building
(<city>/?b=<index>&osm=way/123). Pages are keyed by OpenStreetMap id, which stays the same between data builds.

Writes data/share/<city>/<type>-<id>.html (the folder is rebuilt each time, so removed buildings disappear).
"""
import html
import json
import os
import shutil
from pathlib import Path

from .common import load, city, log


def site_url():
    """The published site, e.g. https://varmara.github.io/walk-through-time/ (from GitHub Actions, or a default)."""
    repo = os.environ.get("GITHUB_REPOSITORY", "varmara/walk-through-time")
    owner, name = repo.split("/")
    return f"https://{owner}.github.io/{name}/" if name != f"{owner}.github.io" else f"https://{name}/"


def describe(p, city_name):
    if p.get("sum"):
        text = p["sum"]
    else:
        bits = []
        if p.get("y") is not None:
            bits.append(("probably built " + p["per"]) if p.get("f") == "area" else
                        f"built {'in ' if p.get('f') == 'exact' else 'about '}{p['y']}")
        if p.get("grade"):
            bits.append(f"Grade {p['grade']} listed")
        text = (p["name"] + ": " + ", ".join(bits) + ".") if bits else f"{p['name']} on the 3D map of historic {city_name}."
    return text if len(text) <= 300 else text[:297].rsplit(" ", 1)[0] + "…"


def page(p, i, city_id, city_name, site):
    osm = p["osm"]
    target = f"{site}{city_id}/?b={i}&osm={osm}"    # the index is this build's; the page is rebuilt with it
    image = (p["image"].replace("http://", "https://") + "?width=1200") if p.get("image") else f"{site}app/share.png"
    title = f"{p['name']} · {city_name} · Walk Through Time"
    e = lambda s: html.escape(str(s), quote=True)  # noqa: E731
    desc = describe(p, city_name)
    return f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<title>{e(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{e(desc)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Walk Through Time">
<meta property="og:title" content="{e(p['name'])}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{e(image)}">
<meta property="og:url" content="{e(site)}data/share/{city_id}/{osm.replace('/', '-')}.html">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(p['name'])}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{e(image)}">
<link rel="canonical" href="{e(target)}">
<meta http-equiv="refresh" content="0; url={e(target)}">
<script>location.replace({json.dumps(target)});</script>
</head><body style="font-family:system-ui,sans-serif;padding:2em">
<p><a href="{e(target)}">Open {e(p['name'])} on the map</a></p>
</body></html>
"""


def main(city_id):
    c = city(city_id)
    data = load(city_id, "package")
    out = Path("data/share") / city_id
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    site, n = site_url(), 0
    for i, f in enumerate(data["buildings"]["features"]):
        p = f["properties"]
        if p.get("name") and p.get("osm"):
            (out / (p["osm"].replace("/", "-") + ".html")).write_text(page(p, i, city_id, c["name"], site))
            n += 1
    log(f"s09 share pages: {n} named buildings (data/share/{city_id}/)")
