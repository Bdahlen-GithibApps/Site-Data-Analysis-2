"""
agents/parking_agent.py — Parking requirements calculation agent.

Loads county-specific parking data from data/<county>/parking.json.
Calculates required motor vehicle spaces, ADA accessible spaces, and bicycle spaces.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_ADA_PERCENTAGE = 0.02  # 2% of total spaces for lots > 500


class ParkingAgent:
    """Calculates parking requirements for a given county, use type, and building size."""

    def __init__(self):
        self._cache: Dict[str, Dict] = {}

    # ──────────────────────────────────────────────────────────────────
    # Data loading
    # ──────────────────────────────────────────────────────────────────

    def _load(self, county: str) -> Dict:
        if county not in self._cache:
            path = Path(__file__).parent.parent / "data" / county.lower() / "parking.json"
            if path.exists():
                with path.open() as f:
                    self._cache[county] = json.load(f)
            else:
                logger.warning("Parking data file not found for county: %s", county)
                self._cache[county] = {}
        return self._cache[county]

    def _load_for_jurisdiction(self, county: str, city: str = "") -> tuple:
        """Try city-specific parking data first, fall back to county.

        Returns (data_dict, source_label) where source_label describes
        which jurisdiction the data came from.
        """
        if city:
            city_key = city.lower().replace(" ", "_").replace(".", "")
            if city_key not in self._cache:
                path = Path(__file__).parent.parent / "data" / city_key / "parking.json"
                if path.exists():
                    with path.open() as f:
                        self._cache[city_key] = json.load(f)
                else:
                    self._cache[city_key] = {}
            city_data = self._cache[city_key]
            if city_data:
                return city_data, city
        county_data = self._load(county)
        label = f"{county} County"
        if city:
            label += f" (city-specific data not available for {city})"
        return county_data, label

    def has_city_data(self, city: str) -> bool:
        """Check if city-specific parking data exists."""
        if not city:
            return False
        city_key = city.lower().replace(" ", "_").replace(".", "")
        path = Path(__file__).parent.parent / "data" / city_key / "parking.json"
        return path.exists()

    # ──────────────────────────────────────────────────────────────────
    # ADA calculation (per ADA / Florida Building Code)
    # ──────────────────────────────────────────────────────────────────

    def get_ada_spaces(self, county: str, total_spaces: int) -> int:
        """Calculate required ADA accessible spaces from total parking count."""
        data = self._load(county)
        ada_table = data.get("ada_parking_table", [])

        for row in ada_table:
            if row["total_spaces_min"] <= total_spaces <= row["total_spaces_max"]:
                if "note" in row and "%" in row["note"]:
                    return max(row["accessible_required"], math.ceil(total_spaces * _ADA_PERCENTAGE))
                return row["accessible_required"]
        # Over 1000 spaces: 2% rule (ceiling)
        return math.ceil(total_spaces * _ADA_PERCENTAGE)

    # ──────────────────────────────────────────────────────────────────
    # Bicycle parking (Sec. 138-3603)
    # ──────────────────────────────────────────────────────────────────

    def get_bicycle_spaces(self, county: str, motor_vehicle_spaces: int, use_type: str = "") -> int:
        """Calculate required bicycle spaces using per-use rate from parking table."""
        data = self._load(county)
        rate_info = data.get("parking_requirements", {}).get(use_type, {})
        bicycle_rate = rate_info.get("bicycle_rate", 0)
        if bicycle_rate and motor_vehicle_spaces > 0:
            return max(2, math.ceil(motor_vehicle_spaces * bicycle_rate))
        # Fallback: older data format
        bp = data.get("bicycle_parking", {})
        min_spaces = bp.get("min_spaces", 2)
        per_mv = bp.get("spaces_per_motor_vehicle", 20)
        if per_mv and motor_vehicle_spaces > 0:
            return max(min_spaces, motor_vehicle_spaces // per_mv)
        return 0

    # ──────────────────────────────────────────────────────────────────
    # Parking rate lookup
    # ──────────────────────────────────────────────────────────────────

    def get_parking_rate(self, county: str, use_type: str, city: str = "") -> Optional[Dict[str, Any]]:
        """Return parking rate dict for a use type."""
        data, _ = self._load_for_jurisdiction(county, city)
        return data.get("parking_requirements", {}).get(use_type)

    def get_use_type_options(self, county: str, city: str = "") -> Dict[str, str]:
        """Return {use_type: use_type} dict for UI dropdowns."""
        data, _ = self._load_for_jurisdiction(county, city)
        return {k: k for k in data.get("parking_requirements", {}).keys()}

    def get_dimensions(self, county: str, city: str = "") -> Dict[str, Any]:
        """Return parking stall dimensions table."""
        data, _ = self._load_for_jurisdiction(county, city)
        return data.get("parking_dimensions", {})

    # ──────────────────────────────────────────────────────────────────
    # Main calculation
    # ──────────────────────────────────────────────────────────────────

    def calculate(
        self,
        county: str,
        use_type: str,
        building_sf: float = 0.0,
        num_units: int = 0,
        city: str = "",
    ) -> Dict[str, Any]:
        """
        Calculate parking requirements for a use type.

        Returns:
            use_type, rate_description, required_spaces, max_spaces,
            ada_spaces, bicycle_spaces, dimensions, data_source, error (if any)
        """
        data, data_source = self._load_for_jurisdiction(county, city)
        reqs = data.get("parking_requirements", {})
        rate = reqs.get(use_type)
        if not rate:
            return {"error": f"Use type '{use_type}' not found in parking tables for {data_source}.",
                    "data_source": data_source}

        unit = rate.get("unit", "")
        min_per_unit = rate.get("min_per_unit")
        calc_spaces = 0
        max_spaces = None

        if unit == "1,000 sf GFA" and building_sf > 0 and min_per_unit is not None:
            calc_spaces = math.ceil(min_per_unit * (building_sf / 1000))
            if rate.get("max_limit"):
                try:
                    max_rate = float(rate["max_limit"].split(" ")[0])
                    max_spaces = math.ceil(max_rate * (building_sf / 1000))
                except (ValueError, IndexError):
                    pass
        elif unit == "dwelling unit" and num_units > 0 and min_per_unit is not None:
            calc_spaces = math.ceil(min_per_unit * num_units)
        elif num_units > 0 and min_per_unit is not None:
            calc_spaces = math.ceil(min_per_unit * num_units)

        ada_spaces = self.get_ada_spaces(county, calc_spaces) if calc_spaces > 0 else 0
        bicycle_spaces = self.get_bicycle_spaces(county, calc_spaces, use_type) if calc_spaces > 0 else 0

        # Code reference from data
        source_url = data.get("_url", "")
        source_section = data.get("_source", "")

        return {
            "use_type": use_type,
            "rate_description": rate.get("min_rate", ""),
            "max_limit_description": rate.get("max_limit"),
            "unit": unit,
            "required_spaces": calc_spaces,
            "max_spaces": max_spaces,
            "ada_spaces": ada_spaces,
            "bicycle_spaces": bicycle_spaces,
            "dimensions": data.get("parking_dimensions", {}),
            "building_sf": building_sf,
            "num_units": num_units,
            "data_source": data_source,
            "source_section": source_section,
            "source_url": source_url,
        }
