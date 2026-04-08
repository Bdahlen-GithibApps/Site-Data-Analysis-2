"""
Parking Agent — loads parking data and calculates required spaces.
"""
from __future__ import annotations

import json
import math
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DATA_ROOT = Path(__file__).parent.parent / "data"


class ParkingAgent:
    """
    Loads county-specific parking data from JSON and provides calculation
    methods for motor-vehicle spaces, ADA spaces, and bicycle spaces.
    """

    def __init__(self, county: str = "Pinellas") -> None:
        self._county = county
        data_dir = _DATA_ROOT / county.lower()
        raw = self._load(data_dir / "parking.json")
        self._requirements: dict = raw.get("requirements", {})
        self._ada_table: list = raw.get("ada_table", [])
        self._dimensions: dict = raw.get("dimensions", {})
        self._bicycle: dict = raw.get("bicycle", {})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load(path: Path) -> dict:
        try:
            with open(path) as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("Data file not found: %s", path)
            return {}
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse %s: %s", path, exc)
            return {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def use_types(self) -> list[str]:
        """Sorted list of use types available in the parking table."""
        return list(self._requirements.keys())

    @property
    def dimensions(self) -> dict:
        """Parking stall dimension configurations."""
        return self._dimensions

    def get_parking_rate(self, use_type: str) -> Optional[dict]:
        """Return the parking rate record for *use_type*, or ``None``."""
        return self._requirements.get(use_type)

    def calculate_spaces(
        self,
        use_type: str,
        building_sf: float = 0.0,
        num_units: int = 0,
    ) -> Optional[int]:
        """
        Calculate the minimum required motor-vehicle spaces.

        Parameters
        ----------
        use_type:
            Key from the parking requirements table.
        building_sf:
            Gross floor area in square feet (used for sf-based rates).
        num_units:
            Number of dwelling units, seats, beds, etc.

        Returns
        -------
        int or None
            Calculated spaces, or ``None`` if data is insufficient.
        """
        rate = self.get_parking_rate(use_type)
        if not rate:
            return None

        unit = rate.get("unit", "")
        min_per_unit = rate.get("min_per_unit")

        if min_per_unit is None:
            return None

        if unit == "1,000 sf GFA":
            if building_sf <= 0:
                return None
            return math.ceil(min_per_unit * (building_sf / 1000))
        elif unit == "dwelling unit":
            if num_units <= 0:
                return None
            return math.ceil(min_per_unit * num_units)
        else:
            if num_units <= 0:
                return None
            return math.ceil(min_per_unit * num_units)

    def get_max_spaces(
        self,
        use_type: str,
        building_sf: float = 0.0,
    ) -> Optional[int]:
        """Return the maximum allowed spaces for sf-based uses, or ``None``."""
        rate = self.get_parking_rate(use_type)
        if not rate or not rate.get("max_limit"):
            return None
        try:
            max_rate = float(str(rate["max_limit"]).split(" ")[0])
            return math.ceil(max_rate * (building_sf / 1000))
        except (ValueError, IndexError):
            return None

    def get_ada_spaces(self, total_spaces: int) -> int:
        """Calculate required ADA accessible spaces from total parking count."""
        for row in self._ada_table:
            if row["total_spaces_min"] <= total_spaces <= row["total_spaces_max"]:
                if "note" in row and "%" in row.get("note", ""):
                    return max(row["accessible_required"], int(total_spaces * 0.02))
                return row["accessible_required"]
        # Over 1000
        return int(total_spaces * 0.02)

    def get_bicycle_spaces(self, motor_vehicle_spaces: int) -> int:
        """
        Calculate required bicycle spaces.

        Rule: 1 bicycle space per ``spaces_per_mv_spaces`` motor-vehicle spaces,
        minimum ``min_spaces``.
        """
        min_spaces = self._bicycle.get("min_spaces", 2)
        ratio = self._bicycle.get("spaces_per_mv_spaces", 20)
        return max(min_spaces, motor_vehicle_spaces // ratio)
