"""
agents/infrastructure_agent.py — Infrastructure data lookup agent.

Queries:
  - Pinellas County GIS (Roads, RightOfWay/Easements)
  - FDOT state road identification via road jurisdiction field
  - Utility provider assignment via city-based lookup table
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
_TIMEOUT = 15

# ──────────────────────────────────────────────────────────────────────
# Utility provider lookup — Pinellas County cities
# Based on public utility service territory assignments.
# PCU = Pinellas County Utilities
# ──────────────────────────────────────────────────────────────────────
_UTILITY_PROVIDERS: Dict[str, Dict[str, str]] = {
    "st. petersburg":      {"water": "City of St. Petersburg",     "sewer": "City of St. Petersburg",     "reclaim": "City of St. Petersburg",     "storm": "City of St. Petersburg"},
    "saint petersburg":    {"water": "City of St. Petersburg",     "sewer": "City of St. Petersburg",     "reclaim": "City of St. Petersburg",     "storm": "City of St. Petersburg"},
    "clearwater":          {"water": "City of Clearwater",          "sewer": "City of Clearwater",          "reclaim": "City of Clearwater",          "storm": "City of Clearwater"},
    "largo":               {"water": "City of Largo",               "sewer": "Pinellas County Utilities (PCU)", "reclaim": "City of Largo", "storm": "Pinellas County / City of Largo"},
    "dunedin":             {"water": "City of Dunedin",             "sewer": "City of Dunedin",             "reclaim": "City of Dunedin",             "storm": "City of Dunedin"},
    "tarpon springs":      {"water": "City of Tarpon Springs",      "sewer": "City of Tarpon Springs",      "reclaim": "City of Tarpon Springs",      "storm": "City of Tarpon Springs"},
    "pinellas park":       {"water": "Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "Pinellas County Utilities (PCU)", "storm": "Pinellas County"},
    "safety harbor":       {"water": "City of Safety Harbor",       "sewer": "City of Safety Harbor",       "reclaim": "City of Safety Harbor",       "storm": "City of Safety Harbor"},
    "oldsmar":             {"water": "City of Oldsmar",             "sewer": "City of Oldsmar",             "reclaim": "City of Oldsmar",             "storm": "City of Oldsmar"},
    "seminole":            {"water": "Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "Pinellas County Utilities (PCU)", "storm": "Pinellas County"},
    "kenneth city":        {"water": "Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "Pinellas County Utilities (PCU)", "storm": "Pinellas County"},
    "gulfport":            {"water": "City of Gulfport / Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "Pinellas County Utilities (PCU)", "storm": "City of Gulfport"},
    "south pasadena":      {"water": "Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "Pinellas County Utilities (PCU)", "storm": "Pinellas County"},
    "st pete beach":       {"water": "City of St. Pete Beach",      "sewer": "Pinellas County Utilities (PCU)", "reclaim": "N/A",                             "storm": "City of St. Pete Beach"},
    "saint pete beach":    {"water": "City of St. Pete Beach",      "sewer": "Pinellas County Utilities (PCU)", "reclaim": "N/A",                             "storm": "City of St. Pete Beach"},
    "treasure island":     {"water": "Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "N/A",                         "storm": "City of Treasure Island"},
    "madeira beach":       {"water": "Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "N/A",                         "storm": "City of Madeira Beach"},
    "redington beach":     {"water": "Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "N/A",                         "storm": "Pinellas County"},
    "north redington beach": {"water": "Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "N/A",                       "storm": "Pinellas County"},
    "redington shores":    {"water": "Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "N/A",                         "storm": "Pinellas County"},
    "indian rocks beach":  {"water": "Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "N/A",                         "storm": "City of Indian Rocks Beach"},
    "indian shores":       {"water": "Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "N/A",                         "storm": "City of Indian Shores"},
    "belleair":            {"water": "Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "Pinellas County Utilities (PCU)", "storm": "Pinellas County"},
    "belleair beach":      {"water": "Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "N/A",                         "storm": "Pinellas County"},
    "belleair bluffs":     {"water": "Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "Pinellas County Utilities (PCU)", "storm": "Pinellas County"},
    "belleair shore":      {"water": "Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "N/A",                         "storm": "Pinellas County"},
    "palm harbor":         {"water": "Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "Pinellas County Utilities (PCU)", "storm": "Pinellas County"},
    "east lake":           {"water": "Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "Pinellas County Utilities (PCU)", "storm": "Pinellas County"},
    "tierra verde":        {"water": "Pinellas County Utilities (PCU)", "sewer": "Pinellas County Utilities (PCU)", "reclaim": "N/A",                         "storm": "Pinellas County"},
}

_DEFAULT_UTILITY = {
    "water": "Pinellas County Utilities (PCU)",
    "sewer": "Pinellas County Utilities (PCU)",
    "reclaim": "Pinellas County Utilities (PCU)",
    "storm": "Pinellas County",
}

# Pasco County utility providers by city/area
_PASCO_UTILITY_PROVIDERS: Dict[str, Dict[str, str]] = {
    "new port richey":  {"water": "Pasco County Utilities (PCU) / City of New Port Richey (verify)", "sewer": "Pasco County Utilities (PCU)", "reclaim": "Pasco County Utilities (PCU)", "storm": "Pasco County"},
    "port richey":      {"water": "Pasco County Utilities (PCU)", "sewer": "Pasco County Utilities (PCU)", "reclaim": "Pasco County Utilities (PCU)", "storm": "Pasco County"},
    "holiday":          {"water": "Pasco County Utilities (PCU)", "sewer": "Pasco County Utilities (PCU)", "reclaim": "Pasco County Utilities (PCU)", "storm": "Pasco County"},
    "trinity":          {"water": "Pasco County Utilities (PCU)", "sewer": "Pasco County Utilities (PCU)", "reclaim": "Pasco County Utilities (PCU)", "storm": "Pasco County"},
    "land o lakes":     {"water": "Pasco County Utilities (PCU)", "sewer": "Pasco County Utilities (PCU)", "reclaim": "Pasco County Utilities (PCU)", "storm": "Pasco County"},
    "lutz":             {"water": "Pasco County Utilities (PCU)", "sewer": "Pasco County Utilities (PCU)", "reclaim": "Pasco County Utilities (PCU)", "storm": "Pasco County"},
    "zephyrhills":      {"water": "City of Zephyrhills", "sewer": "City of Zephyrhills", "reclaim": "N/A — verify with City", "storm": "City of Zephyrhills / Pasco County"},
    "dade city":        {"water": "City of Dade City", "sewer": "City of Dade City", "reclaim": "N/A — verify with City", "storm": "City of Dade City / Pasco County"},
    "wesley chapel":    {"water": "Pasco County Utilities (PCU)", "sewer": "Pasco County Utilities (PCU)", "reclaim": "Pasco County Utilities (PCU)", "storm": "Pasco County"},
    "hudson":           {"water": "Pasco County Utilities (PCU)", "sewer": "Pasco County Utilities (PCU)", "reclaim": "Pasco County Utilities (PCU)", "storm": "Pasco County"},
    "spring hill":      {"water": "Pasco County Utilities (PCU)", "sewer": "Pasco County Utilities (PCU)", "reclaim": "Pasco County Utilities (PCU)", "storm": "Pasco County"},
    "odessa":           {"water": "Pasco County Utilities (PCU)", "sewer": "Pasco County Utilities (PCU)", "reclaim": "Pasco County Utilities (PCU)", "storm": "Pasco County"},
}

_PASCO_DEFAULT_UTILITY = {
    "water": "Pasco County Utilities (PCU) — verify availability at (727) 847-2411",
    "sewer": "Pasco County Utilities (PCU) — verify availability or OSTDS",
    "reclaim": "Pasco County Utilities (PCU) — verify service area",
    "storm": "Pasco County Stormwater",
}

# ──────────────────────────────────────────────────────────────────────
# Road class and jurisdiction code decoders
# ──────────────────────────────────────────────────────────────────────
_ROADCLASS_MAP = {
    "MA": "Major Arterial",
    "A":  "Arterial",
    "C":  "Collector",
    "L":  "Local",
    "PR": "Private",
    "AL": "Alley",
    "FR": "Frontage Road",
    "I":  "Interstate",
    "US": "US Highway",
    "SR": "State Road",
}

_SEGJURIS_MAP = {
    "DOT":   "FDOT (State Road)",
    "CITY":  "City",
    "CO":    "County",
    "19":    "City of St. Petersburg",
    "1":     "Clearwater",
    "10":    "Dunedin",
    "11":    "Gulfport",
    "12":    "Indian Rocks Beach",
    "13":    "Indian Shores",
    "14":    "Kenneth City",
    "15":    "Largo",
    "16":    "Madeira Beach",
    "17":    "North Redington Beach",
    "18":    "Oldsmar",
    "20":    "Pinellas Park",
    "21":    "Redington Beach",
    "22":    "Redington Shores",
    "23":    "Safety Harbor",
    "24":    "Seminole",
    "25":    "South Pasadena",
    "26":    "St. Pete Beach",
    "27":    "Tarpon Springs",
    "28":    "Treasure Island",
    "PINCO": "Pinellas County",
    "PC":    "Pinellas County",
}

# Pinellas easement layer IDs (from RightOfWay MapServer)
_EASEMENT_LAYERS = {
    9: "Drainage Easement",
    3: "Utility Easement",
    6: "Sidewalk Easement",
    8: "Grading Easement",
    7: "Public Right of Way",
    5: "Subordination Agreement",
    4: "Other Easement",
}

_ORDINAL_RE = re.compile(r"\b(\d+)(St|Nd|Rd|Th)\b")
_PINELLAS_BASE = "https://egis.pinellas.gov/gis/rest/services/PublicWebGIS"
_GEOCODE_URL = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"


class InfrastructureAgent:

    def _geocode(self, address: str, city: str, zip_code: str) -> Optional[tuple]:
        single_line = ", ".join(p for p in [address, city, "FL", zip_code] if p)
        try:
            r = _SESSION.get(
                _GEOCODE_URL,
                params={"SingleLine": single_line, "maxLocations": 1, "f": "json"},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            candidates = r.json().get("candidates", [])
            if candidates and candidates[0].get("score", 0) >= 70:
                loc = candidates[0]["location"]
                return float(loc["y"]), float(loc["x"])
        except Exception as exc:
            logger.warning("Geocode failed: %s", exc)
        return None, None

    def _query_layer(self, service: str, layer_id: int, lat: float, lon: float,
                     fields: str, distance_ft: int = 500) -> List[Dict]:
        url = f"{_PINELLAS_BASE}/{service}/MapServer/{layer_id}/query"
        params = {
            "geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "distance": distance_ft,
            "units": "esriSRUnit_Foot",
            "outFields": fields,
            "returnGeometry": "false",
            "f": "json",
        }
        try:
            r = _SESSION.get(url, params=params, timeout=_TIMEOUT)
            r.raise_for_status()
            d = r.json()
            if d.get("error"):
                logger.warning("Layer %s/%s error: %s", service, layer_id, d["error"])
                return []
            return [f["attributes"] for f in d.get("features", [])]
        except Exception as exc:
            logger.warning("Layer query failed %s/%s: %s", service, layer_id, exc)
            return []

    def _get_utilities(self, city: str) -> Dict[str, str]:
        key = (city or "").strip().lower()
        # Try exact match first, then partial
        util = _UTILITY_PROVIDERS.get(key)
        if not util:
            for k, v in _UTILITY_PROVIDERS.items():
                if k in key or key in k:
                    util = v
                    break
        return util or dict(_DEFAULT_UTILITY)

    def _get_pasco_utilities(self, city: str) -> Dict[str, str]:
        key = (city or "").strip().lower()
        util = _PASCO_UTILITY_PROVIDERS.get(key)
        if not util:
            for k, v in _PASCO_UTILITY_PROVIDERS.items():
                if k in key or key in k:
                    util = v
                    break
        return util or dict(_PASCO_DEFAULT_UTILITY)

    def _lookup_pasco(self, address: str, city: str, zip_code: str,
                      lat: float, lon: float) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        # Utilities
        util = self._get_pasco_utilities(city)
        result["utilities_water"] = util["water"]
        result["utilities_sewer"] = util["sewer"]
        result["utilities_reclaim"] = util["reclaim"]
        result["utilities_storm"] = util["storm"]
        result["utilities_gas"] = "Peoples Gas (TECO) — (877) 832-6747 | peoplesgas.com"
        result["utilities_electric"] = "Duke Energy Florida — (800) 700-8744 | duke-energy.com"

        # Roads — use Pasco County ArcGIS roads service
        result["roadway_improvements"] = self._get_pasco_roads(lat, lon)

        result["easements_required"] = (
            "Verify recorded easements with title search and Pasco County Property Appraiser records.\n"
            "Contact Pasco County Development Services regarding any required conservation, drainage, "
            "or utility easements for the proposed development."
        )
        result["utility_extensions"] = (
            "Verify utility availability and capacity with Pasco County Utilities (PCU) at (727) 847-2411.\n"
            "Water/sewer availability letter from PCU required before site plan approval.\n"
            "Extensions may require developer-funded main extension and capacity reservation fee."
        )
        result["additional_access"] = (
            "Additional access may be available from alley or secondary street where present.\n"
            "Confirm with site survey and Pasco County Development Services."
        )
        return result

    def _get_pasco_roads(self, lat: float, lon: float) -> str:
        """Query Pasco County roads ArcGIS service for adjacent roads."""
        geom = json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}})
        try:
            r = _SESSION.get(
                "https://maps.pascopa.com/arcgis/rest/services/Roads/MapServer/0/query",
                params={
                    "geometry": geom, "geometryType": "esriGeometryPoint",
                    "inSR": "4326", "distance": 600, "units": "esriSRUnit_Foot",
                    "outFields": "FULLNAME,ROADCLASS,MAINTBY",
                    "returnGeometry": "false", "f": "json",
                },
                timeout=_TIMEOUT,
            )
            features = r.json().get("features", [])
            if features:
                seen: set = set()
                roads = []
                for f in features:
                    a = f.get("attributes") or {}
                    name = str(a.get("FULLNAME") or "").strip()
                    if name and name not in seen:
                        seen.add(name)
                        roads.append(name)
                if roads:
                    return "Adjacent Roads (Pasco County):\n" + "\n".join(f"  • {r}" for r in roads)
        except Exception as exc:
            logger.warning("Pasco roads query failed: %s", exc)
        return (
            "Adjacent road data not available from Pasco GIS. "
            "Verify road jurisdiction and ROW requirements with Pasco County Engineering."
        )

    def _get_adjacent_roads(self, lat: float, lon: float) -> Dict[str, Any]:
        # Query all three road layers: major (0), arterial (1), local (2)
        all_features: List[Dict] = []
        for layer_id in (0, 1, 2):
            features = self._query_layer(
                "Roads", layer_id, lat, lon,
                "FULLNAME,ROADCLASS,SEGJURIS,STROUTE,FEDROUTE,MAINTBY",
                distance_ft=600,
            )
            all_features.extend(features)

        if not all_features:
            return {}

        roads = []
        fdot_roads = []
        seen_names: set = set()
        for attrs in all_features:
            name = str(attrs.get("FULLNAME") or "").strip().title()
            # Fix title() artifacts with ordinals: 4Th → 4th, 1St → 1st
            name = _ORDINAL_RE.sub(lambda m: m.group(1) + m.group(2).lower(), name)
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            rc = attrs.get("ROADCLASS", "")
            rc_label = _ROADCLASS_MAP.get(rc, rc)
            juris = attrs.get("SEGJURIS", "")
            juris_label = _SEGJURIS_MAP.get(str(juris or ""), str(juris or ""))
            stroute = attrs.get("STROUTE", "")
            fedroute = attrs.get("FEDROUTE", "")

            road_desc = name
            if rc_label:
                road_desc += f" ({rc_label})"
            if juris_label:
                road_desc += f" — {juris_label}"
            if stroute:
                road_desc += f", SR-{stroute}"
            elif fedroute:
                road_desc += f", US-{fedroute}"

            if road_desc not in roads:
                roads.append(road_desc)
            if str(juris or "").upper() == "DOT" or stroute:
                note = name
                if stroute:
                    note += f" (SR-{stroute})"
                elif fedroute:
                    note += f" (US-{fedroute})"
                if note not in fdot_roads:
                    fdot_roads.append(note)

        return {
            "roads_summary": "\n".join(roads),
            "fdot_roads": fdot_roads,
        }

    def _get_easements(self, lat: float, lon: float) -> List[str]:
        found = []
        for layer_id, label in _EASEMENT_LAYERS.items():
            features = self._query_layer(
                "RightOfWay", layer_id, lat, lon,
                "ROWTYPE,OWNERNAME,COMMENTS,ACQUIREWIDTH",
                distance_ft=300,
            )
            for attrs in features:
                desc = label
                if attrs.get("OWNERNAME"):
                    desc += f" — {attrs['OWNERNAME']}"
                if attrs.get("ACQUIREWIDTH"):
                    desc += f" ({attrs['ACQUIREWIDTH']} ft wide)"
                if attrs.get("COMMENTS"):
                    desc += f": {attrs['COMMENTS']}"
                if desc not in found:
                    found.append(desc)
        return found

    def lookup(
        self,
        address: str,
        city: str,
        zip_code: str,
        county: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Returns a dict with keys matching infrastructure state fields.
        """
        result: Dict[str, Any] = {}

        # Geocode if no coordinates provided
        if not lat or not lon:
            lat, lon = self._geocode(address, city, zip_code)

        if not lat or not lon:
            return {"error": "Could not geocode the address. Ensure a property has been looked up first."}

        # Route by county
        if (county or "").strip() == "Pasco":
            return self._lookup_pasco(address, city, zip_code, lat, lon)

        # ── Pinellas (default) ─────────────────────────────────────────
        # ── Utility Providers ──────────────────────────────────────────
        util = self._get_utilities(city)
        result["utilities_water"] = util["water"]
        result["utilities_sewer"] = util["sewer"]
        result["utilities_reclaim"] = util["reclaim"]
        result["utilities_storm"] = util["storm"]

        # Gas and Electric are county-wide in most of Pinellas
        result["utilities_gas"] = "TECO Peoples Gas"
        result["utilities_electric"] = "Duke Energy Florida"

        # ── Adjacent Roads & ROW ───────────────────────────────────────
        roads_data = self._get_adjacent_roads(lat, lon)
        roads_summary = roads_data.get("roads_summary", "")
        fdot_roads = roads_data.get("fdot_roads", [])

        if roads_summary:
            row_text = f"Adjacent Roads:\n{roads_summary}"
            if fdot_roads:
                row_text += (
                    "\n\nNote: The following adjacent road(s) are under FDOT jurisdiction — "
                    "access modifications will require FDOT approval:\n"
                    + "\n".join(f"  • {r}" for r in fdot_roads)
                )
            result["roadway_improvements"] = row_text

        # ── Easements ──────────────────────────────────────────────────
        easements = self._get_easements(lat, lon)
        if easements:
            result["easements_required"] = "\n".join(f"• {e}" for e in easements)
        else:
            result["easements_required"] = "No recorded easements found within 300 ft. Verify with title search."

        # ── SWFWMD note ────────────────────────────────────────────────
        result["utility_extensions"] = (
            "Verify with utility provider(s) whether extensions are required for the proposed use. "
            "Utility atlas maps should be requested from the respective provider(s) prior to permitting."
        )

        # ── Access note ────────────────────────────────────────────────
        result["additional_access"] = (
            "Additional access may be available from alley or secondary street where present. "
            "Confirm with site survey and local jurisdiction."
        )

        return result
