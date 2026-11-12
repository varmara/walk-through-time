"""Download the land's other shapes from OpenStreetMap: brooks and springs, woods, disused railways and lost canals,
historic sites, cemeteries, allotments and orchards. (Ponds are in the main download already: s06_land takes
them from there.)

A second, lighter request over the same squares as s00_fetch_osm, so adding these did not download the buildings
again; each square's answer is saved the same way (pipeline/web.py). Licence: ODbL, © OpenStreetMap contributors.

Writes work/<city>/land_osm.json: {"elements": [...]} as Overpass sends them (tags and geometry).
"""
import os

from .common import log, save
from .s00_fetch_osm import squares

HISTORIC = ("archaeological_site|city_walls|citywalls|castle|ruins|earthworks|moat|fort|tumulus|boundary_stone|"
            "well|milestone|mine|mine_shaft|quarry|mill|wayside_cross|cave|ice_house|dovecote|bridge_site|"
            "industrial|kiln|lime_kiln|pinfold|holy_well")


def query(area):
    return f"""[out:json][timeout:180];(
      way["waterway"~"^(stream|brook|ditch|drain|weir)$"]{area}; node["natural"="spring"]{area};
      way["natural"="wood"]{area}; way["landuse"="forest"]{area};
      way["railway"~"^(abandoned|disused|dismantled|razed)$"]{area};
      way["abandoned:railway"]{area}; way["disused:railway"]{area}; way["razed:railway"]{area};
      way["historic"="railway"]{area};
      way["abandoned:waterway"]{area}; way["disused:waterway"]{area}; way["waterway"="derelict_canal"]{area};
      way["historic"="canal"]{area}; way["waterway"="canal"]["disused"="yes"]{area};
      way["waterway"="canal"]["abandoned"="yes"]{area};
      nw["historic"~"^({HISTORIC})$"]{area}; node["natural"="cave_entrance"]{area};
      way["landuse"="cemetery"]{area}; way["amenity"="grave_yard"]{area};
      way["landuse"="allotments"]{area}; way["landuse"="orchard"]{area};
    ); out tags geom qt;
    (relation["natural"="wood"]{area}; relation["landuse"="forest"]{area}; relation["landuse"="cemetery"]{area};
     relation["historic"~"^({HISTORIC})$"]{area};); out body geom qt;"""


def main(city_id):
    # a shorter time limit than the buildings' (the build has the rest of its steps still to run); past it, or on
    # a square that fails twice, the layer is shown with what was fetched, and the next build fetches the rest
    minutes = os.environ.get("WTT_LAND_MINUTES") or (90 if os.environ.get("WTT_OSM_MINUTES") else None)
    elements = squares(city_id, query, "OpenStreetMap land", minutes, partial=True)
    save(city_id, "land_osm", {"elements": elements})
    log(f"    {len(elements)} land elements in total")
