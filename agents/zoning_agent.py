"""
agents/zoning_agent.py — Zoning & FLUM code lookup agent.

Loads city- or county-specific zoning/FLUM data from JSON files under data/<city_slug>/
or data/<county>/. City-level data takes priority over county-level data.
Optionally queries ArcGIS REST services to auto-detect codes from coordinates.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.arcgis_client import ArcGISClient

logger = logging.getLogger(__name__)

# Map normalized city names to their data folder slug.
# Add entries here as city-specific data files are created.
_CITY_SLUG_MAP: Dict[str, str] = {
    "st. petersburg": "st_petersburg",
    "st petersburg": "st_petersburg",
    "saint petersburg": "st_petersburg",
}


def _city_slug(city: str) -> Optional[str]:
    """Return the data folder slug for a city, or None if no city-specific data exists."""
    if not city:
        return None
    return _CITY_SLUG_MAP.get(city.strip().lower())


class ZoningAgent:
    """
    Provides dimensional standards (setbacks, height, lot size) for zoning
    districts and density/intensity limits for FLUM categories.

    Lookup priority: city-specific data file → county data file.
    """

    def __init__(self):
        self.arcgis = ArcGISClient()
        self._cache: Dict[str, Dict] = {}

    # ──────────────────────────────────────────────────────────────────
    # Data loading
    # ──────────────────────────────────────────────────────────────────

    def _load(self, county: str, dataset: str, city: str = "") -> Dict:
        """Load dataset, checking city-specific folder first, then county folder."""
        slug = _city_slug(city)
        if slug:
            key = f"{slug}/{dataset}"
            if key not in self._cache:
                path = Path(__file__).parent.parent / "data" / slug / f"{dataset}.json"
                if path.exists():
                    with path.open() as f:
                        self._cache[key] = json.load(f)
                    return self._cache[key]
                # No city file — fall through to county
            else:
                return self._cache[key]

        key = f"{county}/{dataset}"
        if key not in self._cache:
            path = Path(__file__).parent.parent / "data" / county.lower() / f"{dataset}.json"
            if path.exists():
                with path.open() as f:
                    self._cache[key] = json.load(f)
            else:
                logger.warning("Data file not found: %s", path)
                self._cache[key] = {}
        return self._cache[key]

    def get_jurisdiction_name(self, county: str, city: str = "") -> str:
        """Return a human-readable jurisdiction label for use in code references."""
        slug = _city_slug(city)
        if slug:
            return city.strip().title()
        return f"Unincorporated {county.strip().title()} County"

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    def get_zoning_standards(self, county: str, zoning_code: str, city: str = "") -> Optional[Dict[str, Any]]:
        """Return dimensional standards for a zoning district code."""
        data = self._load(county, "zoning", city)
        key = zoning_code.upper().strip()
        result = data.get(key)
        if result is None:
            # Fallback: match by name (case-insensitive)
            for code, d in data.items():
                if code.startswith("_"):
                    continue
                if d.get("name", "").upper() == key:
                    return d
        return result

    def get_flum_standards(self, county: str, flum_code: str, city: str = "") -> Optional[Dict[str, Any]]:
        """Return density/intensity standards for a FLUM category code."""
        data = self._load(county, "flum", city)
        key = flum_code.upper().strip()
        result = data.get(key)
        if result is None:
            for code, d in data.items():
                if code.startswith("_"):
                    continue
                if d.get("name", "").upper() == key:
                    return d
        return result

    def get_zoning_options(self, county: str, city: str = "") -> Dict[str, str]:
        """Return {code: label} dict of all zoning districts for a county/city."""
        data = self._load(county, "zoning", city)
        return {code: f"{code} — {d.get('name', '')}" for code, d in data.items() if not code.startswith("_")}

    def get_flum_options(self, county: str, city: str = "") -> Dict[str, str]:
        """Return {code: label} dict of all FLUM categories for a county/city."""
        data = self._load(county, "flum", city)
        return {code: f"{code} — {d.get('name', '')}" for code, d in data.items() if not code.startswith("_")}

    def check_compatibility(
        self, county: str, zoning_code: str, flum_code: str, city: str = ""
    ) -> Dict[str, Any]:
        """
        Check whether a zoning district is compatible with a FLUM category.

        Returns:
            compatible (bool), zoning_code, flum_code, compatible_zoning (list),
            message (str)
        """
        flum = self.get_flum_standards(county, flum_code, city)
        if not flum:
            return {
                "compatible": None,
                "message": f"FLU category '{flum_code}' not found in data.",
            }
        compatible_zoning: List[str] = flum.get("compatible_zoning", [])
        is_compatible = zoning_code.upper().strip() in compatible_zoning
        return {
            "compatible": is_compatible,
            "zoning_code": zoning_code,
            "flum_code": flum_code,
            "compatible_zoning": compatible_zoning,
            "message": (
                f"Zoning {zoning_code} is consistent with FLU {flum_code}."
                if is_compatible
                else f"Zoning {zoning_code} may not be consistent with FLU {flum_code}. "
                     f"Compatible: {', '.join(compatible_zoning)}"
            ),
        }

    def get_requirements(
        self,
        county: str,
        parcel_id: str = "",
        zoning_code: str = "",
        flum_code: str = "",
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Return combined zoning + FLUM requirements.

        If lat/lon are provided and zoning_code/flum_code are not supplied,
        attempts an ArcGIS spatial query to auto-detect codes.
        """
        detected_zoning = zoning_code
        detected_flum = flum_code

        # Try ArcGIS auto-detection if coordinates available and codes not provided
        if lat is not None and lon is not None:
            if not detected_zoning:
                detected_zoning = self.arcgis.query_zoning(county, lat, lon) or ""
            if not detected_flum:
                detected_flum = self.arcgis.query_flu(county, lat, lon) or ""

        result: Dict[str, Any] = {
            "county": county,
            "zoning_code": detected_zoning,
            "flum_code": detected_flum,
        }

        if detected_zoning:
            result["zoning_standards"] = self.get_zoning_standards(county, detected_zoning)
        if detected_flum:
            result["flum_standards"] = self.get_flum_standards(county, detected_flum)
        if detected_zoning and detected_flum:
            result["compatibility"] = self.check_compatibility(county, detected_zoning, detected_flum)

        return result
