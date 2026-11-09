"""Story layers for Nottingham: the centre and the suburbs either side of the Trent.

Every entry rests on a Wikipedia article. `facts` are strings the article must contain; step s05 checks
them and drops the entry if any is missing. Keep stories to one or two plain sentences, and claim
nothing the article does not say. Name legends as legends. See CONTRIBUTING.md.
"""


def E(name, source, story, facts, at=None, year=None):
    """year: when the building standing today was built or opened ("1855", "c. 1420", "1841..1844").
    Its digits must appear in the article; it becomes a date source next to OpenStreetMap and Wikidata."""
    return {"name": name, "source": source, "story": story, "facts": facts,
            **({"at": at} if at else {}), **({"year": year} if year else {})}


def P(name, person, place, story, facts, at=None, group=None, quote=None):
    """A person and a place. `person` and `place` are Wikipedia articles ("en:Title"); the facts must appear in
    the two articles together, and the place's article decides the building. The type of person comes from
    Wikidata; set `group` only when it has none (architects, writers, science, industry, sport, arts, public)."""
    return {"name": name, "source": person, "place": place, "story": story, "facts": facts,
            **({"at": at} if at else {}), **({"group": group} if group else {}), **({"quote": quote} if quote else {})}


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
              "Each still has its church, joined in the 1840s by a Catholic cathedral.",
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
              ("1950", "largest council estate in europe", "private ownership")),
        ]),
    dict(
        id="sneinton", title="Sneinton",
        intro="The hill east of the city: a windmill, cave dwellings, a market and the birthplace of the Salvation Army's founder.",
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
              ("1930s", "wholesale fruit and vegetable market"), at="name:Sneinton Market"),
            E("William Booth Birthplace Museum", "en:Sneinton",
              "William Booth, founder of the Salvation Army, was born in this house on Notintone Place.",
              ("William Booth Birthplace Museum", "Notintone Place"), at="name:William Booth Birthplace Museum"),
        ]),
    dict(
        id="people", title="People", kind="people",
        intro="People connected with buildings on the map: who designed them, who worked in them and who played "
              "in them. Each link is checked against the Wikipedia articles on the person and the place.",
        entries=[
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
        ]),
]
