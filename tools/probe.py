from pipeline.common import http
for w in ["way/288216300", "way/215101442", "way/37080661", "way/210965263"]:
    r = http(f"https://api.openstreetmap.org/api/0.6/{w}.json")
    print("PROBE", w, r["elements"][0].get("tags"))
q = """[out:json];way(around:25,52.9568,-1.1585)["building"];out tags center;"""
