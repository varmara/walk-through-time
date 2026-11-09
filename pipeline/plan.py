"""Which step a data build can start from, given the files a push changed (one path per line on stdin).

Steps run in order and each reads only earlier steps' work/ files, so a build can start at the earliest step
whose code changed and reuse the rest from the last build (restored from the Actions cache). Prints that step,
or "all" when the whole pipeline must run: the area or the workflow changed, or shared code (common.py, run.py).

  git diff --name-only BEFORE AFTER | python -m pipeline.plan
"""
import sys

from .run import STEPS

START = {"stories/": "s04_curated", "pipeline/layers.py": "s06_layers", "pipeline/plan.py": None}
EVERYTHING = ("cities/", "pipeline/common.py", "pipeline/run.py", "pipeline/__init__.py", ".github/workflows/build-data.yml")


def start_for(paths):
    first = None
    for p in paths:
        p = p.strip()
        if not p or not p.startswith(("pipeline/", "stories/", "cities/", ".github/")):
            continue            # the page, the README, the data itself: nothing to rebuild for
        if p.startswith(EVERYTHING):
            return "all"
        step = next((v for k, v in START.items() if p.startswith(k)), "")
        if step == "" and p.startswith("pipeline/") and p.endswith(".py"):
            name = p[len("pipeline/"):-3]
            step = name if name in STEPS else "all"       # another shared module: run everything
        if step == "all":
            return "all"
        if step and (first is None or STEPS.index(step) < STEPS.index(first)):
            first = step
    return first or "all"


if __name__ == "__main__":
    print(start_for(sys.stdin.read().splitlines()))
