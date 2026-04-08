"""
agents/orchestrator.py — OrchestratorAgent routes queries to specialized sub-agents.

Usage:
    orchestrator = OrchestratorAgent()
    results = orchestrator.process({
        "parcel_id": "19-31-17-73166-001-0010",
        "county": "Pinellas",
        "use_type": "Retail (General)",   # optional
        "building_sf": 15000,              # optional
        "num_units": 0,                    # optional
        "zoning_code": "C-2",              # optional, skips ArcGIS query
        "flum_code": "CG",                 # optional, skips ArcGIS query
    })
"""

from __future__ import annotations

from typing import Any, Dict

from agents.property_agent import PropertyAgent
from agents.zoning_agent import ZoningAgent
from agents.parking_agent import ParkingAgent
from agents.landscape_agent import LandscapeAgent


class OrchestratorAgent:
    """
    Coordinates all sub-agents to produce a consolidated site data report
    from a single query dict.
    """

    def __init__(self):
        self.property_agent = PropertyAgent()
        self.zoning_agent = ZoningAgent()
        self.parking_agent = ParkingAgent()
        self.landscape_agent = LandscapeAgent()

    def process(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point. Orchestrates lookup across all sub-agents.

        Required keys:
            parcel_id (str): County parcel identifier
            county (str): County name (e.g. 'Pinellas')

        Optional keys:
            use_type (str): Proposed use for parking calculation
            building_sf (float): Gross floor area in sq ft
            num_units (int): Number of dwelling units / seats / beds
            zoning_code (str): Override zoning (skips ArcGIS lookup)
            flum_code (str): Override FLUM code (skips ArcGIS lookup)
            adjacency_scenario (str): Buffer adjacency key for landscape

        Returns:
            Dict with keys: property, zoning, parking (if use_type given), landscape
        """
        results: Dict[str, Any] = {}

        parcel_id = query.get("parcel_id", "")
        county = query.get("county", "Pinellas")

        # Step 1: Property lookup
        prop = self.property_agent.lookup(parcel_id, county)
        results["property"] = prop

        # Step 2: Zoning + FLUM requirements
        zoning_code = query.get("zoning_code", "")
        flum_code = query.get("flum_code", "")
        zoning = self.zoning_agent.get_requirements(
            county=county,
            parcel_id=parcel_id,
            zoning_code=zoning_code,
            flum_code=flum_code,
        )
        results["zoning"] = zoning

        # Step 3: Parking calculation (only if use_type provided)
        use_type = query.get("use_type", "")
        if use_type:
            parking = self.parking_agent.calculate(
                county=county,
                use_type=use_type,
                building_sf=float(query.get("building_sf") or 0),
                num_units=int(query.get("num_units") or 0),
            )
            results["parking"] = parking

        # Step 4: Landscape requirements
        landscape = self.landscape_agent.get_requirements(
            county=county,
            zoning_code=zoning_code,
            site_area_sf=None,
            adjacency_scenario=query.get("adjacency_scenario"),
        )
        results["landscape"] = landscape

        return results
