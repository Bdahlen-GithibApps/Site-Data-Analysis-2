"""
Zoning Agent — loads and queries zoning district and FLUM data for a county.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DATA_ROOT = Path(__file__).parent.parent / "data"


class ZoningAgent:
    """
    Loads county-specific zoning and Future Land Use data from JSON files
    and exposes query methods used by the UI and OrchestratorAgent.
    """

    def __init__(self, county: str = "Pinellas") -> None:
        self._county = county
        data_dir = _DATA_ROOT / county.lower()
        self._zoning: dict = self._load(data_dir / "zoning.json")
        self._flum: dict = self._load(data_dir / "flum.json")

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
    def zoning_districts(self) -> dict:
        """All zoning district records keyed by district code."""
        return self._zoning

    @property
    def flum_categories(self) -> dict:
        """All FLUM category records keyed by category code."""
        return self._flum

    def get_zoning_standards(self, zoning_code: str) -> Optional[dict]:
        """Return dimensional standards for *zoning_code*, or ``None`` if not found."""
        return self._zoning.get(zoning_code.upper().strip())

    def get_flum_standards(self, flum_code: str) -> Optional[dict]:
        """Return density/intensity standards for *flum_code*, or ``None`` if not found."""
        return self._flum.get(flum_code.upper().strip())

    def check_compatibility(self, zoning_code: str, flum_code: str) -> Optional[bool]:
        """
        Return ``True`` if *zoning_code* is listed as compatible with *flum_code*,
        ``False`` if incompatible, or ``None`` if data is insufficient.
        """
        flu = self.get_flum_standards(flum_code)
        if flu is None:
            return None
        compatible = flu.get("compatible_zoning", [])
        if not compatible:
            return None
        return zoning_code.upper().strip() in compatible
