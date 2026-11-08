# Walk Through Time

Explore cities building by building: when each one was built, what stood there before, and the stories behind them.

Live site: https://varmara.github.io/walk-through-time/

## Cities

| City | Page | Status |
|---|---|---|
| Nottingham | [`nottingham/`](nottingham/) | Prototype: city centre in 3D, coloured by construction year |

## How the Nottingham map works

The page loads its data live in the browser:

- **Buildings, heights, roads, water**: OpenStreetMap via the Overpass API
- **Construction years**: Wikidata (`P571` inception), then OpenStreetMap `start_date`; approximate dates are drawn paler, buildings with no date are grey
- **Listed buildings**: Historic England National Heritage List for England
- **Historic basemap (optional)**: National Library of Scotland OS six-inch map 1888–1913 via MapTiler (needs a free MapTiler key, stored only in the viewer's browser)

## Adding a city

Each city lives in its own folder (`leeds/index.html`, …) and is linked from the landing page `index.html`.

## Data licences

- OpenStreetMap data © OpenStreetMap contributors, [ODbL](https://www.openstreetmap.org/copyright)
- Historic England data, [Open Government Licence](https://historicengland.org.uk/terms/website-terms-conditions/open-data-hub/)
- Wikidata, CC0
- Historic maps reproduced with the permission of the [National Library of Scotland](https://maps.nls.uk/)
