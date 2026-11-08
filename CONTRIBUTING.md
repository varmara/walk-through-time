# Adding a layer

A layer lights up a set of buildings that share a piece of history and, where it can, says why each one is there.
There are two kinds.

## 1. A story layer (hand-written)

Add a layer to `CURATED` in `stories/<city>.py`:

```python
dict(
    id="markets", title="Markets",
    intro="Two or three plain sentences on the history behind the layer.",
    entries=[
        #  name shown on the card, Wikipedia article, the story, facts the article must contain
        E("Old Market Square", "en:Old Market Square",
          "The square has held markets since the Middle Ages.",
          ("market",)),
    ]),
```

Rules, checked by step `s05_curated` every time the pipeline runs:

- **Every story rests on a Wikipedia article.** `facts` are short strings (a year, a name, a key word) that must
  appear in the article. If one is missing, the story is dropped. If the article does not say it, the story
  should not either.
- **The story must be placed on a building.** The pipeline tries, in order: an explicit `at="osm:way/123"`, the
  article's Wikidata item tagged on an OpenStreetMap outline, the item's Historic England list entry, the article's
  coordinates, and finally the entry's name (or `at="name:..."`) matching a building or a named place inside one.
- **Stories are short and plain:** one or two sentences, what happened and when. Name legends as legends.
- **No personal details about private people.** Public figures are fine.

## 2. A rule layer (from an open dataset)

Add a function to `pipeline/layers.py` with the `@layer(...)` decorator. It receives a `Context` (buildings,
listed-building matches, named places, scheduled monuments) and returns `{building index: group}` or
`{building index: (group, {"story": "..."})}`. Helpers cover the common joins: `within(ctx, polygons, group)` and
`containing_places(ctx, test, group)`. A dataset the pipeline does not download yet needs a fetch step
(`pipeline/s00_fetch_*.py`) and an open licence.

## Checking your layer

```bash
python -m pipeline.run nottingham            # everything (downloads take a few minutes)
python -m pipeline.run nottingham --from s05  # only stories, layers and packaging, reusing downloads in work/
python3 -m http.server 8642                   # then open http://localhost:8642/nottingham/
```

`data/<city>-report.md` lists every story that was dropped and why, and how each kept story was placed.
On GitHub the pipeline runs automatically when `stories/`, `pipeline/` or `cities/` change.
