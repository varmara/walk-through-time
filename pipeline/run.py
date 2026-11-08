"""Run the pipeline for one or more cities, or a single step.

  python -m pipeline.run nottingham              all steps
  python -m pipeline.run nottingham --from s04   from a step onwards (reuses work/ files)
  python -m pipeline.run nottingham --only s05   one step
"""
import argparse
import importlib

STEPS = ["s00_fetch_osm", "s00_fetch_heritage", "s01_buildings", "s02_listing", "s03_wikidata",
         "s04_dates", "s05_curated", "s06_layers", "s07_package"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cities", nargs="+")
    ap.add_argument("--from", dest="start")
    ap.add_argument("--only")
    a = ap.parse_args()
    steps = STEPS
    if a.only:
        steps = [s for s in STEPS if s.startswith(a.only)]
    elif a.start:
        steps = STEPS[next(i for i, s in enumerate(STEPS) if s.startswith(a.start)):]
    for c in a.cities:
        for s in steps:
            importlib.import_module(f"pipeline.{s}").main(c)


if __name__ == "__main__":
    main()
