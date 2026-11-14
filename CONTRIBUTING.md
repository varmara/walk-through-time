# Adding a layer

A layer lights up a set of buildings that share a piece of history and, where it can, says why each one is there.
There are two kinds.

## 1. A story layer (hand-written)

Stories live in Markdown files in `stories/<city>/`, one file per layer, named `NN-<id>.md` (`NN` sets the order
in the Layers sheet). Edit them on GitHub or in any text editor; the next data build checks and publishes them.

```markdown
# Markets
id: markets

Two or three plain sentences on the history behind the layer.

## Old Market Square
- source: en:Old Market Square, Nottingham
- at: pin:-1.1497,52.9529
- check: market | 1928

The square has held markets since the Middle Ages; Goose Fair was held here until 1928.
```

A layer that covers several places or themes can split into tickboxes: a `groups:` line under `id:`, each group
`key = Title` (keys unique across all layers), and a `- group: key` line on every entry:

```markdown
# Barton in Fabis and Thrumpton
id: barton
groups: barton-fabis = Barton in Fabis | thrumpton = Thrumpton
```

An entry is a `##` heading (the name shown on the card), then its settings as `- key: value` lines, then the
story as plain text. The settings:

| Setting | Meaning |
|---|---|
| `source` | the Wikipedia article (`en:Title`), Historic England list entry (`he:1254566`) or another site's page (`web:https://…`) the story rests on; for People, the person's article or page |
| `read`, `title` | for another site's page: the date it was read (`2026-11-14`) and the page's title. Such a story is read once by hand and written as a summary in our own words, never its text; the build does not read the site and there is no `check` line; it needs an `at`, and the card cites the site with the date it was read |
| `place` | People only: the place's article, which decides the building |
| `at` | where, when not where the article says: `name:…` (a building's name), `osm:way/123` (an outline), `nhle:1271444` (a list entry), `pin:lon,lat` (a pin), `pin:article` (a pin at the article's own point, or the `place` article's: a village, a site where nothing stands) |
| `year` | when the building standing today was built or opened (`1855`, `c. 1420`, `1841..1844`) |
| `group` | in a layer with `groups:`, the entry's group (its own tickbox); People: the kind of person, when Wikidata has no occupation (architects, writers, science, industry, sport, arts, public) |
| `where` | a pin's own name, the place it marks (`21 Regent Street`, `Bendigo's tomb`), so the pin is a place and the person is told under their name |
| `see` | other stories to link from this one ("See also" on its card), by their headings, separated by `\|`; write `layer/heading` when two stories share a heading (`culture/Nottingham Castle`) |
| `names` | `no` when the entry's name is not the building's name (an event: "The castle burned, 1831") |
| `check` | words the article must contain, separated by `\|` |
| `quote` | for a Historic England source: a passage copied from the list entry (their site blocks automated reading), one per line |
| `architect` | who designed the building, when Wikidata does not say: their Wikipedia article (`en:Thomas Rickman`), or the name as the story writes it and the article (`Vincent Harris = en:E. Vincent Harris`), separated by `\|`; fills the card's Architect row and links their names |
| `note` | for editors only: why, where from; not shown on the map |

A layer file can say `kind: people` (pairs of a person and a place) or `kind: facts` ("Did you know" facts, each
shown on its building's card).

Rules, checked by step `s04_curated` every time the pipeline runs:

- **Every story rests on a source.** The words under `check` (a year, a name, a key word) must appear in the
  article. If one is missing, the story is dropped and the build log says which. If the article does not say it,
  the story should not either. Bulleted lists in the article count too.
- **The story must be placed on a building or a pin.** The pipeline tries, in order: `at`, the article's Wikidata
  item tagged on an OpenStreetMap outline, the item's Historic England list entry, the article's coordinates, and
  finally the entry's name matching a building or a named place inside one.
- **A story about an area or a lost building gets a pin** (`at: pin:lon,lat`): a village, a district, an estate,
  or a building that is gone. Otherwise the article's coordinates can land it on whatever house or shop stands
  there now, and that building takes the story's name.
- **A `year` is about the building standing there today** (built, rebuilt or opened), not an earlier building on
  the site. Its digits must appear in the article, and it becomes a date source.
- **Stories are short and plain:** one or two sentences, what happened and when. Name legends as legends.
- **No personal details about private people.** Public figures are fine.

### People

In a `kind: people` layer, the facts must appear in the person's and the place's articles taken together:

```markdown
## Thomas Cecil Howitt
- source: en:Thomas Cecil Howitt
- place: en:Council House, Nottingham
- check: Howitt | Council House

The architect Thomas Cecil Howitt designed the Council House.
```

The person's type comes from their occupations on Wikidata; each type becomes its own tickbox on the page.

On a building's card each person's story sits under their name, with one line on who they were; the name opens
the person's card (who they were, their years from Wikidata, and all their places on the map). People found
automatically by an address in their Wikipedia article are placed only on a building of that address in the
town the article names; once a person has a hand-written entry here, the automatic one is left out, so a wrong
match is fixed by writing the entry (with a `note` saying it was checked).

### Corrections and links

Tables in the same folder, each with a Note column saying why:

| File | What it holds |
|---|---|
| `names.md` | names chosen by hand, by OpenStreetMap outline |
| `titles.md` | titles "what it was · what it is" chosen by hand |
| `tags.md` | corrections to OpenStreetMap tags (`(remove)` drops one); fix them in OpenStreetMap too |
| `wikipedia.md` | the Wikipedia article for a plaque's person, when the plaque's name is not the article's |
| `plaques.md` | a label, group or type for a plaque, by the start of its inscription or its subject |
| `collections.md` | collections of old pictures that are linked, not copied (not openly licensed) |
| `credits.md` | the name each linked collection's website goes by, in the card's "More photos from …" |
| `architects.md` | architects as OpenStreetMap or a Wikipedia table names them (`T. Cecil Howitt`), made plain, with their article when the name alone does not find it, or another page about them (linked only) when there is no article |
| `old-lines.md` | the years a disused railway or lost canal opened and closed, by its name in OpenStreetMap, with the source checked; these come before Wikidata's and OpenStreetMap's own dates |
| `architects-to-find.md` | architects on the map with no article or page found yet, and where to look; for editors, not read by the build |

## 2. A rule layer (from an open dataset)

Add a function to `pipeline/layers.py` with the `@layer(...)` decorator. It receives a `Context` (buildings,
listed-building matches, named places, scheduled monuments) and returns `{building index: group}` or
`{building index: (group, {"story": "..."})}`. Helpers cover the common joins: `within(ctx, polygons, group)` and
`containing_places(ctx, test, group)`. Give the layer a `section` (the heading it sits under in the Layers sheet:
Heritage, Today, ...). A dataset the pipeline does not download yet needs a fetch step
(`pipeline/s00_fetch_*.py`) and an open licence.

## Checking your layer

```bash
tools/fetch-built.sh                          # the last build's data and work files, from GitHub, and the pages
python -m pipeline.run nottingham --from s04  # then any step onwards, without downloading anything
python -m pipeline.run nottingham            # or everything (downloads take a few minutes)
python -m unittest discover -s tests -t .     # the checks the build runs before publishing
python3 -m http.server 8642                   # then open http://localhost:8642/nottingham/
node tests/page/smoke.cjs http://localhost:8642/   # and the browser check (needs Playwright)
```

`data/<city>-report.md` lists every story that was dropped and why, and how each kept story was placed.
`data/<city>-changes.md` lists every building whose title, year or listing changed since the last build.
When you fix a name, add the building to `tests/expected/<city>-names.md` so the fix cannot quietly break again.
On GitHub the pipeline runs automatically when `stories/`, `pipeline/` or `cities/` change.

## Places stay places

A pin or a building is never titled with a person's bare name. A plaque is "Plaque to Dame Laura Knight", or the
place it marks (plaques.md); a statue is "Statue of Brian Clough"; a People pin takes `where:`. Who a plaque
remembers is listed in `plaque-people.md`, and their card tells their story under their own name: the plaque's
words, then who they were from Wikipedia, or for someone with no article a summary in `about.md` (written by
hand from another site, with its link and the date it was read). A Wikidata tag on a building that points at a
person (an architect's, by mistake) is left out.

