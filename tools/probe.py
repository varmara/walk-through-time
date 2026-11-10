import re
from pipeline.common import http_text
for u in ["https://picturenottingham.co.uk/robots.txt", "https://picturenottingham.co.uk/image-library.html"]:
    try:
        t = http_text(u)
    except Exception as e:
        print("PROBE", u, e); continue
    print("PROBE", u, len(t))
    if u.endswith(".txt"):
        print("PROBE", t[:800].replace("\n", " | "))
    for m in re.finditer(r"<form[^>]*>|<input[^>]*>|<select[^>]*name=[^>]*>|href=\"[^\"]*(?:search|keyword|image-library\?)[^\"]*\"", t):
        print("PROBE", m[0][:250])
