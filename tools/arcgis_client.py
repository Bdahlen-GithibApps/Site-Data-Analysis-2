"""
tools/arcgis_client.py — ArcGIS REST API client for spatial zoning/FLU queries.

Queries county-published ArcGIS Feature Services to auto-detect zoning and
Future Land Use designation from a lat/lon coordinate (parcel centroid).

Usage:
    client = ArcGISClient()
    zoning_code = client.query_zoning("Pinellas", lat=27.9, lon=-82.7)
    flu_code = client.query_flu("Pinellas", lat=27.9, lon=-82.7)
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# County → ArcGIS REST endpoint mapping
# Field names are the attribute field that holds the zoning/FLU code.
# Update these URLs as counties publish or change their GIS services.
# ──────────────────────────────────────────────────────────────────────
ARCGIS_SERVICES: Dict[str, Dict[str, Dict[str, str]]] = {
    "Pinellas": {
        "zoning": {
            "url": "https://egis.pinellascounty.org/arcgis/rest/services/Planning/Zoning/MapServer/0",
            "field": "ZONING",
        },
        "flu": {
            "url": "https://egis.pinellascounty.org/arcgis/rest/services/Planning/FutureLandUse/MapServer/0",
            "field": "FLU_CODE",
        },
    },
    "Hillsborough": {
        "zoning": {
            "url": "https://maps.hillsboroughcounty.org/arcgis/rest/services/Zoning/MapServer/0",
            "field": "ZONING_DIST",
        },
        "flu": {
            "url": "https://maps.hillsboroughcounty.org/arcgis/rest/services/FLU/MapServer/0",
            "field": "FLU_CATEGORY",
        },
    },
    "Pasco": {
        "zoning": {
            "url": "https://gis.pascocountyfl.net/arcgis/rest/services/Zoning/MapServer/0",
            "field": "ZONE_CODE",
        },
        "flu": {
            "url": "https://gis.pascocountyfl.net/arcgis/rest/services/FLU/MapServer/0",
            "field": "FLU_CODE",
        },
    },
}


class ArcGISClient:
    """Query ArcGIS REST Feature Services for zoning/FLU by point location."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self._session = requests.Session()

    def query_zoning(self, county: str, lat: float, lon: float) -> Optional[str]:
        """Return zoning code for the given lat/lon in the specified county."""
        return self._spatial_query(county, "zoning", lat, lon)

    def query_flu(self, county: str, lat: float, lon: float) -> Optional[str]:
        """Return FLU code for the given lat/lon in the specified county."""
        return self._spatial_query(county, "flu", lat, lon)

    def _spatial_query(
        self, county: str, layer_key: str, lat: float, lon: float
    ) -> Optional[str]:
        services = ARCGIS_SERVICES.get(county, {})
        layer = services.get(layer_key)
        if not layer:
            logger.debug("No ArcGIS endpoint configured for county=%s layer=%s", county, layer_key)
            return None

        url = layer["url"]
        field = layer["field"]
        params = {
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": field,
            "returnGeometry": "false",
            "f": "json",
        }

        try:
            resp = self._session.get(f"{url}/query", params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            features = data.get("features", [])
            if features:
                value = features[0].get("attributes", {}).get(field)
                return str(value).strip() if value is not None else None
        except Exception as exc:
            logger.warning("ArcGIS query failed for county=%s layer=%s: %s", county, layer_key, exc)
        return None
