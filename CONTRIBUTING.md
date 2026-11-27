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
| `area` | makes the thread a place: a small area of the map, where each of its stories lives, folded under this heading in "Around the map" (`The city`, `South of the Trent`, `West`, `North and east`). Without it, the thread is a theme |
| `order` | its place in its section of the Layers sheet; else after those with one, by name |
| `sort` | `as listed`: a place's stories in the order written, not by date (Wilford's Roman ford, found in 1900, tells of the earliest times and comes first) |
| `kind` | `people` for the People layer, whose members are not listed |

Each story is a note of its own in `notes/stories/` (events in `notes/events/`), listed in at least one Places
index (Trent Bridge is in both West Bridgford and the Meadows); threads may list it too:

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
| `made` | for a statue or memorial: when it was put up, shown beside `when` (Robin Hood: `when: 13th century`, `made: 1952`) |
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
- **A pin whose place is not known exactly ends with `, approximate`** (or `, ~300 m` for another radius): the map
  draws a pale halo of that size (200 m by default) round it, and its card says "place approximate, within about
  200 m", so the text need not say so.
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
  - Saxon Nottingham, 52.9513, -1.1428, approximate         # a pin not placed exactly: a halo of 200 m (or ", ~300 m")
  - Bendigo's tomb                                           # a pin another note made
  - from the article                                         # a pin at the source article's point
see:
  - "[[Lowe's Silk Mill]]"     # other stories to link from this one
---
When the Lords threw out the Bill, a crowd burned the castle of the
[[Henry Pelham-Clinton, 4th Duke of Newcastle|Duke of Newcastle]]. It reopened as a museum in 1878.[^castle]

[^castle]: https://en.wikipedia.org/wiki/Nottingham_Castle — check: 1878 | museum
```

- **Sources.** A Wikipedia or Historic England page is checked: the build reads it and drops the note if a check
  word is missing. Another site's page is written from by hand: give `read:` (the date it was read) and keep
  facts and links only; the build does not read it. Historic England blocks the build, so a note resting on a
  list entry also gives `quote:`, the passages copied from it, which the check words are found in instead.
  Which sites may be used, and how: [SOURCES.md](SOURCES.md).
- **Footnotes** (`[^name]`) let one sentence or paragraph rest on its own page, checked for its own words, or
  `— read: 2026-11-14` for another site's.
- **Footnotes the build adds.** A story with several sources gets a footnote after each sentence, to the page
  that holds the check words in that sentence; and its `when:` and `made:` dates are footnoted to the page that
  gives them (the build log lists a date that none of its pages gives: it is shown without a source).
- **Links.** `[[Note]]` or `[[Note|words shown]]` links another note, or a person on the map by the name the
  People layer gives them (who need not have a note yet). On the person's card, the story is listed under "In
  these stories and events"; in the graph, the person is linked to its places. A link to a story is its "see
  also". A building is linked with its OpenStreetMap address, which opens it on the map. The build stops on a
  `[[link]]` that finds nothing.
- **A fact goes in the text**, with a footnote when it comes from another page. Where it has a place or a time of
  its own, it is a story or event of its own.
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
| `photo-articles.md` | a Wikipedia article whose lead photo is a building's photo, for a building not linked to it (by OpenStreetMap outline); used only when Wikidata and Commons have none |
| `wikipedia.md` | the Wikipedia article for a plaque's person, when the plaque's name is not the article's |
| `plaques.md` | a label, group or type for a plaque, by the start of its inscription or its subject |
| `collections.md` | collections of old pictures that are linked, not copied (not openly licensed) |
| `credits.md` | the name each linked collection's website goes by, in the card's "More photos from …" |
| `architects.md` | architects as OpenStreetMap or a Wikipedia table names them (`T. Cecil Howitt`), made plain, with their article when the name alone does not find it, or another page about them (linked only) when there is no article |
| `old-lines.md` | the years a disused railway or lost canal opened and closed, by its name in OpenStreetMap, with the source checked; these come before Wikidata's and OpenStreetMap's own dates |
| `architects-to-find.md` | architects on the map with no article or page found yet, and where to look; for editors, not read by the build |

### Places and threads

Every story lives in at least one **place**: a Places index for a small area of the map (the castle rock, the Lace Market,
Wilford, Ruddington). A place is told as a thread of where it is: listed in the Stories sheet under "Around the map",
folded by its `area`, it may list the people, plaques and buildings that belong there as well as its stories, and its
lines may carry thread dates (`- 1970: [[Paul Smith]]`). Its stories and events live there (the first place that
lists one is its home); its people, plaques and buildings are found where the map has them. A **thread** of a theme
follows one story across the map, through any places: the castle and the Crown, frames and lace, coal and getting
about. It is listed under "Themes", opening as numbered cards, and is a theme in the graph. Every index note is a thread: one with an
`area:` is a place (listed under "Around the map", usually with `sort: as listed`), one without is a theme; a thread may list people, plaques and buildings as well as stories; anything can be on several threads, and a card lists the threads it is on, each
opening that thread. Stories do not link to the next one in a thread in their text, so a story can join a thread
anywhere without others changing: the cards keep date order, and the `##` headings are its chapters, by period
or by strand (The Civil War, The dukes' mansion).

A thread of several chapters opens each chapter with an introduction card of its own, so the chapters do not mix:
write it as prose under the `##` heading, before the chapter's first member. Every chapter of such a thread needs
one (a test checks), even a chapter of one story; a thread of a single chapter needs none. This holds for places and themes
alike. An introduction sets the stage: the background the cards below it leave out (why it happened then, what
the wider country was going through), not a retelling of their own words. Its facts are footnoted as a story's
are: `[^k]` in the text, and the `[^k]: …` line anywhere in the index (below the last member reads best). The
build checks them the same way and leaves out a footnote whose page fails, with a line in its log.

```markdown
## The Civil War
In August 1642 Charles I raised his standard outside the castle. Parliament then held it …
- [[Charles I raised his standard, 1642]]
```

```markdown
---
type: index
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
its words (not when it was put up); a person by the year they were born; a building by the year it was built; an
undated item stays after the one listed before it. An index with `sort: as listed` keeps the order it is written in
instead: every place does, so that each reads from its beginning (Wilford's Roman ford, found in 1900, tells of the
earliest times and comes first).

A thread can date a line itself, where the story or person comes into it at another time: the date, a colon, then
the member.

```markdown
- 1847: [[Feargus O'Connor]]          elected MP that year (else he would sort by his birth, 1796)
- 1643: [[St Nicholas' Church]]       pulled down in the siege (its own story is dated by the rebuilding, 1678)
- 1952: [[Statue of Robin Hood]]      on the On a plinth thread, by when it was put up; its card shows both dates
```

### A checklist for a new story

The mistakes that have dropped stories or stopped the build, and how to avoid them. Which sources may be used, and
how, is in [SOURCES.md](SOURCES.md).

**Sources and words**

- [ ] **Check words are copied from the page, not remembered.** The build looks for each word exactly as the article
  writes it. "19 November 1993" failed where the article gave only "1993". A sentence that a summary of the page
  showed, but the article's text did not hold, dropped the Gotham story. Prefer short, distinctive words: years,
  names, figures (`1852 | Star Brewery | Greenall`).
- [ ] **Every sentence rests on a source.** Trim anything the pages do not say, however likely it seems: a cause, a
  "famous", an extra date. A sentence from another page gets its own footnote.
- [ ] **Our own words**, in British English. Retell; never copy a sentence.
- [ ] **A non-Wikipedia page** has `title:` and `read:` (or a footnote with them), and a `note:` saying how it may be
  used ("facts only (no notice)", "CC BY 4.0").

**Dates**

- [ ] **`when:` must be found in a page.** The build matches `1850`, `c. 1750` (as 1750), `1930s`, `13th century` (also
  "thirteenth century", "13th-century", "12th and 13th century"). A date that sits in a footnoted sentence is found
  through that footnote. Otherwise the build log lists it and the card shows it without a source.
- [ ] **Undated is allowed**: leave `when:` out rather than guess. In a thread, an undated story stays after the one
  listed before it.

**Places**

- [ ] **Inside the map.** Check the point against the city's boundary (`bbox` in `cities/<city>.json`): a church just over the
  edge was left out.
- [ ] **On the right side of the river.** A pin on the Trent's other bank puts the story in the wrong village; check
  pins near the river against the map.
- [ ] **A building's own outline** where OpenStreetMap has one (`https://www.openstreetmap.org/way/…`), else a pin,
  with a `note:` saying why. A building of several parts (the two decks of Clifton Bridge) lists every part, the one the
  story starts with first.
- [ ] **Reuse a pin by its name.** A pin is made once, by name and point; another note gives just the name. Making the
  same pin twice at different points stops the build ("the pin … is made twice, at different points").
- [ ] **Approximate?** Say so on the card, briefly: "The pin is approximate." (SOURCES.md, Places).

**Names and links**

- [ ] **The note's name is new.** Two notes cannot share one, and that includes indexes: a place called "Castle
  Marina" and a story called "Castle Marina" clash.
- [ ] **`[[links]]` find something**: another note, or a person by the name the People layer gives them. The build stops
  on a link that finds nothing.

**Placing it**

- [ ] **A Places index lists it.** The first place that lists a story is its home, and the build stops on a story no
  place lists.
- [ ] **A thread lists it where it belongs** for the telling, not wherever it could fit. If a story a thread lists is
  dropped, the build fails, so fix the story rather than unlisting it.
- [ ] **In a place, the order is the story's order** (`sort: as listed`), from its beginning; in a theme, the date order
  decides, and a line can carry its own date (`- 1964: [[…]]`).
- [ ] **The introduction still fits** once stories are added or moved: update the index's first paragraph.

**Before you push**: run the checks in [Checking your layer](#checking-your-layer), then watch the "Build and publish"
run and read its log for `dropped`, `none of its pages` and `fix these`.

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

