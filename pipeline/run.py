"""Run the pipeline for one or more cities, or a single step.

  python -m pipeline.run nottingham              all steps
  python -m pipeline.run nottingham --from s04   from a step onwards (reuses work/ files)
  python -m pipeline.run nottingham --only s05   one step
  python -m pipeline.run nottingham --reuse-downloads
                                                 reuse work/<city>/osm.json if the area and query are unchanged
"""
import argparse
import importlib

STEPS = ["s00_fetch_osm", "s00_fetch_bridges", "s00_fetch_heritage", "s00_fetch_nature", "s00_fetch_plaques", "s00_fetch_voa", "s01_buildings", "s02_listing", "s02_listing_dates", "s03_wikidata",
         "s04_curated", "s04_residents", "s05_dates", "s06_layers", "s06_names", "s06_summaries", "s06_photos", "s07_package", "s08_graph", "s09_share", "s10_tiles", "s11_changes"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cities", nargs="+")
    ap.add_argument("--from", dest="start")
    ap.add_argument("--only")
    ap.add_argument("--reuse-downloads", action="store_true")
    a = ap.parse_args()
    steps = STEPS
    if a.only:
        steps = [s for s in STEPS if s.startswith(a.only)]
    elif a.start:
        steps = STEPS[next(i for i, s in enumerate(STEPS) if s.startswith(a.start)):]
    for c in a.cities:
        for s in steps:
            mod = importlib.import_module(f"pipeline.{s}")
            if s == "s00_fetch_osm" and a.reuse_downloads and mod.reusable(c):
                print(f"s00 OpenStreetMap: reusing the saved download for {c}", flush=True)
                continue
            mod.main(c)


if __name__ == "__main__":
    main()
