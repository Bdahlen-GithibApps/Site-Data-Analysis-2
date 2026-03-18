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
                    return max(row["accessible_required"], math.ceil(total_spaces * 0.02))
                return row["accessible_required"]
        # Over 1000 spaces: 2% rule (ceiling)
        return math.ceil(total_spaces * 0.02)

    # ──────────────────────────────────────────────────────────────────
    # Bicycle parking (Sec. 138-3603)
    # ──────────────────────────────────────────────────────────────────

    def get_bicycle_spaces(self, county: str, motor_vehicle_spaces: int) -> int:
        """Calculate required bicycle spaces. Logic extracted from BICYCLE_PARKING lambda."""
        data = self._load(county)
        bp = data.get("bicycle_parking", {})
        min_spaces = bp.get("min_spaces", 2)
        per_mv = bp.get("spaces_per_motor_vehicle", 20)
        return max(min_spaces, motor_vehicle_spaces // per_mv)

    # ──────────────────────────────────────────────────────────────────
    # Parking rate lookup
    # ──────────────────────────────────────────────────────────────────

    def get_parking_rate(self, county: str, use_type: str) -> Optional[Dict[str, Any]]:
        """Return parking rate dict for a use type."""
        data = self._load(county)
        return data.get("parking_requirements", {}).get(use_type)

    def get_use_type_options(self, county: str) -> Dict[str, str]:
        """Return {use_type: use_type} dict for UI dropdowns."""
        data = self._load(county)
        return {k: k for k in data.get("parking_requirements", {}).keys()}

    def get_dimensions(self, county: str) -> Dict[str, Any]:
        """Return parking stall dimensions table."""
        data = self._load(county)
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
    ) -> Dict[str, Any]:
        """
        Calculate parking requirements for a use type.

        Returns:
            use_type, rate_description, required_spaces, max_spaces,
            ada_spaces, bicycle_spaces, dimensions, error (if any)
        """
        rate = self.get_parking_rate(county, use_type)
        if not rate:
            return {"error": f"Use type '{use_type}' not found in parking tables for {county}."}

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
        bicycle_spaces = self.get_bicycle_spaces(county, calc_spaces) if calc_spaces > 0 else 0

        return {
            "use_type": use_type,
            "rate_description": rate.get("min_rate", ""),
            "max_limit_description": rate.get("max_limit"),
            "unit": unit,
            "required_spaces": calc_spaces,
            "max_spaces": max_spaces,
            "ada_spaces": ada_spaces,
            "bicycle_spaces": bicycle_spaces,
            "dimensions": self.get_dimensions(county),
            "building_sf": building_sf,
            "num_units": num_units,
        }
