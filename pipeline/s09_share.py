"""Share pages: one tiny static page per named building, so a shared link shows a proper preview.

Twitter (X), Telegram, WhatsApp and others read Open Graph tags from the page at the link and do not run
JavaScript, so the map itself cannot describe a building. Each page carries the building's name, its summary
and its photo (or the site's picture) and sends a visitor straight on to the map at that building
(<city>/?b=<index>&osm=way/123). Pages are keyed by OpenStreetMap id, which stays the same between data builds.

Also one readable page per story layer and for People, and a contents page (layer-<id>.html, layers.html):
the layer's introduction, then each place with its story, its date and its source, each linking to the map with
the layer ticked and the place open. They have previews too, so a layer can be shared as well as a building.

Writes data/share/<city>/<type>-<id>.html (the folder is rebuilt each time, so removed buildings disappear;
a shared link keeps working, as the page is keyed by OpenStreetMap id).
"""
import html
import json
import shutil
import urllib.parse
from pathlib import Path

from .pages import site_url
from .common import city, load, log
from .texts import story_text


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
    title = f"{p.get('full') or p['name']} · {city_name} · Walk Through Time"
    e = lambda s: html.escape(str(s), quote=True)  # noqa: E731
    desc = describe(p, city_name)
    return f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<title>{e(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{e(desc)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Walk Through Time">
<meta property="og:title" content="{e(p.get('full') or p['name'])}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{e(image)}">
<meta property="og:url" content="{e(site)}data/share/{city_id}/{osm.replace('/', '-')}.html">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(p.get('full') or p['name'])}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{e(image)}">
<link rel="canonical" href="{e(target)}">
<meta http-equiv="refresh" content="0; url={e(target)}">
<script>location.replace({json.dumps(target)});</script>
<style>{STYLE}</style></head><body><main>
<p class="go"><a href="{e(target)}">Open {e(p['name'])} on the map</a></p></main>
</body></html>
"""


FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600&family=Spectral:ital,wght@0,400;0,500;0,600;1,400;1,500&display=swap">')

# the Survey sheet look of the map page (app/theme.css): survey paper, sepia ink, carmine links; Spectral and Public Sans
STYLE = """:root{--bg:#f4f2ec;--ink:#2a231d;--muted:#6d6459;--line:#d3cec2;--link:#7c1d2b;
--sans:"Public Sans",system-ui,-apple-system,sans-serif;--serif:"Spectral",Georgia,"Times New Roman",serif;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#2a2521;--ink:#ece6dc;--muted:#a59b8e;--line:#3d3631;--link:#eb8b95;color-scheme:dark}}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.55 var(--serif)}
main{max-width:640px;margin:0 auto;padding:24px 16px 64px}
a{color:var(--link);text-decoration-color:color-mix(in srgb,var(--link) 40%,transparent);text-underline-offset:2px}
.top{font:15px/1.4 var(--sans);display:flex;gap:18px;flex-wrap:wrap;margin:0 0 28px}
h1{font:italic 500 36px/1.1 var(--serif);margin:0 0 12px;letter-spacing:-.01em} .intro{font-size:18px}
h2{font:600 15px/1.3 var(--sans);color:var(--muted);margin:36px 0 0}
article{border-top:1px solid var(--line);padding:18px 0}
article h3{margin:0 0 4px;font:600 22px/1.25 var(--serif)} .meta{font:14px/1.4 var(--sans);color:var(--muted);margin:0 0 8px}
article p{margin:6px 0} .src{font:13px/1.4 var(--sans);color:var(--muted)}
.go{font:500 15px/1.4 var(--sans);margin-top:10px} ul.layers{padding:0;list-style:none}
ul.layers li{border-top:1px solid var(--line);padding:14px 0} ul.layers b{font:600 20px/1.3 var(--serif)}
ul.layers .n{font:14px var(--sans);color:var(--muted)}
footer{margin-top:44px;padding-top:16px;border-top:1px solid var(--line);font:13px/1.5 var(--sans);color:var(--muted)}"""


def doc(title, desc, image, url, body):
    e = lambda s: html.escape(str(s), quote=True)  # noqa: E731
    return f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<title>{e(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{e(desc)}">
<meta property="og:type" content="article"><meta property="og:site_name" content="Walk Through Time">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{e(image)}"><meta property="og:url" content="{e(url)}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}"><meta name="twitter:image" content="{e(image)}">
{FONTS}<style>{STYLE}</style></head><body><main>
{body}
</main></body></html>
"""


def ref_key(r):
    return f"b{r}" if isinstance(r, int) else r


def layer_pages(data, city_id, city_name, site, out):
    e = lambda s: html.escape(str(s), quote=False)  # noqa: E731
    feats, pins = data["buildings"]["features"], data.get("pins", {}).get("features", [])
    pin_by = {f"p{f['properties']['i']}": f["properties"] for f in pins}
    mapurl = f"{site}{city_id}/"
    top = (f'<p class="top"><a href="{mapurl}">The map of {e(city_name)}</a>'
           f'<a href="layers.html">All stories</a></p>')

    def place(r):
        """(name, built, image, stories) for a building or a pin."""
        if isinstance(r, int) and r < len(feats):
            p = feats[r]["properties"]
            built = None
            if p.get("y") is not None and p.get("f") != "area":
                built = p.get("dt") or (f"built {'in ' if p.get('f') == 'exact' else 'about '}{p['y']}")
            return (p.get("name") or p.get("listName") or "A building", built, p.get("image"),
                    [story_text(st, pins, data.get("templates")) for st in p.get("stories", [])])
        pp = pin_by.get(r)
        if pp:
            return pp.get("name"), None, None, [{"layer": pp.get("layer"), "text": pp.get("text"), "source": pp.get("source")}]
        return None, None, None, []

    def src_html(s):
        if not s or not s.get("url"):
            return ""
        return f'<p class="src">{e(s.get("kind") or "Source")}: <a href="{html.escape(s["url"])}">{e(s.get("title") or s["url"])}</a></p>'

    listed = []
    for L in data["layers"]:
        if L["kind"] not in ("stories", "people", "topics"):
            continue
        sections, image, n = [], None, 0
        for g in L["groups"]:
            items = [it for it in g.get("items", []) if it and it[1]]
            if not items:
                continue
            arts = []
            for name, refs, *hint in items:
                hint = hint[0] if hint else {}
                # a topic's story is the one its line names (a story's layer, a person's, a plaque's own words)
                want = hint.get("layer") or ("people" if hint.get("person") or hint.get("plaque") else None) \
                    if L["kind"] == "topics" else L["id"]
                person = L["kind"] == "people" or hint.get("person")
                stories, built, first = [], None, None
                for r in refs:
                    pname, pbuilt, pimg, st = place(r)
                    image = image or pimg
                    first = first or pname
                    built = built or pbuilt
                    for s in st:
                        if want and s.get("layer") != want:
                            continue
                        if person:       # a person's story names them (or is about their building)
                            last = name.split()[-1].lower()
                            if last not in (s.get("text") or "").lower() and len(refs) > 1:
                                continue
                        if s.get("text") and s["text"] not in [x["text"] for x in stories]:
                            stories.append(s)
                where = ", ".join(dict.fromkeys(filter(None, (place(r)[0] for r in refs[:6]))))
                more = f" and {len(refs) - 6} more" if len(refs) > 6 else ""
                link = (f"{mapurl}?layer={urllib.parse.quote(L['id'])}&focus={','.join(ref_key(r) for r in refs)}"
                        f"&name={urllib.parse.quote(name)}")
                meta = ([built] if built and not person else []) + ([f"{where}{more}"] if person and where else [])
                who = data.get("people", {}).get(name) if person else None
                arts.append(f"<article><h3>{e(name)}</h3>"
                            + (f'<p class="meta">{e(" · ".join(meta))}</p>' if meta else "")
                            + (f'<p><i>{e(who["text"])}</i></p><p class="src">Wikipedia: <a href="{html.escape(who["url"])}">'
                               f'{e(who["title"])}</a></p>' if who else "")
                            + "".join(f"<p>{e(s['text'])}</p>{src_html(s.get('source'))}" for s in stories[:4])
                            + f'<p class="go"><a href="{html.escape(link)}">Show on the map</a></p></article>')
                n += 1
            if arts:
                head = f"<h2>{e(g['title'])}</h2>" if len(L["groups"]) > 1 else ""
                sections.append(head + "".join(arts))
        if not n:
            continue
        intro = L.get("intro") or ""
        body = (top + f'<h1>{e(L["title"])}</h1>'
                + (f'<p class="intro">{e(intro)}</p>' if intro else "")
                + f'<p class="go"><a href="{mapurl}?layer={urllib.parse.quote(L["id"])}">See all {n} on the map</a></p>'
                + "".join(sections)
                + '<footer>Each story is checked against the source shown with it. Built by the Walk Through Time project '
                  'from open data: OpenStreetMap, Historic England, Wikidata, Wikipedia and Wikimedia Commons.</footer>')
        url = f"{site}data/share/{city_id}/layer-{L['id']}.html"
        img = (image.replace("http://", "https://") + "?width=1200") if image else f"{site}app/share.png"
        desc = intro if len(intro) <= 300 else intro[:297].rsplit(" ", 1)[0] + "…"
        (out / f"layer-{L['id']}.html").write_text(doc(f"{L['title']} · {city_name} · Walk Through Time",
                                                      desc or f"{L['title']} on the 3D map of historic {city_name}.", img, url, body))
        listed.append((L, n))
    body = (f'<p class="top"><a href="{mapurl}">The map of {e(city_name)}</a></p>'
            f"<h1>Stories of {e(city_name)}</h1><ul class=\"layers\">"
            + "".join(f'<li><a href="layer-{L["id"]}.html"><b>{e(L["title"])}</b></a> <span class="n">{n} places</span><br>{e(L.get("intro") or "")}</li>'
                      for L, n in listed) + "</ul>")
    (out / "layers.html").write_text(doc(f"Stories of {city_name} · Walk Through Time",
                                         f"Stories of {city_name}'s buildings, place by place.", f"{site}app/share.png",
                                         f"{site}data/share/{city_id}/layers.html", body))
    return len(listed)


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
    n_layers = layer_pages(data, city_id, c["name"], site, out)
    log(f"s09 share pages: {n} named buildings and {n_layers} layer pages (data/share/{city_id}/)")
