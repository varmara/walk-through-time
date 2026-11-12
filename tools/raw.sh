#!/bin/sh
# Raw downloads kept between builds in the repo's "raw-data" release, so they outlive GitHub's build cache
# (which drops anything unused for a week) and nothing is downloaded twice within a month:
#   web-open.tar.NN   saved answers from openly licensed sources (cache/open/, see pipeline/web.py), in parts
#                     of under 2 GB; their dates are kept, so the age limit still applies after a round trip
#   ground-*.zip      the Environment Agency's ground model squares as downloaded (pipeline/s09_ground.py)
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
  gh release download "$TAG" -D "$RAW" --clobber
  if ls "$RAW"/web-open.tar.* >/dev/null 2>&1; then
    cat "$RAW"/web-open.tar.* | tar -x -C "$CACHE" --skip-old-files
    echo "Saved web answers from the release: $(find "$CACHE/open" -name '*.gz' | wc -l) in all"
  fi
  # downloading resets a file's date: dates.txt has when each was really downloaded
  if [ -f "$RAW/dates.txt" ]; then
    while read -r name when; do [ -f "$RAW/$name" ] && touch -d "@$when" "$RAW/$name"; done < "$RAW/dates.txt"
  fi
  echo "Ground squares from the release: $(ls "$RAW"/ground-*.zip 2>/dev/null | wc -l)"
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
  # ground squares downloaded by this build (new, or refreshed after a month), and everyone's dates
  for f in "$RAW"/ground-*.zip; do
    [ -f "$f" ] || continue
    if [ "$f" -nt "$RAW/.fetched" ] || ! echo "$have" | grep -qx "${f##*/}"; then
      gh release upload "$TAG" "$f" --clobber && echo "Uploaded ${f##*/}"
    fi
  done
  for f in "$RAW"/ground-*.zip; do [ -f "$f" ] && echo "${f##*/} $(stat -c %Y "$f")"; done > "$RAW/dates.txt"
  gh release upload "$TAG" "$RAW/dates.txt" --clobber
  ;;
*) echo "usage: sh tools/raw.sh fetch|save"; exit 2 ;;
esac
