"""
agents — Shared utilities for all agent modules.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# Canonical map of city names to data-folder slugs.
# Add entries here as city-specific data files are created.
_CITY_SLUG_MAP: dict[str, str] = {
    "st. petersburg": "st_petersburg",
    "st petersburg": "st_petersburg",
    "saint petersburg": "st_petersburg",
    "pinellas park": "pinellas_park",
    "kenneth city": "kenneth_city",
    "belleair beach": "belleair_beach",
    "belleair bluffs": "belleair_bluffs",
    "indian rocks beach": "indian_rocks_beach",
    "indian shores": "indian_shores",
    "redington shores": "redington_shores",
    "south pasadena": "south_pasadena",
    "tarpon springs": "tarpon_springs",
    "safety harbor": "safety_harbor",
}


def city_slug(city: str) -> Optional[str]:
    """Return the data-folder slug for a city, or None if unknown.

    Tries the curated map first.  Falls back to a normalised version
    (lowercase, spaces/dots → underscores, strip punctuation) so that
    new cities work even before they are added to the map.
    """
    if not city:
        return None
    key = city.strip().lower()
    if key in _CITY_SLUG_MAP:
        return _CITY_SLUG_MAP[key]
    # Fallback: derive from name
    slug = re.sub(r"[.\-']", "", key).replace(" ", "_")
    return slug if slug else None


# ──────────────────────────────────────────────────────────────────────
# Jurisdiction LDC URL Registry
#
# Hard-coded links to each jurisdiction's Land Development Code sections
# on Municode (or other official sources).  The app renders these as
# clickable references so the user can jump straight to the relevant
# ordinance text.
# ──────────────────────────────────────────────────────────────────────

JURISDICTION_CODE_URLS: Dict[str, Dict[str, Any]] = {
    # ── Pinellas County (unincorporated) ──────────────────────────────
    "pinellas": {
        "label": "Pinellas County",
        "zoning": {
            "url": "https://library.municode.com/fl/pinellas_county/codes/code_of_ordinances?nodeId=PTIIPICOCO_CH138LADEV_ARTIIIZODI",
            "section": "Ch. 138, Art. III — Zoning Districts",
        },
        "parking": {
            "url": "https://library.municode.com/fl/pinellas_county/codes/code_of_ordinances?nodeId=PTIIPICOCO_CH138LADEV_ARTVISTSIED_DIV5OREPALO",
            "section": "Ch. 138, Art. VI, Div. 5 — Off-Street Parking and Loading",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/pinellas_county/codes/code_of_ordinances?nodeId=PTIIPICOCO_CH138LADEV_ARTIVLATRPR",
            "section": "Ch. 138, Art. IV — Landscaping & Tree Protection",
        },
        "flum": {
            "url": "https://pinellas-egis.maps.arcgis.com/apps/webappviewer/index.html?id=3b3e40d1403c4a83bc434e929e4c7de9",
            "section": "Pinellas County FLUM Viewer",
        },
    },
    # ── Pasco County ──────────────────────────────────────────────────
    "pasco": {
        "label": "Pasco County",
        "zoning": {
            "url": "https://library.municode.com/fl/pasco_county/codes/land_development_code?nodeId=PT5LADEDINGS500-522ZODISREGUA",
            "section": "LDC Part 5 — Zoning Districts (Secs. 500–522)",
        },
        "parking": {
            "url": "https://library.municode.com/fl/pasco_county/codes/land_development_code?nodeId=PT9SIDERE_S907OFPALORE",
            "section": "LDC Sec. 907 — Off-Street Parking and Loading",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/pasco_county/codes/land_development_code?nodeId=PT9SIDERE_S904BULA",
            "section": "LDC Sec. 904 — Buffers and Landscaping",
        },
        "flum": {
            "url": "https://pascofl.maps.arcgis.com/apps/webappviewer/index.html?id=7b5dd0eebec44af189e1b2b6b8e63c84",
            "section": "Pasco County FLUM Viewer",
        },
    },
    # ── Hillsborough County ───────────────────────────────────────────
    "hillsborough": {
        "label": "Hillsborough County",
        "zoning": {
            "url": "https://library.municode.com/fl/hillsborough_county/codes/land_development_code?nodeId=ARTIIIZODI",
            "section": "LDC Art. III — Zoning Districts",
        },
        "parking": {
            "url": "https://library.municode.com/fl/hillsborough_county/codes/land_development_code?nodeId=ARTVSIDEST_PT5.07.00OFPALO",
            "section": "LDC Sec. 5.07 — Off-Street Parking and Loading",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/hillsborough_county/codes/land_development_code?nodeId=ARTVSIDEST_PT5.10.00LA",
            "section": "LDC Sec. 5.10 — Landscaping",
        },
        "flum": {
            "url": "https://maps.hillsboroughcounty.org/hillsboroughcountygis/",
            "section": "Hillsborough County GIS Viewer",
        },
    },
    # ── St. Petersburg ────────────────────────────────────────────────
    "st_petersburg": {
        "label": "City of St. Petersburg",
        "zoning": {
            "url": "https://library.municode.com/fl/st._petersburg/codes/code_of_ordinances?nodeId=PTIISTAM_CH16LADERE_S16.20.010ZODIEN",
            "section": "City Code Ch. 16 — Land Development Regulations, Sec. 16.20 — Zoning Districts",
        },
        "parking": {
            "url": "https://library.municode.com/fl/st._petersburg/codes/code_of_ordinances?nodeId=PTIISTAM_CH16LADERE_S16.30.070OFPALO",
            "section": "City Code Sec. 16.30.070 — Off-Street Parking and Loading",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/st._petersburg/codes/code_of_ordinances?nodeId=PTIISTAM_CH16LADERE_S16.30.080LA",
            "section": "City Code Sec. 16.30.080 — Landscaping",
        },
        "flum": {
            "url": "https://gis.stpete.org/Html5Viewer/?viewer=planningzoning",
            "section": "St. Petersburg Planning & Zoning Viewer",
        },
    },
    # ── Clearwater ────────────────────────────────────────────────────
    "clearwater": {
        "label": "City of Clearwater",
        "zoning": {
            "url": "https://library.municode.com/fl/clearwater/codes/community_development_code?nodeId=COMMUNITY_DEVELOPMENT_CODE_ARTIIIDEST",
            "section": "Community Development Code Art. III — Development Standards",
        },
        "parking": {
            "url": "https://library.municode.com/fl/clearwater/codes/community_development_code?nodeId=COMMUNITY_DEVELOPMENT_CODE_ARTIIIDEST_DIV14OFREPAam",
            "section": "CDC Art. III, Div. 14 — Off-Street Required Parking",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/clearwater/codes/community_development_code?nodeId=COMMUNITY_DEVELOPMENT_CODE_ARTIIIDEST_DIV12LADEN",
            "section": "CDC Art. III, Div. 12 — Landscaping",
        },
        "flum": {
            "url": "https://www.myclearwater.com/government/city-departments/planning-development/maps-gis",
            "section": "Clearwater Planning & GIS Maps",
        },
    },
    # ── Largo ─────────────────────────────────────────────────────────
    "largo": {
        "label": "City of Largo",
        "zoning": {
            "url": "https://library.municode.com/fl/largo/codes/code_of_ordinances?nodeId=SPAGEam_CH17LADERE_ARTIVDEST",
            "section": "Code Ch. 17, Art. IV — Development Standards",
        },
        "parking": {
            "url": "https://library.municode.com/fl/largo/codes/code_of_ordinances?nodeId=SPAGEAM_CH17LADERE_ARTIVDEST_DIV4PALO",
            "section": "Code Ch. 17, Art. IV, Div. 4 — Parking and Loading",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/largo/codes/code_of_ordinances?nodeId=SPAGEAM_CH17LADERE_ARTIVDEST_DIV3LA",
            "section": "Code Ch. 17, Art. IV, Div. 3 — Landscaping",
        },
        "flum": {
            "url": "https://largo.maps.arcgis.com/apps/webappviewer/index.html?id=5b5fe8b7c8b14b37913b9c6dfc38a1fb",
            "section": "Largo GIS Viewer",
        },
    },
    # ── Dunedin ───────────────────────────────────────────────────────
    "dunedin": {
        "label": "City of Dunedin",
        "zoning": {
            "url": "https://library.municode.com/fl/dunedin/codes/land_development_code?nodeId=LADECOCIDUFL_ARTIIIZODI",
            "section": "LDC Art. III — Zoning Districts",
        },
        "parking": {
            "url": "https://library.municode.com/fl/dunedin/codes/land_development_code?nodeId=LADECOCIDUFL_ARTVDEST_CH5-6PARE",
            "section": "LDC Art. V, Ch. 5-6 — Parking Requirements",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/dunedin/codes/land_development_code?nodeId=LADECOCIDUFL_ARTVDEST_CH5-7LARE",
            "section": "LDC Art. V, Ch. 5-7 — Landscaping Requirements",
        },
        "flum": {
            "url": "https://dunedin.maps.arcgis.com/apps/webappviewer/index.html?id=8c13d02f19b64a8bb67c29db48d7f50f",
            "section": "Dunedin GIS Viewer",
        },
    },
    # ── Pinellas Park ─────────────────────────────────────────────────
    "pinellas_park": {
        "label": "City of Pinellas Park",
        "zoning": {
            "url": "https://library.municode.com/fl/pinellas_park/codes/land_development_code?nodeId=CH18LADECO_AR15.ZO",
            "section": "LDC Art. 15 — Zoning (Secs. 18-1505 thru 18-1528)",
        },
        "parking": {
            "url": "https://library.municode.com/fl/pinellas_park/codes/land_development_code?nodeId=CH18LADECO_AR15.ZO_S18-1532PALOAGRE",
            "section": "LDC Sec. 18-1532 — Parking and Loading",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/pinellas_park/codes/land_development_code?nodeId=CH18LADECO_AR15.ZO_S18-1533LARE",
            "section": "LDC Sec. 18-1533 — Landscaping",
        },
        "flum": {
            "url": "https://pinellaspark.maps.arcgis.com/apps/webappviewer/index.html?id=58d5bf8c0f754c36b61f3c56d08a3d3f",
            "section": "Pinellas Park GIS Viewer",
        },
    },
    # ── Tarpon Springs ────────────────────────────────────────────────
    "tarpon_springs": {
        "label": "City of Tarpon Springs",
        "zoning": {
            "url": "https://library.municode.com/fl/tarpon_springs/codes/code_of_ordinances?nodeId=PTIIICO_APXALADECO_ARTIVZODIST",
            "section": "LDC App. A, Art. IV — Zoning Districts",
        },
        "parking": {
            "url": "https://library.municode.com/fl/tarpon_springs/codes/code_of_ordinances?nodeId=PTIIICO_APXALADECO_ARTVDEST_DIV6OREPALO",
            "section": "LDC App. A, Art. V, Div. 6 — Off-Street Parking and Loading",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/tarpon_springs/codes/code_of_ordinances?nodeId=PTIIICO_APXALADECO_ARTVDEST_DIV5LA",
            "section": "LDC App. A, Art. V, Div. 5 — Landscaping",
        },
        "flum": {
            "url": "https://tarponsprings.maps.arcgis.com/",
            "section": "Tarpon Springs GIS Portal",
        },
    },
    # ── Safety Harbor ─────────────────────────────────────────────────
    "safety_harbor": {
        "label": "City of Safety Harbor",
        "zoning": {
            "url": "https://library.municode.com/fl/safety_harbor/codes/code_of_ordinances?nodeId=PTIICO_CH110LADERE_ARTIVZODI",
            "section": "Code Ch. 110, Art. IV — Zoning Districts",
        },
        "parking": {
            "url": "https://library.municode.com/fl/safety_harbor/codes/code_of_ordinances?nodeId=PTIICO_CH110LADERE_ARTVDEST_DIV5OFPALO",
            "section": "Code Ch. 110, Art. V, Div. 5 — Off-Street Parking and Loading",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/safety_harbor/codes/code_of_ordinances?nodeId=PTIICO_CH110LADERE_ARTVDEST_DIV3LA",
            "section": "Code Ch. 110, Art. V, Div. 3 — Landscaping",
        },
        "flum": {
            "url": "https://safety-harbor-gis-cityofsafetyharbor.hub.arcgis.com/",
            "section": "Safety Harbor GIS Hub",
        },
    },
    # ── Gulfport ──────────────────────────────────────────────────────
    "gulfport": {
        "label": "City of Gulfport",
        "zoning": {
            "url": "https://library.municode.com/fl/gulfport/codes/code_of_ordinances?nodeId=PTIICO_APXALADERE_ARTIIIZODI",
            "section": "LDR App. A, Art. III — Zoning Districts",
        },
        "parking": {
            "url": "https://library.municode.com/fl/gulfport/codes/code_of_ordinances?nodeId=PTIICO_APXALADERE_ARTVDEST_DIV4OFPALO",
            "section": "LDR App. A, Art. V, Div. 4 — Off-Street Parking and Loading",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/gulfport/codes/code_of_ordinances?nodeId=PTIICO_APXALADERE_ARTVDEST_DIV3LA",
            "section": "LDR App. A, Art. V, Div. 3 — Landscaping",
        },
        "flum": {
            "url": "https://mygulfport.us/gis/",
            "section": "Gulfport GIS Portal",
        },
    },
    # ── Seminole ──────────────────────────────────────────────────────
    "seminole": {
        "label": "City of Seminole",
        "zoning": {
            "url": "https://library.municode.com/fl/seminole/codes/code_of_ordinances?nodeId=PTIICO_CH90ZODIRE",
            "section": "Code Ch. 90 — Zoning Districts",
        },
        "parking": {
            "url": "https://library.municode.com/fl/seminole/codes/code_of_ordinances?nodeId=PTIICO_CH90ZODIRE_ARTVIOREPALO",
            "section": "Code Ch. 90, Art. VI — Off-Street Parking and Loading",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/seminole/codes/code_of_ordinances?nodeId=PTIICO_CH90ZODIRE_ARTVLA",
            "section": "Code Ch. 90, Art. V — Landscaping",
        },
        "flum": {
            "url": "https://egis.pinellascounty.org/Html5Viewer/?viewer=pcgis",
            "section": "Pinellas County GIS (Seminole uses county FLUM)",
        },
    },
    # ── Oldsmar ───────────────────────────────────────────────────────
    "oldsmar": {
        "label": "City of Oldsmar",
        "zoning": {
            "url": "https://library.municode.com/fl/oldsmar/codes/code_of_ordinances?nodeId=PTIICO_CH110LADERE_ARTIVZODI",
            "section": "Code Ch. 110, Art. IV — Zoning Districts",
        },
        "parking": {
            "url": "https://library.municode.com/fl/oldsmar/codes/code_of_ordinances?nodeId=PTIICO_CH110LADERE_ARTVDEST_DIV5OFPALO",
            "section": "Code Ch. 110, Art. V, Div. 5 — Off-Street Parking and Loading",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/oldsmar/codes/code_of_ordinances?nodeId=PTIICO_CH110LADERE_ARTVDEST_DIV3LA",
            "section": "Code Ch. 110, Art. V, Div. 3 — Landscaping",
        },
        "flum": {
            "url": "https://oldsmar.maps.arcgis.com/",
            "section": "Oldsmar GIS Portal",
        },
    },
    # ── Kenneth City ──────────────────────────────────────────────────
    "kenneth_city": {
        "label": "Town of Kenneth City",
        "zoning": {
            "url": "https://library.municode.com/fl/kenneth_city/codes/code_of_ordinances",
            "section": "Code of Ordinances — Subpart B, Land Development Code",
        },
        "parking": {
            "url": "https://library.municode.com/fl/kenneth_city/codes/code_of_ordinances",
            "section": "Code of Ordinances — Subpart B, Land Development Code (Parking)",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/kenneth_city/codes/code_of_ordinances",
            "section": "Code of Ordinances — Subpart B, Land Development Code (Landscaping)",
        },
        "flum": {
            "url": "https://egis.pinellascounty.org/Html5Viewer/?viewer=pcgis",
            "section": "Pinellas County GIS (Kenneth City uses county FLUM)",
        },
    },
    # ── Belleair ──────────────────────────────────────────────────────
    "belleair": {
        "label": "Town of Belleair",
        "zoning": {
            "url": "https://library.municode.com/fl/belleair/codes/code_of_ordinances",
            "section": "Code of Ordinances — Zoning",
        },
        "parking": {
            "url": "https://library.municode.com/fl/belleair/codes/code_of_ordinances",
            "section": "Code of Ordinances — Parking",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/belleair/codes/code_of_ordinances",
            "section": "Code of Ordinances — Landscaping",
        },
        "flum": {
            "url": "https://egis.pinellascounty.org/Html5Viewer/?viewer=pcgis",
            "section": "Pinellas County GIS (Belleair uses county FLUM)",
        },
    },
    # ── Belleair Beach ────────────────────────────────────────────────
    "belleair_beach": {
        "label": "City of Belleair Beach",
        "zoning": {
            "url": "https://library.municode.com/fl/belleair_beach/codes/code_of_ordinances",
            "section": "Ch. 94 — Zoning (Art. IV Districts, Art. V Supplemental)",
        },
        "parking": {
            "url": "https://library.municode.com/fl/belleair_beach/codes/code_of_ordinances",
            "section": "Ch. 94 — Zoning (Parking provisions)",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/belleair_beach/codes/code_of_ordinances",
            "section": "Ch. 94 — Zoning (Landscaping provisions)",
        },
        "flum": {
            "url": "https://egis.pinellascounty.org/Html5Viewer/?viewer=pcgis",
            "section": "Pinellas County GIS (Belleair Beach uses county FLUM)",
        },
    },
    # ── Belleair Bluffs ───────────────────────────────────────────────
    "belleair_bluffs": {
        "label": "City of Belleair Bluffs",
        "zoning": {
            "url": "https://library.municode.com/fl/belleair_bluffs/codes/code_of_ordinances",
            "section": "Ch. 102 — Land Development Code (Zoning)",
        },
        "parking": {
            "url": "https://library.municode.com/fl/belleair_bluffs/codes/code_of_ordinances",
            "section": "Ch. 102 — Land Development Code (Parking)",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/belleair_bluffs/codes/code_of_ordinances",
            "section": "Ch. 102 — Land Development Code (Landscaping)",
        },
        "flum": {
            "url": "https://egis.pinellascounty.org/Html5Viewer/?viewer=pcgis",
            "section": "Pinellas County GIS (Belleair Bluffs uses county FLUM)",
        },
    },
    # ── Indian Rocks Beach ────────────────────────────────────────────
    "indian_rocks_beach": {
        "label": "City of Indian Rocks Beach",
        "zoning": {
            "url": "https://library.municode.com/fl/indian_rocks_beach/codes/code_of_ordinances",
            "section": "Code of Ordinances — Zoning",
        },
        "parking": {
            "url": "https://library.municode.com/fl/indian_rocks_beach/codes/code_of_ordinances",
            "section": "Code of Ordinances — Parking",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/indian_rocks_beach/codes/code_of_ordinances",
            "section": "Code of Ordinances — Landscaping",
        },
        "flum": {
            "url": "https://egis.pinellascounty.org/Html5Viewer/?viewer=pcgis",
            "section": "Pinellas County GIS (Indian Rocks Beach uses county FLUM)",
        },
    },
    # ── Indian Shores ─────────────────────────────────────────────────
    "indian_shores": {
        "label": "Town of Indian Shores",
        "zoning": {
            "url": "https://library.municode.com/fl/indian_shores/codes/code_of_ordinances",
            "section": "Code of Ordinances — Zoning",
        },
        "parking": {
            "url": "https://library.municode.com/fl/indian_shores/codes/code_of_ordinances",
            "section": "Code of Ordinances — Parking",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/indian_shores/codes/code_of_ordinances",
            "section": "Code of Ordinances — Landscaping",
        },
        "flum": {
            "url": "https://egis.pinellascounty.org/Html5Viewer/?viewer=pcgis",
            "section": "Pinellas County GIS (Indian Shores uses county FLUM)",
        },
    },
    # ── Redington Shores ──────────────────────────────────────────────
    "redington_shores": {
        "label": "Town of Redington Shores",
        "zoning": {
            "url": "https://library.municode.com/fl/redington_shores/codes/code_of_ordinances",
            "section": "Ch. 90 — Land Development Regulations (Zoning)",
        },
        "parking": {
            "url": "https://library.municode.com/fl/redington_shores/codes/code_of_ordinances",
            "section": "Ch. 90 — Land Development Regulations (Parking)",
        },
        "landscape": {
            "url": "https://library.municode.com/fl/redington_shores/codes/code_of_ordinances",
            "section": "Ch. 90 — Land Development Regulations (Landscaping)",
        },
        "flum": {
            "url": "https://egis.pinellascounty.org/Html5Viewer/?viewer=pcgis",
            "section": "Pinellas County GIS (Redington Shores uses county FLUM)",
        },
    },
    # ── South Pasadena ────────────────────────────────────────────────
    "south_pasadena": {
        "label": "City of South Pasadena",
        "zoning": {
            "url": "https://ecode360.com/14079132",
            "section": "Ch. 130, Art. III — Zoning Districts (§ 130-5 thru § 130-18.1)",
        },
        "parking": {
            "url": "https://ecode360.com/14079457",
            "section": "Ch. 130, Art. IV — Off-Street Parking and Loading (§ 130-19)",
        },
        "landscape": {
            "url": "https://ecode360.com/14079470",
            "section": "Ch. 130, § 130-20 — Landscaping Requirements",
        },
        "flum": {
            "url": "https://egis.pinellascounty.org/Html5Viewer/?viewer=pcgis",
            "section": "Pinellas County GIS (South Pasadena uses county FLUM)",
        },
    },
}


def get_code_urls(county: str, city: str = "") -> Optional[Dict[str, Any]]:
    """Return the code URL registry entry for a jurisdiction.

    Tries city-specific first; falls back to county.
    """
    slug = city_slug(city)
    if slug and slug in JURISDICTION_CODE_URLS:
        return JURISDICTION_CODE_URLS[slug]
    county_key = county.strip().lower()
    if county_key in JURISDICTION_CODE_URLS:
        return JURISDICTION_CODE_URLS[county_key]
    return None


def get_code_url(county: str, topic: str, city: str = "") -> Optional[Dict[str, str]]:
    """Return {"url": ..., "section": ...} for a specific topic.

    topic: 'zoning', 'parking', 'landscape', 'flum'
    """
    entry = get_code_urls(county, city)
    if entry:
        return entry.get(topic)
    return None
