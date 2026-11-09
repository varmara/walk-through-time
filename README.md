# Walk Through Time

Explore cities building by building: when each one was built, what stood there before, and the stories behind them.

Live site: https://varmara.github.io/walk-through-time/

## Cities

| City | Page | Status |
|---|---|---|
| Nottingham | [`nottingham/`](nottingham/) | Prototype: city centre, the Meadows, and south of the Trent (Wilford, West Bridgford, Clifton) in 3D, coloured by construction year |

## How it works

```
open data ──► pipeline/ (Python, numbered steps) ──► data/<city>.json ──► <city>/index.html (MapLibre)
```

| Step | What it does |
|---|---|
| `s00_fetch_osm` | Buildings, roads, water, parks and named places from OpenStreetMap |
| `s00_fetch_heritage` | Listed buildings and scheduled monuments from Historic England |
| `s00_fetch_plaques` | Commemorative plaques (Open Plaques, public domain), as published with locations by Nottingham City Council |
| `s00_fetch_nature` | Nature Reserves, SSSIs and ancient woodland from Natural England; other nature reserves from OpenStreetMap |
| `s01_buildings` | Building outlines and heights, the base map, named places matched to buildings |
| `s02_listing` | Listed-building points matched to outlines |
| `s02_listing_dates` | Dates of listed buildings from Wikipedia's ward and parish lists (written from the Historic England entries) |
| `s03_wikidata` | Names, dates, architects, photos and Wikipedia links from Wikidata |
| `s04_curated` | Hand-written stories (`stories/<city>.py`) checked against Wikipedia and placed on buildings |
| `s05_dates` | One year per building with its precision (exact, approximate, century) and source; keeps every date that disagrees with it |
| `s06_layers` | Every layer resolved to its buildings: story layers and rule layers (`pipeline/layers.py`) |
| `s04_residents` | Well-known residents: people tied to the city in Wikidata whose Wikipedia article names a house number and street here, matched to the building by its OpenStreetMap address |
| `s06_photos` | Photos from Wikimedia Commons (many imported from Geograph): a current photo where Wikidata has none, and up to six old photographs per building, one per decade, never older than the building |
| `s06_summaries` | One to three sentences per named or listed building: the start of its Wikipedia article, or written only from facts in the data (use and street, date, listing, architect) |
| `s07_package` | Gathers everything the page shows, and writes the data report `data/<city>-report.md` |
| `s10_tiles` | Writes what the page loads: vector tiles (`data/<city>/tiles/`, made with [tippecanoe](https://github.com/felt/tippecanoe)), a small index of every building (`data/<city>.json`) and card files loaded when a card opens (`data/<city>/cards/`) |
| `s08_graph` | Writes `data/<city>-graph.json` for the graph page (`<city>/graph.html`): people and story themes linked to places by checked stories |

A GitHub Actions workflow (`.github/workflows/build-data.yml`) runs the pipeline twice a year
(1 January and 1 July), whenever the pipeline, stories or city settings change, and on demand from the
**Actions** tab, then commits the results.

Downloading OpenStreetMap takes most of an hour, so the last download is kept, compressed, on the `downloads` branch.
Runs triggered by a change reuse it, as long as the city's area and the download query are unchanged, and finish in a
few minutes. The twice-yearly runs, and manual runs with **refresh** ticked, download everything again and replace it.
Answers from the other web services (Wikipedia, Wikidata, Commons, Historic England, Natural England, Council Tax)
are saved too, in the Actions cache, and a build triggered by a change reuses them, asking only for what is new.
It also starts at the earliest step whose code changed (a story change starts at `s04_curated`), reusing the last
build's intermediate files (`pipeline/plan.py`). Changes to `common.py`, `run.py`, the workflow or a city's settings
run every step. The twice-yearly and **refresh** runs start from nothing.

```
cities/<id>.json          city settings: area (polygon and bounding box) and starting view
stories/<id>.py           hand-written story layers for the city
app/city.js, app/city.css the shared city page
<id>/index.html           one page per city
lib/                      MapLibre GL JS (BSD-3-Clause)
```

### How a building's year is chosen

- **Sources:** OpenStreetMap `start_date` on the building outline; a year given in a story, checked against its
  Wikipedia article; and Wikidata inception (`P571`) of the item linked to the building by its OpenStreetMap tag or
  its Historic England list entry (`P1216`).
- **Precision:** *exact* (one year), *approximate* (circa, a decade, a short range) or *century*. Less precise dates
  are drawn paler; buildings with no date are grey.
- **Order of trust:** OpenStreetMap and Wikipedia dates come first, the more precise one winning (OpenStreetMap first
  when equally precise, as its date is tagged on the outline itself). Wikidata is used only when neither has a date,
  because its item often describes an institution, such as a theatre company or a museum, rather than the building.
- **Disagreements:** when sources give dates that cannot both be right (their ranges do not overlap), the card shows
  all of them with their sources. They often describe different moments, such as a founding and a rebuilding.

### Layers

Story layers are hand-written, and every entry is checked against its sources: Wikipedia articles or Historic England
list entries. The People layer combines hand-written entries, every commemorative plaque in the area, and every
architect recorded in Wikidata, sorted by type of person. Rule layers are
built from open data: listed buildings by grade, buildings on scheduled monuments, and pubs. Nature areas are drawn on
the ground by type. On the page, layers are ticked in one sheet behind the Layers button, in any combination. See [CONTRIBUTING.md](CONTRIBUTING.md)
to add one.

## Adding a city

1. Add `cities/<id>.json` with the city's bounding box and starting view.
2. Optionally add `stories/<id>.py` with story layers.
3. Copy `nottingham/index.html` to `<id>/index.html` and change `data-city` and the titles.
4. Add the city to the list on the landing page `index.html`.

The workflow builds the new city's data on the next push.

## Acknowledgements

The pipeline structure, the checks on stories and the rule layers follow
[Amsterdam, building by building](https://github.com/alexbarakov/amsterdam-by-building) by Alex Barakov (MIT),
itself inspired by Sasha Bogachev's [Paris, building by building](https://paris.bogachev.fr).

## Data licences

- OpenStreetMap data © OpenStreetMap contributors, [ODbL](https://www.openstreetmap.org/copyright). The prepared files in `data/` are derived from OpenStreetMap and are available under the same licence.
- Natural England data, [Open Government Licence](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
- Historic England data, [Open Government Licence](https://historicengland.org.uk/terms/website-terms-conditions/open-data-hub/)
- Wikidata, CC0
- Open Plaques, public domain; plaque locations via Nottingham City Council
- Wikipedia text, CC BY-SA; stories link to the articles they rest on
- Historic maps reproduced with the permission of the [National Library of Scotland](https://maps.nls.uk/)
