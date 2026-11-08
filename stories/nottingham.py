"""Story layers for Nottingham city centre.

Every entry rests on a Wikipedia article. `facts` are strings the article must contain; step s05 checks
them and drops the entry if any is missing. Keep stories to one or two plain sentences, and claim
nothing the article does not say. Name legends as legends. See CONTRIBUTING.md.
"""


def E(name, source, story, facts, at=None):
    return {"name": name, "source": source, "story": story, "facts": facts, **({"at": at} if at else {})}


CURATED = [
    dict(
        id="inns", title="Old inns",
        intro="Three pubs in the centre each claim to be the oldest inn in England. "
              "The claims rest on tradition more than records, but the buildings are genuinely old.",
        entries=[
            E("Ye Olde Trip to Jerusalem", "en:Ye Olde Trip to Jerusalem",
              "Claims to date from 1189, a date that rests on tradition rather than records. "
              "It is built against the castle rock, with rooms cut into the sandstone.",
              ("1189", "sandstone")),
            E("Bell Inn", "en:Bell Inn, Nottingham",
              "One of the pubs that claims to be the oldest in England, on the edge of the Old Market Square.",
              ("oldest",)),
            E("Salutation Inn", "en:Salutation Inn, Nottingham",
              "Another claimant to the title of England's oldest inn, with caves cut into the rock beneath it.",
              ("oldest", "caves")),
        ]),
    dict(
        id="churches", title="Churches",
        intro="Medieval Nottingham had three parishes: St Mary's, St Peter's and St Nicholas'. "
              "Each still has its church, joined in the 1840s by a Catholic cathedral.",
        entries=[
            E("St Mary's Church", "en:St Mary's Church, Nottingham",
              "The oldest religious foundation in the city and its largest medieval building, on a site "
              "mentioned in the Domesday Book.",
              ("Domesday", "largest")),
            E("St Peter's Church", "en:St Peter's Church, Nottingham",
              "One of the three medieval parish churches of Nottingham, a short walk from the Old Market Square.",
              ("medieval",)),
            E("St Nicholas' Church", "en:St Nicholas' Church, Nottingham",
              "The medieval church was pulled down during the Civil War; the brick church standing today "
              "was finished in 1678.",
              ("Civil War", "1678")),
            E("Cathedral of St Barnabas", "en:Cathedral of St Barnabas, Nottingham",
              "A Catholic cathedral designed by Augustus Pugin and opened in 1844.",
              ("Pugin", "1844")),
        ]),
    dict(
        id="lace", title="Lace and trade",
        intro="In the 19th century Nottingham was a world centre of lace. Merchants built warehouses and "
              "showrooms in the Lace Market, east of the Old Market Square.",
        entries=[
            E("Adams Building", "en:Adams Building",
              "A lace warehouse built for the merchant Thomas Adams and designed by Thomas Chambers Hine.",
              ("Thomas Adams", "Hine")),
            E("Severns Building", "en:Severns Building",
              "A medieval timber-framed house. It was taken down in 1970 and rebuilt on Castle Road "
              "to make way for a shopping centre.",
              ("1970", "Castle Road")),
            E("Victoria Centre", "en:Victoria Centre",
              "A shopping centre opened in 1972 on the site of Nottingham Victoria railway station, "
              "whose clock tower still stands beside it.",
              ("1972", "clock tower")),
        ]),
    dict(
        id="civic", title="Civic Nottingham",
        intro="The buildings where the town and county were governed, judged and connected to the railway.",
        entries=[
            E("Council House", "en:Council House, Nottingham",
              "Designed by Thomas Cecil Howitt and opened in 1929, on the site of the old Exchange "
              "at the head of the Old Market Square.",
              ("Howitt", "1929", "Exchange")),
            E("Guildhall", "en:Nottingham Guildhall",
              "The Victorian Guildhall, completed in 1888, held the city's courts and police station.",
              ("1888",)),
            E("Shire Hall", "en:Shire Hall, Nottingham",
              "The county courthouse and gaol, rebuilt to a design by James Gandon. "
              "It is now the National Justice Museum.",
              ("Gandon", "National Justice Museum")),
            E("Nottingham station", "en:Nottingham railway station",
              "The station building of red brick and terracotta opened in 1904.",
              ("1904", "terracotta")),
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
              "A Georgian town house of 1752, home to a subscription library since 1822.",
              ("1752", "1822")),
            E("Theatre Royal", "en:Theatre Royal, Nottingham",
              "Opened in 1865 and designed by Charles J. Phipps.",
              ("1865", "Phipps")),
            E("Royal Concert Hall", "en:Royal Concert Hall, Nottingham",
              "A concert hall built next to the Theatre Royal and opened in 1982.",
              ("1982",)),
            E("Albert Hall", "en:Albert Hall, Nottingham",
              "Built as a Methodist mission hall and opened in 1909.",
              ("Methodist", "1909")),
            E("Nottingham Playhouse", "en:Nottingham Playhouse",
              "A modernist theatre designed by Peter Moro, opened in 1963.",
              ("Moro", "1963")),
            E("Nottingham Contemporary", "en:Nottingham Contemporary",
              "An art centre designed by Caruso St John and opened in 2009, its walls patterned with lace.",
              ("Caruso St John", "2009", "lace")),
            E("Arkwright Building", "en:Arkwright Building",
              "Built for University College Nottingham and now part of Nottingham Trent University.",
              ("University College",)),
        ]),
]
