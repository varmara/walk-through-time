from pipeline.s06_summaries import extracts
cands = ["Lord Byron", "John Wesley", "William Carey (missionary)", "John Player (businessman)", "John Player",
         "James Sadler (balloonist)", "John Hutchinson (Roundhead)", "John Hutchinson (soldier)", "Frank Matcham",
         "Benjamin Mayo", "John Levers", "John Leavers", "Charles I of England", "Robin Hood", "Frank Robinson",
         "William Thompson (boxer)", "Robert Evans (architect, 1832–1911)"]
got = extracts(cands)
for c in cands:
    print("PROBE", c, "::", (got.get(c) or "-")[:160].replace("\n", " "))
