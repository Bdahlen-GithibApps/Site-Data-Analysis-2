"""
Landscape Agent — loads and exposes landscape code requirements for a county.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DATA_ROOT = Path(__file__).parent.parent / "data"


class LandscapeAgent:
    """
    Loads county-specific landscape data from JSON and provides query methods
    for perimeter buffers, parking lot landscaping, and tree requirements.
    """

    def __init__(self, county: str = "Pinellas") -> None:
        self._county = county
        data_dir = _DATA_ROOT / county.lower()
        self._data: dict = self._load(data_dir / "landscape.json")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load(path: Path) -> dict:
        try:
            with open(path) as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("Landscape data file not found: %s", path)
            return {}
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse %s: %s", path, exc)
            return {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_perimeter_buffer(self, adjacency_type: str) -> Optional[dict]:
        """
        Return buffer requirements for a given adjacency scenario.

        Parameters
        ----------
        adjacency_type:
            One of the keys in the ``perimeter_buffers`` section of the data,
            e.g. ``"nonresidential_to_residential"``.
        """
        buffers = self._data.get("perimeter_buffers", {})
        return buffers.get(adjacency_type)

    def get_parking_lot_requirements(self) -> dict:
        """Return interior parking lot landscaping requirements."""
        return self._data.get("parking_lot_landscaping", {})

    def get_tree_requirements(self) -> dict:
        """Return tree preservation and replacement requirements."""
        return self._data.get("tree_requirements", {})

    def get_irrigation_requirements(self) -> dict:
        """Return irrigation system requirements."""
        return self._data.get("irrigation", {})

    def get_stormwater_requirements(self) -> dict:
        """Return stormwater / littoral zone landscaping requirements."""
        return self._data.get("stormwater_landscaping", {})

    @property
    def all_data(self) -> dict:
        """Full raw landscape data dict."""
        return self._data
