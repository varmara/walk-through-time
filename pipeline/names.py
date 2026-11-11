"""Naming rules: what a building was, not who is in it now. Used by s06_names (and tested in tests/test_names.py)."""
import re


OCCUPANT_KEYS = ("shop", "office", "brand", "brand:wikidata", "operator", "craft", "healthcare")
OCCUPANT_AMENITY = {"bank", "restaurant", "cafe", "fast_food", "bar", "pub", "nightclub", "pharmacy", "doctors",
                    "dentist", "post_office", "bureau_de_change", "money_transfer", "betting", "gambling", "casino"}
_HE_TAIL = re.compile(r"\s*(?:,|\bAND\b|\bWITH\b|\bINCLUDING\b)\s*(?:THE\s+)?(?:ATTACHED|ADJOINING|ADJACENT|FRONT|BOUNDARY|"
                      r"GATES?|GATEPIERS?|RAILINGS?|WALLS?|PIERS|FORECOURT|LAMP|STEPS|AREA)\b.*$", re.I)


def occupied(tags):
    """True when the outline's name is probably a business inside it (a shop, an office, a brand) rather than
    the building's own name: OpenStreetMap often puts the occupier's tags on the building."""
    return any(tags.get(k) for k in OCCUPANT_KEYS) or tags.get("amenity") in OCCUPANT_AMENITY


def tidy_listing(name):
    """Historic England's name for a building, readable: 'NEWCASTLE HOUSE AND ATTACHED BOUNDARY WALL' ->
    'Newcastle House'. None when it is only an address ('3 AND 5, HOUNDS GATE')."""
    if not name:
        return None
    n = name.strip()
    was = re.search(r"\bformerly (?:the )?(.+)$", n, re.I)     # "11 Pelham Street…, formerly the Nottingham and…"
    if was:
        n = was[1]
    n = _HE_TAIL.sub("", re.sub(r"\s*\([^)]*\)", "", n)).strip(" ,")
    n = re.sub(r",\s*Nottingham$", "", n, flags=re.I)
    if not n or re.match(r"^\d", n) or re.match(r"^(?:NOS?\.?|NUMBERS?)\s*\d", n, re.I):
        return None
    if re.match(r"^(?:railings|walls?|gates?|gate piers|steps|boundary|lamp|bollards?|kerb)\b", n, re.I):
        return None                       # a listing of railings or a wall names no building
    if n.isupper():
        n = n.title()
    n = re.sub(r"\b(And|Of|The|At|To|On|In|For)\b", lambda m: m[1].lower(), n).replace("'S ", "'s ")
    return n[0].upper() + n[1:]


BUILDINGISH = re.compile(r"\b(house|hall|chapel|church|school|mill|bank|inn|arms|hotel|theatre|cinema|picture|station|works|"
                         r"factory|warehouse|baths|library|exchange|buildings?|chambers|court|lodge|cottages?|almshouses?|"
                         r"institute|club|tavern|brewery|market|offices|mission|tabernacle|hospital|asylum|gaol|barracks|home|"
                         r"school|college|museum|gallery|cross|tower|lodge|works|depot|shop|stores|arcade|castle|centre|site)\b", re.I)
_PLAIN = {"the", "and", "of", "at", "to", "on", "in", "for", "a", "st", "saint", "former", "old", "new", "nottingham"}


def _words(s):
    s = re.sub(r"['’]", "", (s or "").lower())            # Severn's, Severns'
    return {w.rstrip("s") for w in re.findall(r"[a-z]{3,}", s) if w not in _PLAIN}


def other_names(tags, name, today, label=None, listing_name=None):
    """The building's other names, oldest first where known: its old name, Historic England's, Wikidata's, another
    name in OpenStreetMap ("Midland Railway Station" for Nottingham station; "Pearson's Department Store")."""
    seen = {(name or "").lower(), (today or "").lower()}
    out = []
    for n in (tags.get("old_name"), tags.get("historic:name"), tidy_listing(listing_name), label, tags.get("building:name"),
              tags.get("alt_name"), tags.get("name") if tags.get("name") != today else None):
        for part in (n or "").split(";"):
            part = part.strip()
            key = re.sub(r"\s*\([^)]*\)", "", part).lower()      # "D34 (Fire Station) At …" is "D34 at …"
            if part and key not in seen and not any(key in s or s in key for s in seen if s):
                seen.add(key)
                out.append(part)
    return out or None


LANDMARK = re.compile(r"\b(museum|gallery|theatre|cinema|college|university|school|church|cathedral|chapel|"
                      r"mosque|synagogue|station|library|hospital|arts centre|concert hall)\b", re.I)
LANDMARK_USE = {"amenity": {"theatre", "cinema", "arts_centre", "library", "college", "university", "school",
                            "place_of_worship", "townhall", "courthouse", "hospital", "concert_hall"},
                "tourism": {"museum", "gallery"}, "building": {"train_station", "church", "cathedral", "chapel",
                                                               "university", "college", "museum"},
                "railway": {"station"}, "public_transport": {"station"}}


_TRADE = re.compile(r"\b(bar|caf[eé]|restaurant|gaming|pub|grill|lounge|hotel|former|academy|global|ltd|limited)\b", re.I)


def landmark(tags_list, now):
    """A lasting public institution (a museum, theatre, college, church, station), whose current name belongs in
    the title next to what the building was: 'Shire Hall and County Gaol · National Justice Museum'. Its name must
    say so, and not be a business's ('Riverbank Bar and Gallery') or an old name ('Former Police Station')."""
    return bool(now and LANDMARK.search(now) and not _TRADE.search(now))


def same_place(a, b):
    """Two ways of naming one thing: 'Church of St Mary' and 'St Mary's Church'; 'The Corner House' and
    'The Cornerhouse'; 'Castle Gate Congregational Church' and '… Centre'."""
    squash = lambda n: re.sub(r"[^a-z]", "", re.sub(r"\b(the|of|church|saint|st)\b", "", n.lower()))  # noqa: E731
    if squash(a) and squash(b) and (squash(a) in squash(b) or squash(b) in squash(a)):
        return True
    mine = lambda n: _words(n) - {m.lower().rstrip("s") for m in BUILDINGISH.findall(n)}  # noqa: E731
    return bool(mine(a) & mine(b))


FIXTURES = {"vending_machine", "photo_booth", "atm", "telephone", "post_box", "bench", "waste_basket",
            "bicycle_parking", "parking_entrance", "ticket_validator", "drinking_water", "recycling", "toilets",
            "charging_station", "luggage_locker", "left_luggage", "clock", "fountain", "bureau_de_change",
            "parcel_locker", "public_bookcase", "shelter", "kiosk"}


def marker(tags):
    """A thing on or in a building that names something else: a plaque or memorial ("Near this site stood the
    Malt Cross"), a sign, or a fixture (a Photo-Me booth in the station, a cash machine)."""
    return ((tags.get("historic") and tags["historic"] not in ("building", "castle", "church", "manor", "house"))
            or tags.get("memorial") or tags.get("tourism") == "information"
            or tags.get("amenity") in FIXTURES or tags.get("shop") in ("kiosk", "vending")
            or tags.get("vending"))


def he_names_more(he, osm):
    """Historic England's name says what the building was, and the OpenStreetMap name is another thing entirely
    (an occupier without shop or office tags: "Regus" in Stanford House, "Jem Leisure" in the Midland Bank)."""
    if not he or not osm or not BUILDINGISH.search(he) or re.match(r"^(railings|walls?|gates?|steps|boundary)\b", he, re.I):
        return False
    mine = lambda n: _words(n) - {m.lower().rstrip("s") for m in BUILDINGISH.findall(n)}  # noqa: E731
    # both must name something of their own ("Nottingham Castle" names only the town and the kind of building),
    # and nothing in common ("Musters Road Methodist Church" is "West Bridgford Methodist Church")
    return bool(mine(he)) and bool(mine(osm)) and not (mine(he) & mine(osm))


def house_numbers(n):
    """An address's numbers as written: '15;16' -> '15 and 16', '3;5;7' -> '3, 5 and 7', '2-4' -> '2–4'."""
    parts = [x.strip().replace("-", "–") for x in re.split(r"[;,]", n or "") if x.strip()]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1] if parts else ""


def building_name(tags, story=None, label=None, listing_name=None, place=None):
    """(name, today): the name to show and, if different, who or what uses the building today.

    Prefer what the building was: a story's name, the building's own name in OpenStreetMap (building:name,
    historic:name), Historic England's name, the listed building's Wikidata item, an old_name that names a
    building ("Kings Arms", "Albert Hall"; old_name is more often just the previous shop, which is skipped);
    the OpenStreetMap name only when it is the building's own name, otherwise it becomes 'today'."""
    osm = tags.get("name")
    own = tags.get("building:name") or tags.get("historic:name") or tags.get("name:historic")
    old = tags.get("old_name")
    if old and (";" in old or not BUILDINGISH.search(old)):
        old = None
    he = tidy_listing(listing_name)
    if label and re.match(r"^(?:railings|walls?|gates?|gate piers|steps|boundary)\b", label, re.I):
        label = None                      # a listing of railings names no building
    if label:   # Wikidata labels of listed buildings copy Historic England's: tidy them the same way
        label = re.sub(r"\b(And|Of|The|At|To|On|In|For)\b", lambda m: m[1].lower(),
                       _HE_TAIL.sub("", label).strip(" ,")) or label
        label = label[0].upper() + label[1:]
    num, street = tags.get("addr:housenumber"), tags.get("addr:street")
    address = f"{house_numbers(num)} {street}" if num and street else None
    # an unlisted shop, café or office with no name for the building itself: its address, the business 'Today'
    # (a building with only an address stays unnamed: its card is titled by the address)
    trade = tags.get("building") in ("retail", "commercial", "office", "industrial", "warehouse", "supermarket", "kiosk")
    if story:
        name = story
    elif own:
        name = own
    elif osm and not occupied(tags) and not he_names_more(he, osm) and not (trade and address and not he and not label
                                                                           and not BUILDINGISH.search(osm)):
        name = osm
    else:
        # a pub's name, or a name that says what the building is ("Kings Arms", "Albert Hall"), beats the address
        keep = osm and (tags.get("amenity") == "pub" or BUILDINGISH.search(osm))
        name = he or label or old or (osm if keep else address if osm else None) or osm or place
    m = re.match(r"^(?:Numbers?|Nos?\.?)\s+(\d.*)$", name or "")
    if m:                                 # "Numbers 119 and 121" -> "119 and 121 Derby Road"
        street = tags.get("addr:street")
        name = m[1] + (f" {street}" if street and street.lower() not in m[1].lower() else "")
    today = (osm if osm and name and osm.strip().lower() not in name.strip().lower()
             and (occupied(tags) or own or he_names_more(he, osm) or name == address) else None)   # not "Newton" for the Newton Building
    return name, today
