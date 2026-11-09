import collections, json, re, sys
from pipeline.common import http
from pipeline.s02_listing_dates import rows, templates, params
W = "https://en.wikipedia.org/w/api.php"
for t in sys.argv[1:]:
    r = http(W, params={"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "format": "json", "formatversion": "2", "titles": t})
    txt = r["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
    print("=====", t, len(txt))
    print(collections.Counter(params(txt[a:b])["_name"][:40] for a, b in templates(txt)).most_common(12))
    i = txt.find("{|")
    print(txt[i:i + 2500])
    rs = rows(txt); print(len(rs), "rows parsed"); print(rs[:3])
