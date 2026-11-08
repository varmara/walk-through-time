# Walk Through Time

Explore cities building by building: when each one was built, what stood there before, and the stories behind them.

Live site: https://varmara.github.io/walk-through-time/

## Cities

| City | Page | Status |
|---|---|---|
| Nottingham | [`nottingham/`](nottingham/) | Prototype: city centre in 3D, coloured by construction year |

## How it works

```
cities/<id>.json          city settings: area (bounding box) and starting view
scripts/build_city.py     fetches and joins the data for one city
data/<id>.json            the prepared map data (written by GitHub Actions)
app/city.js, app/city.css the shared city page
<id>/index.html           one page per city
lib/                      MapLibre GL JS (BSD-3-Clause)
```

A GitHub Actions workflow (`.github/workflows/build-data.yml`) runs every Monday, whenever the script or a city file changes, and on demand from the **Actions** tab. It fetches the sources, joins them and commits `data/<id>.json`. The page loads that file, so visitors don't wait for the source servers. If the file doesn't exist yet, the page fetches the sources live in the browser instead.

### Sources and how a building's year is chosen

- **Buildings, heights, roads, water, parks**: OpenStreetMap via the Overpass API
- **Construction year**, in order of preference: an exact Wikidata date (`P571` inception), an exact OpenStreetMap `start_date`, then approximate dates from either. Approximate dates are drawn paler; buildings with no date are grey.
- **Listed buildings**: Historic England National Heritage List for England. Wikidata items are also matched by list entry number (`P1216`).
- **Historic basemap (optional)**: National Library of Scotland OS six-inch map, 1888–1913, via MapTiler. Needs a free MapTiler key, which is stored only in the visitor's browser.

## Adding a city

1. Add `cities/<id>.json` with the city's bounding box and starting view.
2. Copy `nottingham/index.html` to `<id>/index.html` and change `data-city` and the titles.
3. Add the city to the list on the landing page `index.html`.

The workflow builds the new city's data on the next push.

## Data licences

- OpenStreetMap data © OpenStreetMap contributors, [ODbL](https://www.openstreetmap.org/copyright). The prepared files in `data/` are derived from OpenStreetMap and are available under the same licence.
- Historic England data, [Open Government Licence](https://historicengland.org.uk/terms/website-terms-conditions/open-data-hub/)
- Wikidata, CC0
- Historic maps reproduced with the permission of the [National Library of Scotland](https://maps.nls.uk/)
