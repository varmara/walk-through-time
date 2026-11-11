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

An entry is a `##` heading (the name shown on the card), then its settings as `- key: value` lines, then the
story as plain text. The settings:

| Setting | Meaning |
|---|---|
| `source` | the Wikipedia article (`en:Title`) or Historic England list entry (`he:1254566`) the story rests on; for People, the person's article |
| `place` | People only: the place's article, which decides the building |
| `at` | where, when not where the article says: `name:…` (a building's name), `osm:way/123` (an outline), `nhle:1271444` (a list entry), `pin:lon,lat` (a pin) |
| `year` | when the building standing today was built or opened (`1855`, `c. 1420`, `1841..1844`) |
| `group` | People only, when Wikidata has no occupation: architects, writers, science, industry, sport, arts, public |
| `names` | `no` when the entry's name is not the building's name (an event: "The castle burned, 1831") |
| `check` | words the article must contain, separated by `\|` |
| `quote` | for a Historic England source: a passage copied from the list entry (their site blocks automated reading), one per line |
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

## 2. A rule layer (from an open dataset)

Add a function to `pipeline/layers.py` with the `@layer(...)` decorator. It receives a `Context` (buildings,
listed-building matches, named places, scheduled monuments) and returns `{building index: group}` or
`{building index: (group, {"story": "..."})}`. Helpers cover the common joins: `within(ctx, polygons, group)` and
`containing_places(ctx, test, group)`. Give the layer a `section` (the heading it sits under in the Layers sheet:
Heritage, Today, ...). A dataset the pipeline does not download yet needs a fetch step
(`pipeline/s00_fetch_*.py`) and an open licence.

## Checking your layer

```bash
tools/fetch-built.sh                          # the last build's data and work files, from GitHub
python -m pipeline.run nottingham --from s04  # then any step onwards, without downloading anything
python -m pipeline.run nottingham            # or everything (downloads take a few minutes)
python -m unittest discover -s tests -t .     # the checks the build runs before publishing
python3 -m http.server 8642                   # then open http://localhost:8642/nottingham/
```

`data/<city>-report.md` lists every story that was dropped and why, and how each kept story was placed.
On GitHub the pipeline runs automatically when `stories/`, `pipeline/` or `cities/` change.
