#!/bin/sh
# Raw downloads kept between builds in the repo's "raw-data" release, so they outlive GitHub's build cache
# (which drops anything unused for a week) and nothing is downloaded twice:
#   web-open.tar.NN   saved answers from openly licensed sources (cache/open/, see pipeline/web.py), in parts
#                     of under 2 GB; their dates are kept, so the age limit still applies after a round trip
#   ground-*.zip      the Environment Agency's ground model squares as downloaded (pipeline/s09_ground.py)
#   hills-<city>-<fingerprint>.tar   a city's hills as made from them (s09_ground), so they are not made again
#                     when the build cache has been dropped; one per city, the older removed
# "fetch" does not download the squares (about 700 MB): only the build that makes the hills needs them, and
# s09_ground fetches those it needs from the release itself (their names are in raw/assets.txt).
# Only openly licensed data goes here (the release is public): council map data and other sites' pages stay in
# the build cache (cache/other/).
#
#   sh tools/raw.sh fetch     before the pipeline: release -> raw/ and cache/open/ (keeping newer local copies)
#   sh tools/raw.sh save      after it: changed or new parts -> release
# Needs the gh command and GH_TOKEN (the build's own token can write releases).
set -e
TAG=raw-data
RAW=${WTT_RAW:-raw}
CACHE=${WTT_CACHE:-cache}
mkdir -p "$RAW" "$CACHE/open"

case "$1" in
fetch)
  if ! gh release view "$TAG" >/dev/null 2>&1; then echo "No $TAG release yet"; touch "$RAW/.fetched"; exit 0; fi
  gh release download "$TAG" -D "$RAW" --clobber -p 'web-open.tar.*' -p 'hills-*.tar'
  gh release view "$TAG" --json assets -q '.assets[].name' > "$RAW/assets.txt"
  if ls "$RAW"/web-open.tar.* >/dev/null 2>&1; then
    cat "$RAW"/web-open.tar.* | tar -x -C "$CACHE" --skip-old-files
    echo "Saved web answers from the release: $(find "$CACHE/open" -name '*.gz' | wc -l) in all"
  fi
  echo "In the release: $(grep -c '^ground-' "$RAW/assets.txt") ground squares (fetched only to make hills)," \
       "hills fetched: $(ls "$RAW"/hills-*.tar 2>/dev/null | wc -l)"
  touch "$RAW/.fetched"
  ;;
save)
  if ! gh release view "$TAG" >/dev/null 2>&1; then
    gh release create "$TAG" --title "Raw downloads" --latest=false --notes "Raw data the build downloaded, kept so \
it is not downloaded again within a month (tools/raw.sh). Not part of the site. Openly licensed only: OpenStreetMap \
(ODbL, © OpenStreetMap contributors); Environment Agency LIDAR, Historic England, Natural England, ONS and VOA data \
(Open Government Licence); Wikidata (CC0); Wikipedia and Wikimedia Commons text (CC BY-SA); Mapping Museums \
(Birkbeck, CC BY 4.0); Open Plaques (public domain)."
  fi
  have=$(gh release view "$TAG" --json assets -q '.assets[].name')
  # the open answers, packed the same way every time (names sorted, no owners) so unchanged parts match
  rm -rf "$RAW/new" && mkdir -p "$RAW/new"
  tar -c --sort=name --owner=0 --group=0 --numeric-owner -C "$CACHE" open | split -b 1900m -d - "$RAW/new/web-open.tar."
  for f in "$RAW"/new/web-open.tar.*; do
    name=${f##*/}
    if [ -f "$RAW/$name" ] && cmp -s "$f" "$RAW/$name"; then continue; fi
    gh release upload "$TAG" "$f" --clobber && echo "Uploaded $name"
  done
  for name in $(echo "$have" | grep '^web-open\.tar\.' || true); do      # parts no longer needed
    [ -f "$RAW/new/$name" ] || { gh release delete-asset "$TAG" "$name" -y && echo "Removed $name"; }
  done
  rm -rf "$RAW/new"
  # ground squares new to the release (a square's name has its survey year: one kept never changes)
  for f in "$RAW"/ground-*.zip; do
    [ -f "$f" ] || continue
    echo "$have" | grep -qx "${f##*/}" || { gh release upload "$TAG" "$f" --clobber && echo "Uploaded ${f##*/}"; }
  done
  # hills made by this build: uploaded, and the city's older hills removed
  for f in "$RAW"/hills-*.tar; do
    [ -f "$f" ] || continue
    name=${f##*/}
    if [ "$f" -nt "$RAW/.fetched" ] || ! echo "$have" | grep -qx "$name"; then
      gh release upload "$TAG" "$f" --clobber && echo "Uploaded $name"
      for old in $(echo "$have" | grep "^${name%-*}-[0-9a-f]*\.tar\$" || true); do
        [ "$old" = "$name" ] || { gh release delete-asset "$TAG" "$old" -y && echo "Removed $old"; }
      done
    fi
  done
  # (squares' download dates are no longer kept: nothing asks a square's age)
  if echo "$have" | grep -qx dates.txt; then gh release delete-asset "$TAG" dates.txt -y; fi
  ;;
*) echo "usage: sh tools/raw.sh fetch|save"; exit 2 ;;
esac
