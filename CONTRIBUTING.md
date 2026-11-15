# Adding a layer

A layer lights up a set of buildings that share a piece of history and, where it can, says why each one is there.
There are two kinds.

## 1. A story layer (hand-written)

Everything written by hand is a note: one Markdown file in `stories/<city>/notes/`, as in an Obsidian vault,
which the folder can be opened as. A layer is an **index** note (`notes/indexes/`): its introduction, then its
stories listed as links, under a `##` heading for each group (each a tickbox of its own, its key the layer's id
and the heading: `barton-thrumpton`):

```markdown
---
type: index
id: barton
order: 14
---
Two or three plain sentences on the history behind the layer.

## Barton in Fabis
- [[St George's Church]]

## Thrumpton
- [[Thrumpton Hall]]
- [[The staircase]]
```

| Property | Meaning |
|---|---|
| `id` | the layer's id, which links use (`?layer=barton`); else made from the file's name |
| `section` | `Places` (the default: a small area of the map, where each of its stories lives) or `Threads` (a story told across the map, below) |
| `area` | for a place: the small heading it folds under in the Layers sheet (`The city`, `South of the Trent`, `West`, `North and east`) |
| `order` | its place in its section of the Layers sheet; else after those with one, by name |
| `kind` | `people` for the People layer and `facts` for "Did you know", whose members are not listed |

Each story is a note of its own in `notes/stories/` (events in `notes/events/`), listed in exactly one Places
index, which is its layer and group; threads may list it too:

```markdown
---
type: story
source: https://en.wikipedia.org/wiki/Thrumpton_Hall
check: Babington | priest hole | Pigot | 1617
at:
  - https://www.openstreetmap.org/way/55087219
---
The Powdrells, a Roman Catholic family, lost their house here after the Babington Plot; part of it survives inside
the hall, with a priest hole. The Pigots' rose-brick house around it was largely complete by 1617.
```

Besides those in Notes below, a story note can give:

| Property | Meaning |
|---|---|
| `name` | the name shown on the map, when the file's name differs (two "St Mary's Church" notes are `St Mary's Church, Clifton` and `St Mary's Church, Nottingham`) |
| `year` | when the building standing today was built or opened (`1855`, `c. 1420`, `1841..1844`) |
| `when` | when the story is set (`1952`, `c. 1200`, `1930s`, `13th century`): what its card is dated and ordered by, where the first year in its text is not it (Rock City tells of 1876 first, and is a story of `1980`) |
| `made` | for a statue or memorial: when it was put up, shown beside `when` (Robin Hood: `when: c. 1200`, `made: 1952`) |
| `names: no` | the story's name is not the building's name (an event: "The castle burned, 1831") |
| `quote` | for a Historic England source: passages copied from the list entry (their site blocks automated reading) |
| `architect` | who designed the building, when Wikidata does not say: their article (`en:Thomas Rickman`), or the name as the story writes it and the article (`Vincent Harris = en:E. Vincent Harris`), separated by `\|` |
| `note` | for editors only: why, where from; not shown on the map |

Rules, checked by step `s04_curated` every time the pipeline runs:

- **Every story rests on a source.** The words under `check` (a year, a name, a key word) must appear in the
  article. If one is missing, the story is dropped and the build log says which. If the article does not say it,
  the story should not either. Bulleted lists in the article count too.
- **The story is placed where its `at:` says:** a building's OpenStreetMap link, or a pin.
- **A story about an area or a lost building gets a pin** (`Name, latitude, longitude`): a village, a district, an estate,
  or a building that is gone. Otherwise the article's coordinates can land it on whatever house or shop stands
  there now, and that building takes the story's name.
- **A `year` is about the building standing there today** (built, rebuilt or opened), not an earlier building on
  the site. Its digits must appear in the article, and it becomes a date source.
- **Stories are short and plain:** one or two sentences, what happened and when. Name legends as legends.
- **No personal details about private people.** Public figures are fine.

### Notes: stories, events and people

Stories, events with the people in them, and people are notes: one Markdown file each in `stories/<city>/notes/`
(`stories/`, `events/`, `people/`), as in an Obsidian vault, which the folder can be opened as. A note's name is its file's
name; two notes cannot share one. Properties go at the top, the text below:

```markdown
---
type: event                    # story, event or person (or index, above)
source: https://en.wikipedia.org/wiki/1831_reform_riots      # one page, or a list of pages
check: 8 October 1831 | Duke of Newcastle                    # words the pages must contain between them
at:                            # its places
  - https://www.openstreetmap.org/way/16459858               # a building: its OpenStreetMap link
  - Lowe's Silk Mill, 52.9265, -1.2165                       # a new pin: its name, latitude, longitude
  - Bendigo's tomb                                           # a pin another note made
  - from the article                                         # a pin at the source article's point
see:
  - "[[Lowe's Silk Mill]]"     # other stories to link from this one
---
When the Lords threw out the Bill, a crowd burned the castle of the
[[Henry Pelham-Clinton, 4th Duke of Newcastle|Duke of Newcastle]].[^castle]

> [!fact]
> source: https://en.wikipedia.org/wiki/Nottingham_Castle
> check: 1878
>
> The castle reopened as a museum in 1878.

[^castle]: https://en.wikipedia.org/wiki/Nottingham_Castle — check: 1878 | museum
```

- **Sources.** A Wikipedia or Historic England page is checked: the build reads it and drops the note if a check
  word is missing. Another site's page is written from by hand: give `read:` (the date it was read) and keep
  facts and links only; the build does not read it. Historic England blocks the build, so a note resting on a
  list entry also gives `quote:`, the passages copied from it, which the check words are found in instead.
- **Footnotes** (`[^name]`) let one paragraph or fact rest on its own page, checked for its own words, or
  `— read: 2026-11-14` for another site's.
- **Links.** `[[Note]]` or `[[Note|words shown]]` links another note, or a person on the map by the name the
  People layer gives them (who need not have a note yet). On the person's card, the story is listed under "In
  these stories and events"; in the graph, the person is linked to its places. A link to a story is its "see
  also". A building is linked with its OpenStreetMap address, which opens it on the map. The build stops on a
  `[[link]]` that finds nothing.
- **Facts** (`> [!fact]`) show under "Did you know?" on the note's places, or the callout's own `at:`; in a
  person's note, with no `at:`, on their card. A note may hold several.
- **Places stay places.** A pin is named for the place (a tomb, an address), never for a person.

A **person** note (`type: person`) may give `kind:` (architects, writers, science, industry, sport, arts, faith,
military, public, other: else their occupations on Wikidata decide) and `wikipedia:` (the article whose opening
starts their card, when their name does not find it, or `no`). Their text follows the article's opening on their
card, and with `at:` it is told on those places' cards under their name. A person note may be properties only:
the article's opening is then their card.

People found automatically by an address in their Wikipedia article are placed only on a building of that
address in the town the article names; once a person has a note, the automatic one is left out, so a wrong match
is fixed by writing the note.

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

### Places and threads

Every story lives in one **place**: a Places index for a small area of the map (the castle rock, the Lace Market,
Wilford, Ruddington). A **thread** follows one story across the map, through any places: the castle and the
Crown, frames and lace, coal and getting about. It is a layer of its own in the Layers sheet's Threads section and
a theme in the graph. A thread is an index note with `section: Threads`, and may list people, plaques and
buildings as well as stories; anything can be on several threads, and a card lists the threads it is on, each
opening that thread. Stories do not link to the next one in a thread in their text, so a story can join a thread
anywhere without others changing: the cards keep date order, and the `##` headings are its chapters, by period
or by strand (The Civil War, The dukes' mansion).

```markdown
---
type: index
section: Threads
id: civilwar
---
Nottingham in the Civil War: where the King raised his standard, the castle held for Parliament, and a Royalist
house stormed and burned.

## The Civil War
- [[The storming of Shelford House]]                         a story or event
- [[Charles I]]                                              a person: a note, or someone on the map by name
- plaque: The Chilwell Explosion, 1st July 1918              a plaque, by its title on the map
- [Wollaton Hall](https://www.openstreetmap.org/way/4438894) a building
```

A thread tells nothing new: each card shows the story, plaque or person as its own layer tells it, with its
source. The build stops on a line that finds nothing or more than one thing (a plaque two places share), naming
the note and line.

### Date order

Every set of numbered cards runs in date order, and each card shows its date: a place's groups, a thread, a
person's places. A story is dated by its `when:`, else the first year in its text; a plaque by the first year in
its words (not when it was put up); a person by the year they were born; a building by the year it was built; the
undated come last, in the index's order.

A thread can date a line itself, where the story or person comes into it at another time: the date, a colon, then
the member.

```markdown
- 1847: [[Feargus O'Connor]]          elected MP that year (else he would sort by his birth, 1796)
- 1643: [[St Nicholas' Church]]       pulled down in the siege (its own story is dated by the rebuilding, 1678)
- 1952: [[Statue of Robin Hood]]      on the On a plinth thread, by when it was put up; its card shows both dates
```

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
words, what happened at this place (the Here column of `plaque-people.md`: each of a person's plaques tells its
own part), then who they were from Wikipedia, or for someone with no article their note (written by hand from
another site, with its link and the date it was read). A Wikidata tag on a building that points at a
person (an architect's, by mistake) is left out.

A plaque to a place takes its own title from the plaque list ("Moot Hall", "Swine Green"); one with neither a
person, a label nor a title is named from its first words and listed in the build report for a label. Places
that share a name are one set on the map only when they are next to each other (a pub of two outlines); a person
is one set wherever they are.

