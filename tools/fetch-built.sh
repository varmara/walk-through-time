#!/bin/sh
# Fetch the last build's output for working on a computer, without running the whole pipeline:
#   data/   the published data (from the "site" branch), so the page can be opened locally
#   work/   the pipeline's intermediate files (from the "work" branch), so any step from s01 on can be run again,
#           e.g. python -m pipeline.run nottingham --from s07
# Then serve the folder (python3 -m http.server) and open http://localhost:8000/nottingham/.
set -e
cd "$(dirname "$0")/.."
what=${1:-both}
if [ "$what" != work ]; then
  git fetch -q --depth 1 origin site
  rm -rf data && git archive FETCH_HEAD data | tar -x
  echo "data/ from the site branch ($(git log -1 --format=%s FETCH_HEAD))"
  python3 -m pipeline.pages          # and the pages, from app/templates/
fi
if [ "$what" != data ]; then
  git fetch -q --depth 1 origin work
  tmp=$(mktemp -d)
  git archive FETCH_HEAD | tar -x -C "$tmp"
  mkdir -p work && cat "$tmp"/work.tar.gz.* | tar -xz -C work
  rm -rf "$tmp"
  if git fetch -q --depth 1 origin downloads 2>/dev/null; then      # the OpenStreetMap download, kept apart
    for f in $(git ls-tree --name-only FETCH_HEAD | grep '\.osm\.json\.gz$'); do
      c=${f%.osm.json.gz}; mkdir -p "work/$c"
      git show "FETCH_HEAD:$f" | gunzip > "work/$c/osm.json"
      git show "FETCH_HEAD:$c.osm.stamp" > "work/$c/osm.stamp"
    done
  fi
  echo "work/ from the work branch"
fi
