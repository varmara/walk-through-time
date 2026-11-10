from pipeline.common import http
for w in ["way/591854932", "way/165120327"]:
    r = http(f"https://api.openstreetmap.org/api/0.6/{w}.json")
    print("PROBE", w, r["elements"][0].get("tags"))
