"""
agents/zoning_agent.py — Zoning & FLUM code lookup agent.

Loads county-specific zoning/FLUM data from JSON files under data/<county>/.
Optionally queries ArcGIS REST services to auto-detect codes from coordinates.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.arcgis_client import ArcGISClient

logger = logging.getLogger(__name__)


class ZoningAgent:
    """
    Provides dimensional standards (setbacks, height, lot size) for zoning
    districts and density/intensity limits for FLUM categories.
    """

    def __init__(self):
        self.arcgis = ArcGISClient()
        self._cache: Dict[str, Dict] = {}

    # ──────────────────────────────────────────────────────────────────
    # Data loading
    # ──────────────────────────────────────────────────────────────────

    def _load(self, county: str, dataset: str) -> Dict:
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

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    def get_zoning_standards(self, county: str, zoning_code: str) -> Optional[Dict[str, Any]]:
        """Return dimensional standards for a zoning district code."""
        data = self._load(county, "zoning")
        return data.get(zoning_code.upper().strip())

    def get_flum_standards(self, county: str, flum_code: str) -> Optional[Dict[str, Any]]:
        """Return density/intensity standards for a FLUM category code."""
        data = self._load(county, "flum")
        return data.get(flum_code.upper().strip())

    def get_zoning_options(self, county: str) -> Dict[str, str]:
        """Return {code: label} dict of all zoning districts for a county."""
        data = self._load(county, "zoning")
        return {code: f"{code} — {d.get('name', '')}" for code, d in data.items()}

    def get_flum_options(self, county: str) -> Dict[str, str]:
        """Return {code: label} dict of all FLUM categories for a county."""
        data = self._load(county, "flum")
        return {code: f"{code} — {d.get('name', '')}" for code, d in data.items()}

    def check_compatibility(
        self, county: str, zoning_code: str, flum_code: str
    ) -> Dict[str, Any]:
        """
        Check whether a zoning district is compatible with a FLUM category.

        Returns:
            compatible (bool), zoning_code, flum_code, compatible_zoning (list),
            message (str)
        """
        flum = self.get_flum_standards(county, flum_code)
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
