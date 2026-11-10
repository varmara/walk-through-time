"""Story layers for Nottingham: the centre and the suburbs either side of the Trent.

Every entry rests on a Wikipedia article. `facts` are strings the article must contain; step s05 checks
them and drops the entry if any is missing. Keep stories to one or two plain sentences, and claim
nothing the article does not say. Name legends as legends. See CONTRIBUTING.md.
"""


def E(name, source, story, facts, at=None, year=None, names=True):
    """names=False: the story's title is not the building's name ("The castle burned, 1831").
    year: when the building standing today was built or opened ("1855", "c. 1420", "1841..1844").
    Its digits must appear in the article; it becomes a date source next to OpenStreetMap and Wikidata."""
    return {"name": name, "source": source, "story": story, "facts": facts,
            **({"at": at} if at else {}), **({"year": year} if year else {}), **({"names": False} if not names else {})}


def P(name, person, place, story, facts, at=None, group=None, quote=None):
    """A person and a place. `person` and `place` are Wikipedia articles ("en:Title"); the facts must appear in
    the two articles together, and the place's article decides the building. The type of person comes from
    Wikidata; set `group` only when it has none (architects, writers, science, industry, sport, arts, public)."""
    return {"name": name, "source": person, "place": place, "story": story, "facts": facts,
            **({"at": at} if at else {}), **({"group": group} if group else {}), **({"quote": quote} if quote else {})}


def F(name, source, fact, facts, at=None):
    """A 'Did you know' fact about one building, shown on its card. Same checks and placement as a story: the
    facts must appear in the article, and the article (or `at`) decides the building."""
    return {"name": name, "source": source, "story": fact, "facts": facts, **({"at": at} if at else {})}


# People whose plaque gives a name that Wikipedia does not use, or more than one person could have: their
# article, so their card can say who they were. (Each checked by hand against the plaque's words and years.)
WIKIPEDIA = {
    "George Gordon Byron": "Lord Byron",                       # "Lord Byron 1788-1824 the poet, lived in this house"
    "John Wesley": "John Wesley",                              # opened the Hockley Methodist Chapel, 1783
    "William Carey": "William Carey (missionary)",             # his missionary sermon, 30 May 1792
    "John Player": "John Player & Sons",                       # "Site of John Player's first shop 1861"
    "James Sadler": "James Sadler (balloonist)",               # Nottingham's first balloon flight, 1813
    "John Hutchinson": "John Hutchinson (Roundhead)",          # Governor of the castle 1643-1647
    "Frank Matcham": "Frank Matcham",                          # the Theatre Royal, 1897
    "John Leavers": "John Levers",                             # inventor of the Leavers lace machine
    "Charles I": "Charles I of England",                       # raised his standard here, 25 August 1642
    "Robin Hood": "Robin Hood",                                # the statue by the castle
    "William Thompson": "William Thompson (boxer)",            # "Bendigo"
}

# Corrections to plaques (Nottingham City Council's list and OpenStreetMap), by the start of the inscription or
# the subject's name: a label for a plaque to an event, or the group a person belongs in.
PLAQUES = {
    "Commemorating 'the most Dreadful": {"label": "The canal warehouse explosion"},
    "Midland Counties Railway": {"label": "Beeston Station", "type": "thing"},
    "George Green": {"group": "science"},        # a miller by trade, remembered as a mathematician
    "The World's Oldest Professional League Club": {"label": "Notts County Football Club", "type": "group"},
    "Thomas Adams": {"group": "industry"},       # "Lace Manufacturer, Christian Philanthropist"
    "William Thompson": {"group": "sport"},      # Bendigo: a prize-fighter first, an evangelist later
    "Jesse Boot": {"group": "industry"},
    "Samuel Bourne": {"group": "arts"},          # photographer
    "John Player": {"group": "industry"},
    "James Sadler": {"group": "science"},        # balloonist and chemist
    "Thomas Smith": {"group": "industry"},       # banker: Smith's Bank
    "Eric Irons": {"group": "public"},           # magistrate
    "Constance Shacklock": {"group": "arts"},    # contralto
    "Benjamin Mayo": {"group": "other"},         # 'The Old General', a local character, not a soldier
}

# Collections of old pictures that are not openly licensed, so the map links to them instead of showing their
# pictures: a building or pin gets the link when it is in the area, the layer, or has the name or person given.
PN = "https://picturenottingham.co.uk/image-themes/"
COLLECTIONS = [
    {"title": "Nottingham Castle", "url": PN + "nottingham-castle.html", "areas": ["Castle"],
     "names": ["nottingham castle", "castle gatehouse", "mortimer's hole"], "who": ["John Hutchinson"]},
    {"title": "The Lace Market", "url": PN + "lace-market.html", "areas": ["Lace Market"]},
    {"title": "Nottingham's lace industry", "url": PN + "nottinghams-lace-industry.html", "layers": ["lace"]},
    {"title": "Old Market Square", "url": PN + "nottinghams-old-market-square.html", "areas": ["Old Market Square"]},
    {"title": "Goose Fair", "url": PN + "goose-fair.html", "names": ["old market square"]},
    {"title": "Trent Bridge", "url": PN + "trent-bridge.html", "names": ["trent bridge", "city ground", "county hall"]},
    {"title": "Wilford", "url": PN + "wilford.html", "areas": ["Wilford Village", "Wilford House"], "layers": ["wilford"]},
    {"title": "Robin Hood", "url": PN + "robin-hood.html", "who": ["Robin Hood"]},
    {"title": "D. H. Lawrence", "url": PN + "dh-lawrence.html", "who": ["D. H. Lawrence"]},
    {"title": "Lord Byron", "url": PN + "lord-byron-and-newstead-abbey.html", "who": ["George Gordon Byron"]},
    {"title": "Sport", "url": PN + "sport.html", "names": ["city ground", "meadow lane", "trent bridge cricket ground"]},
]

# Names chosen by hand, by OpenStreetMap outline, where neither OpenStreetMap nor Historic England gives a good one.
# (The other names still show on the card.)
NAMES = {
    "way/210965263": "52–57 Long Row",             # three merchants' houses, later Pearson's Department Store
    "way/37080661": "Boots D6 building",           # Owen Williams's 'Wets' factory, 1930-1932; Medicity today
    "way/215101442": "Boots D34 fire station",
    "way/363152364": "Nottingham station porte-cochère",   # the covered carriage entrance, now part of the concourse
    "way/168960005": "Nottingham General Hospital",        # the hospital's buildings, now flats called Standard Court
}

# Titles chosen by hand, "what it was · what it is", where the rule gets them the wrong way round.
TITLES = {
    "way/168960005": "Nottingham General Hospital · Standard Court",
}

# Corrections to OpenStreetMap's tags, by outline (None drops the tag). Better still, fix them in OpenStreetMap.
TAG_FIXES = {
    # the porte-cochère opened with the station's forebuildings in 1904 (Albert Edward Lambert, architect);
    # 1839 is when the first station, on Carrington Street, opened
    "way/363152364": {"start_date": "1904", "start_date:source": "Wikipedia (Nottingham railway station)",
                      "architect": "Albert Edward Lambert", "historic": None},
}

CURATED = [
    dict(
        id="inns", title="Old inns",
        intro="Three pubs in the centre each claim to be the oldest in Nottingham. A television investigation "
              "concluded that the Salutation is the oldest building, but the Bell has been a pub the longest.",
        entries=[
            E("Ye Olde Trip to Jerusalem", "en:Ye Olde Trip to Jerusalem",
              "Claims to date from 1189, a date that rests on tradition rather than records. "
              "It is built against the castle rock, with rooms cut into the sandstone.",
              ("1189", "sandstone")),
            E("The Bell Inn", "en:The Bell Inn, Nottingham",
              "Claims to be the oldest pub in the city. Tree-ring dating of its timbers suggests it was built "
              "around 1420, and its cellars are cut into the sandstone.",
              ("oldest", "dendrochronological", "1420", "sandstone"), year="c. 1420"),
            E("Ye Olde Salutation Inn", "en:Ye Olde Salutation Inn",
              "Another claimant to the title of the city's oldest pub. The core of the building dates from "
              "around 1360, and unusually large caves lie beneath it.",
              ("oldest", "1360", "caves"), year="c. 1360"),
        ]),
    dict(
        id="churches", title="Churches",
        intro="Medieval Nottingham had three parishes: St Mary's, St Peter's and St Nicholas'. "
              "Each still has its church, joined in the 1840s by a Catholic cathedral, and by chapels of the "
              "Nonconformists, such as the Unitarians on High Pavement.",
        entries=[
            E("St Mary's Church", "en:St Mary's Church, Nottingham",
              "One of the three medieval parish churches of Nottingham, on a site mentioned in the Domesday Book.",
              ("Domesday",)),
            E("St Peter's Church", "en:St Peter's Church, Nottingham",
              "One of the three medieval parish churches of Nottingham. Parts of the building date from "
              "about 1180.",
              ("mediaeval", "1180"), year="c. 1180"),
            E("St Nicholas' Church", "en:St Nicholas' Church, Nottingham",
              "The medieval church was pulled down during the Civil War; the brick church standing today "
              "was finished in 1678.",
              ("Civil War", "1678"), year="1678"),
            E("Cathedral of St Barnabas", "en:Nottingham Cathedral",
              "The Catholic cathedral, designed by Augustus Pugin and built between 1841 and 1844.",
              ("Pugin", "1841", "1844"), year="1841..1844"),
            E("High Pavement Chapel", "en:High Pavement Chapel",
              "Built in 1876 to designs by Stuart Colman for a congregation that goes back to 1690 and became "
              "Unitarian in 1802. Worship ended in 1982; the chapel then housed a lace museum and is now a "
              "Pitcher & Piano.",
              ("1876", "Stuart Colman", "1690", "1802", "1982", "Pitcher"), at="name:Former Unitarian Chapel",
              year="1876"),
        ]),
    dict(
        id="lace", title="Lace and trade",
        intro="In the 19th century Nottingham was a world centre of lace. Merchants built warehouses and "
              "showrooms in the Lace Market, east of the Old Market Square.",
        entries=[
            E("Adams Building", "en:Adams Building, Nottingham",
              "A lace showroom and warehouse built for Thomas Adams to a design by Thomas Chambers Hine, "
              "opened in 1855.",
              ("Thomas Adams", "Thomas Chambers Hine", "1855"), year="1855"),
            E("Severn's Building", "en:Severn's Building",
              "A medieval timber-framed building, moved to its present site on Castle Road.",
              ("Castle Road",)),
            E("Victoria Centre", "en:Victoria Centre",
              "A shopping centre opened in 1972 on the site of Nottingham Victoria railway station, "
              "whose clock tower still stands beside it.",
              ("1972", "clock tower"), year="1972"),
            E("Adams Building", "en:Adams Building, Nottingham",
              "Built from 1854 to designs by Thomas Chambers Hine for Thomas Adams, a Quaker lace manufacturer, "
              "with a chapel for the workers in the basement. Inspectors thought it a model example of its kind; "
              "since 1999 it has been part of Nottingham College.",
              ("Thomas Chambers Hine", "Quaker", "chapel", "model example", "1999")),
        ]),
    dict(
        id="civic", title="Civic Nottingham",
        intro="The buildings where the town and county were governed, judged and connected to the railway.",
        entries=[
            E("Council House", "en:Council House, Nottingham",
              "Designed by Thomas Cecil Howitt and opened in 1929, on the site of the old Exchange "
              "at the head of the Old Market Square.",
              ("Howitt", "1929", "Exchange"), year="1929"),
            E("Guildhall", "en:Nottingham Guildhall",
              "The Victorian Guildhall, completed in 1888, held the city's courts and police station.",
              ("1888",), year="1888"),
            E("Shire Hall", "en:Shire Hall, Nottingham",
              "The county courthouse and gaol, rebuilt to a design by James Gandon. "
              "It is now the National Justice Museum.",
              ("Gandon", "National Justice Museum")),
            E("Nottingham station", "en:Nottingham railway station",
              "The station building of red brick and terracotta opened in 1904.",
              ("1904", "terracotta"), year="1904"),
            E("Old Market Square", "en:Old Market Square, Nottingham",
              "One of the largest paved squares in the United Kingdom. The two towns were once divided by a wall "
              "across it, whose line a stainless steel channel now marks; Goose Fair was held here until 1928.",
              ("largest paved squares", "divided by a wall", "stainless steel", "1928"), at="pin:-1.1497,52.9529"),
            E("Broad Marsh", "en:Broad Marsh",
              "After large-scale slum clearance, the Broad Marsh shopping centre was officially opened on 25 March "
              "1975. It closed in 2020 and was left partially demolished; caves found beneath it, dug into the soft "
              "sandstone, became part of the City of Caves.",
              ("slum clearance", "25 March 1975", "partially demolished", "City of Caves")),
            E("The castle burned, 1831", "en:1831 reform riots",
              "When the House of Lords threw out the Second Reform Bill on 8 October 1831, rioting broke out in "
              "Nottingham and a crowd burned the castle, which belonged to the Duke of Newcastle, an opponent of "
              "reform. Three men were hanged; the Duke refused to restore the castle, and its burnt shell stood "
              "on the rock for years.",
              ("8 October 1831", "Duke of Newcastle", "hanged", "burnt shell"), at="name:Nottingham Castle",
              names=False),
        ]),
    dict(
        id="culture", title="Theatres and culture",
        intro="Theatres, concert halls, a library and galleries, from a Georgian subscription library "
              "to a 21st-century art centre.",
        entries=[
            E("Nottingham Castle", "en:Nottingham Castle",
              "The medieval castle was demolished after the Civil War and a ducal mansion built on the rock. "
              "Rioters burnt the mansion in 1831; it reopened as a museum in 1878.",
              ("1831", "1878")),
            E("Bromley House", "en:Bromley House Library",
              "A Georgian town house built in 1752. The Nottingham Subscription Library, founded in 1816, "
              "moved in during 1821.",
              ("1752", "1816", "1821"), year="1752"),
            E("Theatre Royal", "en:Theatre Royal, Nottingham",
              "Opened in 1865 and designed by Charles J. Phipps.",
              ("1865", "Phipps"), year="1865"),
            E("Royal Concert Hall", "en:Royal Concert Hall, Nottingham",
              "A concert hall built next to the Theatre Royal and opened in 1982.",
              ("1982",), year="1982"),
            E("Albert Hall", "en:Albert Hall, Nottingham",
              "Built as a Methodist mission hall and opened in 1909.",
              ("Methodist", "1909"), year="1909"),
            E("Nottingham Playhouse", "en:Nottingham Playhouse",
              "A modernist theatre designed by Peter Moro, opened in 1963.",
              ("Moro", "1963"), year="1963"),
            E("Nottingham Contemporary", "en:Nottingham Contemporary",
              "An art centre designed by Caruso St John and opened in 2009, its walls patterned with lace.",
              ("Caruso St John", "2009", "lace"), year="2009"),
            E("Malt Cross", "en:Malt Cross",
              "Built in 1877 to designs credited to Edwin Hill, it is one of the few surviving Victorian music "
              "halls, under a high arched glass roof on laminated wooden arches.",
              ("1877", "Edwin Hill", "music hall"), at="osm:way/291697300", year="1877"),
            E("Rock City", "en:Rock City (venue)",
              "The building opened in 1876 as the Alexandra Skating Rink. Rock City opened in December 1980, with "
              "the Undertones playing the first gig, and holds 2,000 people.",
              ("1876", "Alexandra Skating Rink", "December 1980", "Undertones"), at="name:Rock City"),
            E("Broadway", "en:Broadway Cinema",
              "The building began in 1839 as a grand Wesleyan chapel on Broad Street. Broadway opened here in 1990, "
              "and one of its screens is the only cinema screen designed by Sir Paul Smith.",
              ("1839", "Wesleyan chapel", "1990", "Paul Smith")),
        ]),
    dict(
        id="wilford", title="Wilford",
        intro="A village on the south bank of the Trent, reached for centuries by ferry and, since the 1870s, by bridge.",
        entries=[
            E("Wilford Toll Bridge", "en:Wilford Toll Bridge",
              "Opened in 1870, replacing a ferry that had crossed here for some 400 years. Pedestrians paid a "
              "halfpenny toll. It was closed to traffic in 1974.",
              ("1870", "ferry", "400 years", "1974"), year="1870"),
            E("Wilford Suspension Bridge", "en:Wilford Suspension Bridge",
              "A footbridge built by the city's water department, mainly to carry water pipes across the Trent to "
              "the reservoir on Wilford Hill. The engineer was Arthur Brown.",
              ("Arthur Brown", "Wilford Hill reservoir", "water")),
            E("St Wilfrid's Church", "en:St Wilfrid's Church, Wilford",
              "The church dates from the late 14th century and is thought to have been founded by Gervase de Wilford "
              "in around 1361. Inside are two memorials to the poet Henry Kirke White, who drew much inspiration "
              "from Wilford and Clifton.",
              ("late 14th century", "Gervase de Wilford", "1361", "Henry Kirke White", "inspiration"),
              at="name:St Wilfrid's Church"),
            E("The poet in the churchyard", "en:Wilford",
              "Henry Kirke White is said to have spent much of his time writing poems in the churchyard, sitting "
              "under his favourite tree.",
              ("Henry Kirke White", "churchyard", "favourite tree"), at="name:St Wilfrid's Church", names=False),
            E("Ferry Inn", "en:Wilford",
              "Wilford stayed a village until the later 19th century. With woods around it and riverside amenities "
              "such as the Ferry Inn, it attracted many visitors from Nottingham. The Notts County goalkeeper "
              "Albert Iremonger was its landlord until his death in 1958.",
              ("later 19th century", "wilford ferry inn", "many visitors from nottingham", "iremonger", "1958"),
              at="name:Ferry Inn"),
            E("Wilford House", "en:Wilford",
              "Thomas Forman, who founded the Nottingham Post, bought Wilford House from the Smith family after the "
              "newspaper's successful launch.",
              ("Forman", "Wilford House", "Smith family"), at="name:Wilford House"),
        ]),
    dict(
        id="bridgford", title="West Bridgford and Trent Bridge",
        intro="South of the river: Test cricket, Nottingham Forest and the county's headquarters.",
        entries=[
            E("Trent Bridge cricket ground", "en:Trent Bridge",
              "The first recorded match was played on ground behind the Trent Bridge Inn in 1838, and William Clarke "
              "opened the ground in 1841. It hosted its first Test match, England against Australia, in 1899.",
              ("1838", "Trent Bridge Inn", "William Clarke", "1841", "1899")),
            E("County Hall", "en:County Hall, Nottinghamshire",
              "Nottinghamshire County Council's headquarters, designed by Vincent Harris. Building paused during the "
              "Second World War, and it was only completed in 1954.",
              ("Vincent Harris", "Second World War", "1954")),
            E("City Ground", "en:City Ground",
              "Nottingham Forest moved here in 1898, to their seventh home. The name dates from 1897, when Nottingham "
              "was granted city status, and Notts County's Meadow Lane is only three hundred yards away, on the "
              "other side of the Trent.",
              ("1898", "seventh home", "city status", "three hundred yards")),
            E("The Trent Bridge Inn", "en:Trent Bridge Inn",
              "The cricketer William Clarke married Mary Chapman, the inn's landlady, and the Trent Bridge cricket "
              "ground began in a field behind the pub.",
              ("William Clarke", "Mary Chapman", "landlady", "field behind"), at="name:The Trent Bridge Inn"),
            E("St Giles' Church", "en:St Giles Church, West Bridgford",
              "A medieval church of which little remains. Thomas Chambers Hine restored it in 1872, and in 1896 a "
              "new nave and chancel were begun, their foundation stone laid by Lady Byron of Thrumpton Hall.",
              ("little remains", "1872", "1896", "Lady Byron"), at="name:St Giles'"),
        ]),
    dict(
        id="meadows", title="The Meadows and the river",
        intro="The low ground between the city and the Trent, with two football grounds facing each other across the river.",
        entries=[
            E("Trent Bridge", "en:Trent Bridge (bridge)",
              "The iron bridge was designed by Marriott Ogle Tarbotton and built between 1868 and 1871. A medieval "
              "bridge of more than 20 stone arches, begun in 1156, crossed the river nearby.",
              ("Tarbotton", "1156", "stone arches"), year="1868..1871"),
            E("Meadow Lane", "en:Meadow Lane",
              "Notts County moved here on 3 September 1910. Divided by the Trent, Meadow Lane and the City Ground are "
              "the closest pair of football grounds in England.",
              ("3 September 1910", "closest")),
            E("City War Memorial", "en:City War Memorial, Nottingham",
              "Designed by the City Engineer Thomas Wallis Gordon, on land beside the Trent given by Sir Jesse Boot, "
              "and unveiled on 11 November 1927. It remembers the men of Nottingham who died in both World Wars.",
              ("Thomas Wallis Gordon", "Jesse Boot", "11 November 1927"), at="name:Memorial Arch", year="1927"),
            E("Victoria Embankment", "en:The Meadows, Nottingham",
              "A mile and a quarter of flood defences along the Trent, built between 1898 and 1901 under the borough "
              "engineer Arthur Brown. Part of it was later laid out as Memorial Gardens to the dead of the First "
              "World War.",
              ("1898", "1901", "flood defence", "Arthur Brown", "Memorial Gardens"), at="pin:-1.1468,52.9338"),
            E("The Meadows rebuilt", "en:The Meadows, Nottingham",
              "Much of the Meadows' pre-1919 terraced housing was demolished to make way for a new development of "
              "modern council housing, and the viaduct carrying the Great Central railway came down in 1975.",
              ("pre-1919", "modern council housing", "Great Central", "1975"), at="pin:-1.1530,52.9390"),
        ]),
    dict(
        id="clifton", title="Clifton",
        intro="An old village above the Trent, and next to it one of the largest housing estates ever built by a council.",
        entries=[
            E("Clifton Hall", "en:Clifton, Nottingham",
              "For 700 years the Clifton family owned the manor of Clifton, and Clifton Hall was their manor house.",
              ("700 years", "Clifton Hall"), at="name:Clifton Hall"),
            E("Clifton estate", "en:Clifton, Nottingham",
              "Planned from 1950, the Clifton council estate was at one time the largest council estate in Europe. "
              "Since the 1980s most of its houses have passed into private ownership.",
              ("1950", "largest council estate in europe", "private ownership"), at="pin:-1.1745,52.9045"),
            E("St Mary's Church", "en:St Mary's Church, Clifton",
              "A medieval church, listed Grade I. Lewis Nockalls Cottingham restored it in 1846, and much of the "
              "decoration is by George Frederick Bodley.",
              ("medieval", "Cottingham", "1846", "Bodley")),
            E("Clifton Grove", "en:Henry Kirke White",
              "The Nottingham poet Henry Kirke White, a butcher's son, published Clifton Grove, a Sketch in Verse, "
              "in 1803, aged 17. He died in 1806, aged 21.",
              ("Clifton Grove", "1803", "butcher", "1806"), at="pin:-1.1876,52.9140"),
        ]),
    dict(
        id="sneinton", title="Sneinton",
        intro="The hill east of the city: a windmill, cave dwellings, a church by Thomas Rickman and the old wholesale market.",
        entries=[
            E("Green's Windmill", "en:Green's Mill, Sneinton",
              "A tower mill built shortly after 1807 by the baker George Green. It burned in 1947, was restored and "
              "reopened in 1986, and is now part of a science centre.",
              ("1807", "George Green", "1947", "1986"), year="c. 1807"),
            E("St Stephen's Church", "en:St Stephen's Church, Sneinton",
              "The present church was designed by Thomas Rickman and dates from 1837. It was extended between 1909 "
              "and 1912 to designs by George Frederick Bodley.",
              ("Thomas Rickman", "1837", "Bodley"), year="1837"),
            E("Sneinton Market", "en:Sneinton",
              "In the 1930s the city's wholesale fruit and vegetable market moved here from the Old Market Square.",
              ("1930s", "wholesale fruit and vegetable market"), at="pin:-1.1399,52.9531"),
            E("William Booth's birthplace", "en:William Booth",
              "William Booth, who founded the Salvation Army, was born in Sneinton on 10 April 1829. At 13 he was "
              "apprenticed to a pawnbroker. His birthplace is now a museum.",
              ("10 April 1829", "Sneinton", "pawnbroker", "now a museum"), at="osm:way/123120708"),
        ]),
    dict(
        id="caves", title="Caves",
        intro="Nottingham stands on soft sandstone that can be dug with hand tools, and about a thousand man-made "
              "caves are known beneath it: cellars, workshops, dwellings and shelters.",
        entries=[
            E("City of Caves", "en:City of Caves",
              "Caves under the old town, used over the years as a tannery, pub cellars and an air raid shelter. "
              "Two caves opening onto the cliff face held the only known underground tannery in Britain, set up "
              "in 1500.",
              ("tannery", "air raid shelter", "only known underground tannery", "1500")),
            E("Mortimer's Hole", "en:Nottingham Castle",
              "A long passage to the bottom of the castle rock is known as Mortimer's Hole. In October 1330 Edward "
              "III's men came in by a secret tunnel, and Roger Mortimer was led out bound and gagged.",
              ("Mortimer's Hole", "1330", "secret tunnel", "bound and gagged"), at="pin:-1.1541,52.9496"),
            E("Sneinton Hermitage", "en:Sneinton",
              "Cave dwellings dug into the sandstone ridge extended out into Sneinton, where they were known as the "
              "Hermitage. What little remains can still be seen along Sneinton Hermitage.",
              ("Hermitage", "cave dwellings", "what little remains"), at="pin:-1.1310,52.9489"),
        ]),
    dict(
        id="facts", kind="facts", title="Did you know",
        intro="Short facts shown on building cards, each checked against its article.",
        entries=[
            F("Council House", "en:Nottingham Council House",
              "The sculptor Joseph Else named the two stone lions on its steps Agamemnon and Menelaus.",
              ("Joseph Else", "Agamemnon", "Menelaus")),
            F("Council House", "en:Nottingham Council House",
              "Little John, the hour bell in the dome, weighs over 10 tonnes, and its strike can be heard 7 miles away.",
              ("Little John", "10 tonnes", "7 miles")),
            F("Bromley House", "en:Bromley House Library",
              "The longcase clock in the library is still set to Nottingham time, 4 minutes and 33 seconds behind "
              "Greenwich, by a meridian line laid in 1836.",
              ("4 minutes and 33 seconds", "meridian line", "1836")),
            F("Bromley House", "en:Bromley House Library",
              "In 1841 Alfred Barber opened the first photographic studio in the Midlands in its attics.",
              ("Alfred Barber", "first photographic studio in the Midlands", "1841")),
            F("Theatre Royal", "en:Theatre Royal, Nottingham",
              "The world premiere of Agatha Christie's The Mousetrap took place here, in October 1952.",
              ("world premiere", "Mousetrap", "1952")),
            F("Nottingham Castle", "en:Nottingham Castle",
              "Rioters burnt the Duke of Newcastle's mansion here in 1831, over his opposition to the Reform Bill. "
              "It reopened in 1878 as the first municipal art gallery in the UK outside London.",
              ("1831", "Reform Bill", "1878", "first municipal art gallery")),
            F("National Justice Museum", "en:National Justice Museum",
              "The last public execution here was in 1864, when Richard Thomas Parker was hanged on a scaffold above "
              "the front steps.",
              ("1864", "Richard Thomas Parker", "steps")),
            F("National Justice Museum", "en:National Justice Museum",
              "Its courtrooms date back to the 14th century, and Nottingham's courts sat here until 1991.",
              ("14th century", "1991")),
            F("Malt Cross", "en:Malt Cross",
              "It takes its name from a monument that once stood in the market square; before it, the site was an "
              "inn called the Roebuck.",
              ("monument", "Roebuck"), at="osm:way/291697300"),     # the article's point is on Long Row
        ]),
    dict(
        id="people", title="People", kind="people",
        intro="People connected with buildings on the map: who designed them, who worked in them and who played "
              "in them. Each link is checked against the Wikipedia articles on the person and the place.",
        entries=[
            P("Albert Iremonger", "en:Albert Iremonger", "en:Wilford",
              "Born in Wilford, the 6 ft 5 in goalkeeper played 564 matches for Notts County. In the 1940s he ran "
              "the Ferry Inn.",
              ("Wilford", "564", "Ferry Inn"), at="name:Ferry Inn", group="sport"),
            P("Henry Kirke White", "en:Henry Kirke White", "en:St Wilfrid's Church, Wilford",
              "The poet lived in Wilford in 1804–1805; the church holds two memorials to him.",
              ("Henry Kirke White", "Wilford", "1804"), at="name:St Wilfrid's Church"),
            P("Bendigo", "en:William Thompson (boxer)", "en:William Thompson (boxer)",
              "William \"Bendigo\" Thompson, born in Nottingham on 11 October 1811, won the heavyweight championship "
              "of England in 1839. He died in 1880 and was buried in St Mary's burial ground, under a tomb with a "
              "crouching lion. The city of Bendigo in Australia is indirectly named after him.",
              ("11 October 1811", "heavyweight championship of England", "St Mary's burial ground", "crouching lion"),
              at="nhle:1271444", group="sport"),
            P("Thomas Chambers Hine", "en:Thomas Chambers Hine", "en:Adams Building, Nottingham",
              "The Nottingham architect Thomas Chambers Hine designed this lace showroom and warehouse.",
              ("Thomas Chambers Hine", "Adams")),
            P("Thomas Adams", "en:Thomas Adams (manufacturer and philanthropist)", "en:Adams Building, Nottingham",
              "The lace manufacturer Thomas Adams built this showroom and warehouse; it is named after him.",
              ("Thomas Adams", "lace")),
            P("Augustus Pugin", "en:Augustus Pugin", "en:Nottingham Cathedral",
              "Augustus Pugin, who also designed the interior of the Houses of Parliament, designed the cathedral.",
              ("Pugin", "Houses of Parliament")),
            P("Thomas Cecil Howitt", "en:Thomas Cecil Howitt", "en:Council House, Nottingham",
              "The architect Thomas Cecil Howitt designed the Council House.",
              ("Howitt", "Council House")),
            P("C. J. Phipps", "en:C. J. Phipps", "en:Theatre Royal, Nottingham",
              "The theatre architect Charles J. Phipps designed the Theatre Royal.",
              ("Phipps",)),
            P("Peter Moro", "en:Peter Moro", "en:Nottingham Playhouse",
              "The architect Peter Moro designed the Playhouse.",
              ("Moro", "Playhouse")),
            P("James Gandon", "en:James Gandon", "en:Shire Hall, Nottingham",
              "The architect James Gandon designed the rebuilt Shire Hall.",
              ("Gandon",)),
            P("George Green", "en:George Green (mathematician)", "en:Bromley House Library",
              "The mathematician George Green was a member of the subscription library at Bromley House.",
              ("Bromley House", "George Green")),
            P("Brian Clough", "en:Brian Clough", "en:City Ground",
              "Brian Clough managed Nottingham Forest at the City Ground.",
              ("City Ground", "Clough"), at="near:120"),
            P("Jesse Boot", "en:Jesse Boot, 1st Baron Trent", "he:1254566",
              "Almshouses paid for by Jesse Boot, founder of Boots, in 1908 for veterans of the Crimean War and the "
              "Indian Mutiny: the Dorothy Boot Homes in Wilford.",
              ("Jesse Boot", "1908", "Crimean", "Indian Mutiny"),
              # Historic England blocks automated requests; passages copied from the list entry:
              quote=["Paid for by Jesse Boot of Nottingham.",
                     "These almshouses were intended for the use of Crimean War and Indian Mutiny veterans.",
                     "1908"]),
            P("George Green", "en:George Green (mathematician)", "en:Green's Windmill",
              "The mathematician George Green was a miller; his family's windmill in Sneinton is restored and "
              "named after him.",
              ("miller", "windmill")),
            P("Torvill and Dean", "en:Torvill and Dean", "en:National Ice Centre",
              "The ice dancers Jayne Torvill and Christopher Dean come from Nottingham. The square outside the ice "
              "centre is named Bolero Square after their Olympic routine.",
              ("Torvill", "Bolero"), group="sport"),
            P("D. H. Lawrence", "en:D. H. Lawrence", "en:Arkwright Building",
              "Built between 1877 and 1881 for University College Nottingham, where D. H. Lawrence studied during "
              "his teacher-training years.",
              ("1877", "University College", "Lawrence")),
        ]),
]
