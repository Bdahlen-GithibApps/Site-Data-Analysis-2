"""
agents/environmental_agent.py — Environmental data lookup agent.

Data sources:
  - FEMA NFHL (flood zones, BFE) — confirmed working
  - Pinellas SurveyCoastal (CCCL proximity) — confirmed working
  - Authoritative template text for geotechnical, SWFWMD, building code
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
_TIMEOUT = 20

_FEMA_FLOOD_URL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
_CCCL_URL = "https://egis.pinellas.gov/gis/rest/services/PublicWebGIS/SurveyCoastal/MapServer/1/query"
_GEOCODE_URL = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"

# ──────────────────────────────────────────────────────────────────────
# Flood zone decoders
# ──────────────────────────────────────────────────────────────────────
_ZONE_DESCRIPTIONS = {
    "AE":   "Zone AE — Special Flood Hazard Area (100-year floodplain). Base Flood Elevation (BFE) established.",
    "AO":   "Zone AO — Special Flood Hazard Area with shallow flooding (sheet flow). Average depths 1–3 ft.",
    "AH":   "Zone AH — Special Flood Hazard Area with shallow ponding. BFE established.",
    "A":    "Zone A — Special Flood Hazard Area. No BFE established.",
    "VE":   "Zone VE — Coastal High Hazard Area (CHHA). 100-year coastal flood with wave action. BFE established.",
    "V":    "Zone V — Coastal High Hazard Area. No BFE established.",
    "X":    "Zone X — Minimal Flood Hazard (outside 500-year floodplain).",
    "D":    "Zone D — Undetermined flood hazard.",
}

_SFHA_ZONES = {"AE", "AO", "AH", "A", "VE", "V", "A99", "AR", "AE"}
_COASTAL_ZONES = {"VE", "V"}


class EnvironmentalAgent:

    def _geocode(self, address: str, city: str, zip_code: str) -> tuple:
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

    def _get_flood_zone(self, lat: float, lon: float) -> Dict[str, Any]:
        geom = json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}})
        try:
            r = _SESSION.get(
                _FEMA_FLOOD_URL,
                params={
                    "geometry": geom,
                    "geometryType": "esriGeometryPoint",
                    "inSR": "4326",
                    "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE,DEPTH",
                    "returnGeometry": "false",
                    "f": "json",
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            features = r.json().get("features", [])
            if features:
                return features[0]["attributes"]
        except Exception as exc:
            logger.warning("FEMA flood query failed: %s", exc)
        return {}

    def _near_cccl(self, lat: float, lon: float, distance_ft: int = 2000) -> bool:
        geom = json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}})
        try:
            r = _SESSION.get(
                _CCCL_URL,
                params={
                    "geometry": geom,
                    "geometryType": "esriGeometryPoint",
                    "inSR": "4326",
                    "distance": distance_ft,
                    "units": "esriSRUnit_Foot",
                    "outFields": "OBJECTID",
                    "returnGeometry": "false",
                    "f": "json",
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            return len(r.json().get("features", [])) > 0
        except Exception as exc:
            logger.warning("CCCL query failed: %s", exc)
        return False

    def _build_fields(self, flood: Dict[str, Any], near_cccl: bool) -> Dict[str, str]:
        fld_zone = str(flood.get("FLD_ZONE") or "").strip().upper()
        zone_subty = str(flood.get("ZONE_SUBTY") or "").strip()
        sfha = str(flood.get("SFHA_TF") or "").strip().upper() == "T"
        bfe_raw = flood.get("STATIC_BFE", -9999)
        bfe = float(bfe_raw) if bfe_raw and bfe_raw != -9999 else None
        is_coastal = fld_zone in _COASTAL_ZONES
        is_sfha = sfha or fld_zone in _SFHA_ZONES

        zone_desc = _ZONE_DESCRIPTIONS.get(fld_zone, f"Zone {fld_zone}" if fld_zone else "Flood zone undetermined")
        if zone_subty and zone_subty.upper() not in zone_desc.upper():
            zone_desc += f" ({zone_subty.title()})"

        result: Dict[str, str] = {}

        # ── stormwater_treatment ──────────────────────────────────────
        sw_lines = [
            "SWFWMD Environmental Resource Permit (ERP) or exemption required prior to site development.",
            "Post-development discharge must not exceed pre-development rates for the 25-year/24-hour storm event.",
            "Treatment volume: minimum 0.5-inch dry retention or 1-inch wet detention.",
        ]
        if is_sfha:
            sw_lines.append(
                "Site is within a FEMA Special Flood Hazard Area — compensatory storage may be required "
                "for any fill within the floodplain."
            )
        result["stormwater_treatment"] = "\n".join(sw_lines)

        # ── wetlands_flood ─────────────────────────────────────────────
        wf_lines = [f"FEMA Flood Zone: {zone_desc}"]
        if is_sfha:
            wf_lines.append("Site is within a Special Flood Hazard Area (SFHA). Flood insurance required for federally-backed mortgages.")
        else:
            wf_lines.append("Site is not within a Special Flood Hazard Area.")
        wf_lines.append(
            "Wetland delineation by a qualified environmental professional is recommended prior to "
            "permitting. Consult USACE and FDEP for wetland jurisdictional determination."
        )
        result["wetlands_flood"] = "\n".join(wf_lines)

        # ── flood_elevation ────────────────────────────────────────────
        if is_sfha and bfe is not None:
            fe_lines = [
                f"Base Flood Elevation (BFE): {bfe:.1f} ft NAVD88.",
                "Minimum finished floor elevation: BFE + 1 ft per Florida Building Code.",
            ]
            if is_coastal:
                fe_lines.append("Coastal Zone: Wave action considered. Bottom of lowest horizontal structural member must be at or above BFE.")
        elif is_sfha:
            fe_lines = [
                "Site is within SFHA but no BFE is established for this zone.",
                "Consult local floodplain administrator for finished floor elevation requirements.",
            ]
        else:
            fe_lines = [
                "No Base Flood Elevation (BFE) required — Zone X (minimal hazard).",
                "Confirm finished floor elevation with surveyor and local jurisdiction.",
            ]
        result["flood_elevation"] = "\n".join(fe_lines)

        # ── natural_cultural ──────────────────────────────────────────
        result["natural_cultural"] = (
            "No NRA (Natural Resource Assessment) designation identified from available GIS data. "
            "An NRA study may be required by the jurisdiction if the site contains sensitive plant communities, "
            "listed species habitat, or is proximate to wetlands.\n"
            "Historic/cultural resource review recommended. Contact FDOS Division of Historical Resources "
            "(SHPO) and local Historic Preservation Officer if site or improvements are >50 years old."
        )

        # ── env_considerations ────────────────────────────────────────
        env_notes = []
        if is_coastal or near_cccl:
            env_notes.append(
                "Site is within or near the Coastal Construction Control Line (CCCL). "
                "FDEP CCCL permit or exemption required for construction activity seaward of the line."
            )
        if is_sfha:
            env_notes.append(
                "Site is within a FEMA Special Flood Hazard Area. "
                "Substantial improvement rules apply (50% rule). No net fill in floodway."
            )
        if not env_notes:
            env_notes.append(
                "No significant environmental constraints identified from available GIS data."
            )
        env_notes.append(
            "Phase I Environmental Site Assessment (ESA) recommended prior to acquisition."
        )
        result["env_considerations"] = "\n".join(env_notes)

        # ── geotechnical ──────────────────────────────────────────────
        geo_lines = [
            "Geotechnical investigation required prior to design.",
            "Pinellas County is within Florida karst terrain — sinkhole risk assessment (ASTM D6429) recommended.",
        ]
        if is_sfha:
            geo_lines.append(
                "Flood zone designation may affect foundation design — elevated footings or pilings may be required."
            )
        if is_coastal:
            geo_lines.append(
                "Coastal zone: Deep foundations (pilings) typically required. Consult licensed geotechnical engineer."
            )
        result["geotechnical"] = "\n".join(geo_lines)

        # ── building_code ─────────────────────────────────────────────
        result["building_code"] = "Florida Building Code, 8th Edition (2023)"

        # ── construction_methods ──────────────────────────────────────
        cm_lines = []
        if is_coastal:
            cm_lines.append(
                "Coastal High Hazard Area (CHHA) — Zone VE. Breakaway walls required below BFE. "
                "No fill under the building footprint. Deep foundation (pilings) required."
            )
        elif is_sfha:
            cm_lines.append(
                "Flood Zone " + fld_zone + ": Flood-resistant construction required per FBC and ASCE 24. "
                "Lowest floor must be at or above BFE + 1 ft freeboard."
            )
        if near_cccl:
            cm_lines.append(
                "Coastal Construction Control Line (CCCL) in proximity — FDEP permit required for "
                "construction activity seaward of the CCCL."
            )
        cm_lines.append(
            "Florida karst terrain: Sinkhole-resistant foundation design may be warranted "
            "depending on geotechnical findings. Compaction grouting or deep foundations may be required."
        )
        result["construction_methods"] = "\n".join(cm_lines)

        # ── fire_route ────────────────────────────────────────────────
        result["fire_route"] = "Verify fire access with local fire marshal. Minimum 20-ft clear fire lane required per FBC."

        return result

    def lookup(
        self,
        address: str,
        city: str,
        zip_code: str,
        county: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not lat or not lon:
            lat, lon = self._geocode(address, city, zip_code)

        if not lat or not lon:
            return {"error": "Could not geocode the address."}

        flood = self._get_flood_zone(lat, lon)
        near_cccl = self._near_cccl(lat, lon)

        result = self._build_fields(flood, near_cccl)
        result["_flood_zone"] = flood.get("FLD_ZONE", "")  # for display in notify
        return result
