import json
from pipeline.common import http
r = http("https://api.openstreetmap.org/api/0.6/way/210422928.json")
print("PROBE tags", r["elements"][0].get("tags"))
q = http("https://www.wikidata.org/wiki/Special:EntityData/Q26546211.json")
e = q["entities"]["Q26546211"]
print("PROBE wd", e["labels"].get("en", {}).get("value"), [c["mainsnak"].get("datavalue", {}).get("value") for c in e["claims"].get("P1216", [])])
