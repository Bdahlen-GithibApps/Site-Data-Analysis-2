"""
agents/landscape_agent.py — Landscape buffer, tree canopy, and irrigation requirements agent.

Loads county-specific landscape code data from data/<county>/landscape.json.
Based on Pinellas County Ch. 138, Art. IV — Landscaping & Tree Protection.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from agents import city_slug as _city_slug

logger = logging.getLogger(__name__)


class LandscapeAgent:
    """
    Returns landscape requirements including:
    - Perimeter buffer types (A/B/C) based on zoning adjacency
    - Parking lot landscaping standards
    - Tree canopy coverage requirements
    - Irrigation requirements
    - Sight triangle standards
    - Plant material standards
    """

    def __init__(self):
        self._cache: Dict[str, Dict] = {}

    # ──────────────────────────────────────────────────────────────────
    # Data loading
    # ──────────────────────────────────────────────────────────────────

    def _load(self, county: str, city: str = "") -> Dict:
        slug = _city_slug(city)
        if slug:
            if slug not in self._cache:
                path = Path(__file__).parent.parent / "data" / slug / "landscape.json"
                if path.exists():
                    with path.open() as f:
                        self._cache[slug] = json.load(f)
                else:
                    self._cache[slug] = {}
            if self._cache[slug]:
                return self._cache[slug]
        # Fall back to county
        if county not in self._cache:
            path = Path(__file__).parent.parent / "data" / county.lower() / "landscape.json"
            if path.exists():
                with path.open() as f:
                    self._cache[county] = json.load(f)
            else:
                logger.warning("Landscape data file not found for county: %s", county)
                self._cache[county] = {}
        return self._cache[county]

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    def get_buffer_type(self, county: str, adjacency_key: str, city: str = "") -> Optional[Dict[str, Any]]:
        """
        Return the buffer type definition for a given adjacency scenario.

        adjacency_key examples:
            'residential_adjacent_to_commercial_or_industrial'
            'commercial_adjacent_to_residential'
        """
        data = self._load(county, city)
        buffers = data.get("perimeter_buffers", {})
        adjacency = buffers.get("adjacency_matrix", {})
        buffer_types = buffers.get("buffer_types", {})

        type_key = adjacency.get(adjacency_key) or adjacency.get("default", "type_A")
        return buffer_types.get(type_key)

    def get_parking_lot_requirements(self, county: str, city: str = "") -> Dict[str, Any]:
        """Return parking lot landscaping standards."""
        data = self._load(county, city)
        return data.get("parking_lot_landscaping", {})

    def get_tree_canopy_requirements(self, county: str, use_category: str = "commercial", city: str = "") -> Dict[str, Any]:
        """
        Return tree canopy requirements for a use category.

        use_category: 'residential', 'commercial', or 'industrial'
        """
        data = self._load(county, city)
        canopy = data.get("tree_canopy", {})
        return canopy.get(use_category, canopy.get("commercial", {}))

    def get_requirements(
        self,
        county: str,
        zoning_code: Optional[str] = None,
        site_area_sf: Optional[float] = None,
        adjacency_scenario: Optional[str] = None,
        use_category: str = "commercial",
        city: str = "",
    ) -> Dict[str, Any]:
        """
        Return full landscape requirements for a site.

        Args:
            county: County name (e.g. 'Pinellas')
            zoning_code: Optional zoning district code for context
            site_area_sf: Optional site area in square feet for calculations
            adjacency_scenario: Optional adjacency key for buffer lookup
            use_category: 'residential', 'commercial', or 'industrial'
            city: Optional city name for city-specific data

        Returns:
            Dict with available, county, buffer_types, parking_lot,
            tree_canopy, irrigation, sight_triangles, plant_materials
        """
        data = self._load(county, city)
        if not data:
            jurisdiction = city or f"{county} County"
            return {
                "available": False,
                "message": f"Landscape code data not yet available for {jurisdiction}.",
            }

        result: Dict[str, Any] = {
            "available": True,
            "county": county,
            "code_reference": data.get("code_reference", ""),
        }

        # Perimeter buffers — all buffer type definitions
        buffers = data.get("perimeter_buffers", {})
        result["buffer_types"] = buffers.get("buffer_types", {})
        result["adjacency_matrix"] = buffers.get("adjacency_matrix", {})

        # Specific buffer for adjacency scenario
        if adjacency_scenario:
            result["applicable_buffer"] = self.get_buffer_type(county, adjacency_scenario, city=city)

        # Parking lot landscaping
        result["parking_lot"] = data.get("parking_lot_landscaping", {})

        # Tree canopy
        result["tree_canopy"] = self.get_tree_canopy_requirements(county, use_category, city=city)
        result["tree_canopy_heritage"] = data.get("tree_canopy", {}).get("heritage_trees", {})
        result["tree_canopy_specimen"] = data.get("tree_canopy", {}).get("specimen_trees", {})

        # Irrigation
        result["irrigation"] = data.get("irrigation", {})

        # Sight triangles
        result["sight_triangles"] = data.get("sight_triangles", {})

        # Plant material standards
        result["plant_materials"] = data.get("plant_materials", {})

        return result
