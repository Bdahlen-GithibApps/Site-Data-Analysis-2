"""
Orchestrator Agent — coordinates sub-agents for a full parcel analysis.

Routes a query dict to PropertyAgent, ZoningAgent, ParkingAgent, and
LandscapeAgent, then consolidates and returns the results.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from agents.property_agent import PropertyAgent
from agents.zoning_agent import ZoningAgent
from agents.parking_agent import ParkingAgent
from agents.landscape_agent import LandscapeAgent

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """
    Top-level agent that wires together all domain sub-agents.

    Usage::

        orch = OrchestratorAgent(county="Pinellas")
        result = orch.run({
            "parcel_id": "19-31-17-73166-001-0010",
            "county": "Pinellas",
            "zoning": "C-2",
            "future_land_use": "CG",
            "use_type": "Retail (General)",
            "building_sf": 15000,
            "num_units": 0,
        })
    """

    def __init__(self, county: str = "Pinellas") -> None:
        self._county = county
        self._property_agent = PropertyAgent()
        self._zoning_agent = ZoningAgent(county)
        self._parking_agent = ParkingAgent(county)
        self._landscape_agent = LandscapeAgent(county)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a full parcel analysis and return consolidated results.

        Parameters
        ----------
        query:
            Dict with any combination of:
            - ``parcel_id`` (str)
            - ``county`` (str, defaults to agent county)
            - ``zoning`` (str)
            - ``future_land_use`` (str)
            - ``use_type`` (str)
            - ``building_sf`` (float)
            - ``num_units`` (int)

        Returns
        -------
        dict with keys:
            ``property``, ``zoning``, ``flum``, ``parking``, ``landscape``
        """
        results: Dict[str, Any] = {}
        county = query.get("county", self._county)

        # Property lookup
        parcel_id = query.get("parcel_id", "")
        if parcel_id:
            results["property"] = self._property_agent.lookup(parcel_id, county)
        else:
            results["property"] = None

        # Zoning standards
        zoning_code = query.get("zoning", "")
        if zoning_code:
            results["zoning"] = self._zoning_agent.get_zoning_standards(zoning_code)
        else:
            results["zoning"] = None

        # FLUM standards
        flum_code = query.get("future_land_use", "")
        if flum_code:
            results["flum"] = self._zoning_agent.get_flum_standards(flum_code)
            if zoning_code and results["flum"]:
                results["zoning_flum_compatible"] = self._zoning_agent.check_compatibility(
                    zoning_code, flum_code
                )
        else:
            results["flum"] = None

        # Parking
        use_type = query.get("use_type", "")
        if use_type:
            building_sf = float(query.get("building_sf") or 0)
            num_units = int(query.get("num_units") or 0)
            spaces = self._parking_agent.calculate_spaces(use_type, building_sf, num_units)
            results["parking"] = {
                "use_type": use_type,
                "rate": self._parking_agent.get_parking_rate(use_type),
                "required_spaces": spaces,
                "max_spaces": (
                    self._parking_agent.get_max_spaces(use_type, building_sf)
                    if building_sf > 0 else None
                ),
                "ada_spaces": self._parking_agent.get_ada_spaces(spaces) if spaces else 0,
                "bicycle_spaces": (
                    self._parking_agent.get_bicycle_spaces(spaces) if spaces else 0
                ),
                "dimensions": self._parking_agent.dimensions,
            }
        else:
            results["parking"] = None

        # Landscape (summary data, not parcel-specific)
        results["landscape"] = {
            "tree_requirements": self._landscape_agent.get_tree_requirements(),
            "parking_lot": self._landscape_agent.get_parking_lot_requirements(),
            "irrigation": self._landscape_agent.get_irrigation_requirements(),
        }

        return results

    # ------------------------------------------------------------------
    # Convenience accessors (used by UI layer without a full run())
    # ------------------------------------------------------------------

    @property
    def zoning_agent(self) -> ZoningAgent:
        return self._zoning_agent

    @property
    def parking_agent(self) -> ParkingAgent:
        return self._parking_agent

    @property
    def landscape_agent(self) -> LandscapeAgent:
        return self._landscape_agent

    @property
    def property_agent(self) -> PropertyAgent:
        return self._property_agent
