# Sources and rights

Every story on the map says where its facts come from, and links there. This page sets out which sources may be used, how,
and which may not. How to write the notes themselves is in [CONTRIBUTING.md](CONTRIBUTING.md).

## The rule

**Facts only, in our own words, with a link.** A story retells what its sources say; it never copies their sentences.
Facts are not owned, but the way a page puts them is. So a note is written fresh from the facts, however freely the
source is licensed, and links the page it rests on.

## Which sources, and how

| Source | Use | How the build treats it |
| --- | --- | --- |
| **Wikipedia** (CC BY-SA) | Facts, retold. The first source to try for any story. | Read by the build: each note's `check:` words must be on the page, or the note is dropped. |
| **Openly licensed sites** (CC BY 4.0, the Open Government Licence), such as the History of Parliament | Facts, retold, with the licence named in the note's `note:` | Not read by the build: `read:` gives the date it was read. |
| **Sites with copyright and no open licence**, whose terms allow it: council walk leaflets, local history pages, a firm's own news page | Facts only, retold, with a link and the date read. Say so in `note:`, e.g. "facts only (no notice)". | Not read by the build. Read once, by hand. |
| **Historic England list entries** | Facts, from passages a person copies from the entry into `quote:` | Historic England blocks automated reading, so the check words are found in `quote:` instead. |
| **Picture Nottingham** and other picture collections | Links only, listed in `collections.md` | Never copied. |
| **CAMRA** | Facts and links only | Not read by the build. |

### Not used

- **Britannica**: its terms forbid rewriting its articles.
- **Mirrors of Historic England** (britishlistedbuildings.co.uk and the like): using them would route round Historic England's
  refusal of automated reading. Ask a person to paste the passage from the entry itself instead.
- **Any site that blocks or declines automated access**: we do not go round a refusal with another tool, a cache or a copy.
- **Anything for a private individual**: no stories that expose where a private person lives or works.

### Checking a new site

Before a site other than Wikipedia is used, look for its copyright notice or terms of use, and its licence if it has one:

1. An open licence (CC BY, CC BY-SA, the Open Government Licence): use it, and name the licence in `note:`.
2. Copyright, or no notice at all: facts only, retold, linked, and say so in `note:`.
3. Terms that forbid reuse or rewriting, or a site that refuses automated access: do not use it.

## Writing down where a fact came from

- **One Wikipedia page**: `source:` and `check:` in the properties.
- **One other page**: `source:` with `title:` and `read:` (the date it was read, `2026-11-16`).
- **Several pages**: the main one in `source:`, and a footnote on each sentence that rests on another:
  - `[^k]: https://… — check: word | word` for a Wikipedia page;
  - `[^k]: https://… — title: … — read: 2026-11-16` for any other.
- **Read once.** Other sites are read by hand, once, and their date read is recorded. The build never reads them, so a
  later change to the page cannot quietly change a story.
- **A date** (`when:`, `made:`) must be given by one of the story's pages, or by the footnoted sentence that holds it.
  The build log lists any date that no page gives, and the card then shows it without a source.

## Places

- **Approximate places.** When a source gives no exact spot ("near the foot of Clifton Grove"), the pin is put where the
  source points, and the card says so, briefly: "The pin is approximate." When something else is uncertain, the card says
  what: "Where the poll was held is not known." The `note:` property is for editors and is never shown.
- **Inside the map.** Every place must lie inside the city's boundary (`bbox` in `cities/<city>.json`); a story about a place
  outside it is left out.
- **Places stay places.** A pin is named for the place, never for a person (see CONTRIBUTING.md).

## Photos

- Photos come only from **Wikimedia Commons**, as freely licensed files, shown with their author and licence and linked
  to the file's page: the building's Wikidata photo, or else a geotagged Commons photo whose title names the building,
  or else the lead photo of its Wikipedia article (free files only, a JPEG, within 300 m of the building where Commons
  gives a position). The report lists the buildings that got a photo this way; `photo-articles.md` names an article
  for a few buildings that are not linked to theirs.
- Old pictures in collections that are not openly licensed are **linked, not copied** (`collections.md`).
- No photos of public figures are taken from the web or put into the map.

## The build and the web

- The build reads Wikipedia, Wikidata and Commons through their APIs, and identifies itself as
  `walk-through-time/1.0 (+https://github.com/varmara/walk-through-time)`; no personal email address is sent.
- Keys stay private: the visitor's MapTiler key lives only in their browser, and any key the build needs lives in a
  GitHub repository secret, never in the page.
