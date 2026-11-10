import re
from pipeline.s04_curated import article
for ref, words in [("en:Wilford", ["forman", "smith", "ferry inn", "iremonger"]), ("en:City of Caves", ["tannery", "1500"])]:
    t = article(ref)["text"]
    for w in words:
        for m in list(re.finditer(re.escape(w), t))[:3]:
            print(ref, w, "::", t[max(0, m.start() - 150): m.end() + 150].replace("\n", " "))
