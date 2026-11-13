"""Write the site's pages from templates: the landing page with a row per city, and each city's map page and graph
page, filled in from the city's settings (cities/<city>.json: name, page.description, page.share, page.tagline).
Adding a city is then its settings (and stories), with no page to copy.

  python -m pipeline.pages            into this folder (index.html, <city>/), to open the site locally
  python -m pipeline.pages _site      into the site the build publishes
"""
import hashlib
import html
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"


def site_url():
    """The published site, e.g. https://varmara.github.io/walk-through-time/ (from GitHub Actions, or a default)."""
    repo = os.environ.get("GITHUB_REPOSITORY", "varmara/walk-through-time")
    owner, name = repo.split("/")
    return f"https://{owner}.github.io/{name}/" if name != f"{owner}.github.io" else f"https://{name}/"


def fill(template, values):
    out = template
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def version():
    """The version the pages' own files carry (?v=): a hash of app/ and lib/, so a phone keeps them until one
    changes (sw.js keeps files with ?v= until the version changes) and fetches them again as soon as one does."""
    h = hashlib.sha1()
    for p in sorted([*(ROOT / "app").rglob("*"), *(ROOT / "lib").rglob("*")]):
        if p.is_file() and "templates" not in p.parts:
            h.update(str(p.relative_to(ROOT)).encode() + b"\0" + p.read_bytes())
    return h.hexdigest()[:10]


def cities():
    return [json.loads(p.read_text()) | {"id": p.stem} for p in sorted((ROOT / "cities").glob("*.json"))]


def main(out=ROOT):
    out = Path(out)
    site = site_url()
    v = version()
    city_t, graph_t, index_t = ((TEMPLATES / f).read_text() for f in ("city.html", "graph.html", "index.html"))
    rows = []
    for c in cities():
        page = c.get("page", {})
        e = lambda s: html.escape(s or "", quote=True)  # noqa: E731
        values = {"id": c["id"], "name": e(c["name"]), "site": site, "v": v,
                  "description": e(page.get("description") or f"{c['name']} in 3D, every building coloured by the year it was built."),
                  "share": e(page.get("share") or f"Historic {c['name']} in 3D, building by building.")}
        (out / c["id"]).mkdir(parents=True, exist_ok=True)
        (out / c["id"] / "index.html").write_text(fill(city_t, values))
        (out / c["id"] / "graph.html").write_text(fill(graph_t, values))
        rows.append(f'    <a class="city" href="{c["id"]}/"><div><b>{e(c["name"])}</b><span>{e(page.get("tagline") or "3D")}</span></div>'
                    f'</a>')
    (out / "index.html").write_text(fill(index_t, {"cities": "\n".join(rows), "site": site}))
    print(f"pages: the landing page and the pages of {len(rows)} {'city' if len(rows) == 1 else 'cities'} in {out}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT)
