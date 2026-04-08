"""
Property Agent — handles parcel lookup across multiple counties.

Uses a strategy pattern: each county has its own scraper function.
All scrapers return the same standardised dict format.
"""
from __future__ import annotations

import logging
from typing import Dict, Any

from tools.scraper import scrape_pinellas_property

logger = logging.getLogger(__name__)

# Standardised return dict shape (all keys always present):
#   success: bool
#   parcel_id: str
#   address: str
#   city: str
#   zip: str
#   owner: str
#   land_use: str
#   site_area_sqft: str  (formatted, e.g. "12,345")
#   site_area_acres: str (formatted, e.g. "0.28")
#   legal_description: str
#   strap: str
#   tax_district: str
#   error: str  (only present when success=False)


def _not_implemented(parcel_id: str, county: str) -> Dict[str, Any]:
    return {
        "success": False,
        "error": f"Property lookup is not yet implemented for {county} County.",
    }


class PropertyAgent:
    """Routes parcel lookup requests to the appropriate county scraper."""

    _COUNTY_STRATEGIES: dict[str, Any] = {
        "Pinellas": scrape_pinellas_property,
    }

    def lookup(self, parcel_id: str, county: str) -> Dict[str, Any]:
        """
        Look up a parcel and return a standardised result dict.

        Parameters
        ----------
        parcel_id:
            Raw parcel identifier string (formatting normalised per county).
        county:
            Display name of the county, e.g. ``"Pinellas"``.

        Returns
        -------
        dict
            Standardised result; see module docstring for shape.
        """
        strategy = self._COUNTY_STRATEGIES.get(county)
        if strategy is None:
            logger.info("No strategy for county '%s'", county)
            return _not_implemented(parcel_id, county)
        try:
            return strategy(parcel_id)
        except Exception as exc:
            logger.exception("Property lookup failed for %s / %s", county, parcel_id)
            return {"success": False, "error": str(exc)}
