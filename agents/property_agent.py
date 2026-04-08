"""
agents/property_agent.py — Parcel data lookup agent with multi-county strategy pattern.

Supported counties:
  - Pinellas  → scrapes PCPAO (pcpao.gov)
  - Hillsborough → placeholder (not yet implemented)
  - Pasco       → placeholder (not yet implemented)
"""

from __future__ import annotations

from typing import Any, Dict

from tools.scraper import scrape_pinellas_property


class PropertyAgent:
    """Fetches parcel data from county property appraiser systems."""

    SUPPORTED_COUNTIES = {
        "Pinellas": "pcpao",
        "Hillsborough": "hcpafl",
        "Pasco": "pascopa",
    }

    def lookup(self, parcel_id: str, county: str) -> Dict[str, Any]:
        """
        Look up parcel data for a given parcel_id in the specified county.

        Returns a dict with at minimum:
            success (bool), error (str on failure), parcel_id, address, city, zip,
            owner, land_use, site_area_sqft, site_area_acres, legal_description, strap.
        """
        strategy = self.SUPPORTED_COUNTIES.get(county)

        if strategy == "pcpao":
            return scrape_pinellas_property(parcel_id)
        elif strategy == "hcpafl":
            return self._lookup_hillsborough(parcel_id)
        elif strategy == "pascopa":
            return self._lookup_pasco(parcel_id)
        else:
            return {
                "success": False,
                "error": f"County '{county}' is not yet supported. "
                         f"Supported counties: {', '.join(self.SUPPORTED_COUNTIES)}",
            }

    def _lookup_hillsborough(self, parcel_id: str) -> Dict[str, Any]:
        # TODO: Implement HCPA API scraping
        # https://gis.hcpafl.org/ has ArcGIS REST services
        return {
            "success": False,
            "error": "Hillsborough County lookup not yet implemented.",
        }

    def _lookup_pasco(self, parcel_id: str) -> Dict[str, Any]:
        # TODO: Implement Pasco PA lookup
        # https://www.pascopa.com/
        return {
            "success": False,
            "error": "Pasco County lookup not yet implemented.",
        }
