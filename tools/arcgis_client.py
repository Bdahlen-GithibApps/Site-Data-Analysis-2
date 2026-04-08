"""
ArcGIS REST API client for spatial zoning and Future Land Use queries.

Provides point-based lookups against county ArcGIS feature services to
automatically detect zoning and FLU designations from latitude/longitude.
"""
from __future__ import annotations

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# County → ArcGIS endpoint mapping
# ---------------------------------------------------------------------------
# Each entry maps a county name to its relevant feature service layers.
# Layers listed under "zoning" return the zoning district code/name.
# Layers listed under "flu" return the Future Land Use designation.
ARCGIS_ENDPOINTS: dict[str, dict] = {
    "Pinellas": {
        "zoning": {
            "url": (
                "https://pinellas-egis.maps.arcgis.com/arcgis/rest/services/"
                "Zoning/MapServer/0/query"
            ),
            "code_field": "ZONING",
            "name_field": "ZONENAME",
        },
        "flu": {
            "url": (
                "https://pinellas-egis.maps.arcgis.com/arcgis/rest/services/"
                "FutureLandUse/MapServer/0/query"
            ),
            "code_field": "FLUCCS",
            "name_field": "FLUCCSNAME",
        },
    },
    "Hillsborough": {
        "zoning": {
            "url": (
                "https://gis.hcpafl.org/arcgis/rest/services/"
                "Parcels/ZoningLayers/MapServer/0/query"
            ),
            "code_field": "ZONING",
            "name_field": "ZONING_DESC",
        },
        "flu": {
            "url": (
                "https://gis.hcpafl.org/arcgis/rest/services/"
                "Parcels/FutureLandUse/MapServer/0/query"
            ),
            "code_field": "FLU",
            "name_field": "FLU_DESC",
        },
    },
    "Pasco": {
        "zoning": {
            "url": (
                "https://gis.pascocountyfl.net/arcgis/rest/services/"
                "PascoGIS/Zoning/MapServer/0/query"
            ),
            "code_field": "ZONING",
            "name_field": "DESCRIPTION",
        },
        "flu": {
            "url": (
                "https://gis.pascocountyfl.net/arcgis/rest/services/"
                "PascoGIS/FutureLandUse/MapServer/0/query"
            ),
            "code_field": "FLU",
            "name_field": "DESCRIPTION",
        },
    },
}


class ArcGISClient:
    """Client for querying ArcGIS REST feature service endpoints."""

    def __init__(self, timeout: int = 10) -> None:
        self._timeout = timeout
        self._session = requests.Session()

    def _query_point(
        self,
        service_url: str,
        lat: float,
        lon: float,
        out_fields: str = "*",
    ) -> Optional[dict]:
        """
        Execute an ``esriGeometryPoint`` spatial query against *service_url*.

        Returns the first feature's attributes dict, or ``None`` on failure.
        """
        params = {
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": out_fields,
            "returnGeometry": "false",
            "f": "json",
        }
        try:
            resp = self._session.get(service_url, params=params, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
            features = data.get("features", [])
            if features:
                return features[0].get("attributes", {})
        except Exception as exc:
            logger.debug("ArcGIS query failed for %s: %s", service_url, exc)
        return None

    def query_zoning(self, county: str, lat: float, lon: float) -> Optional[dict]:
        """
        Return ``{"code": ..., "name": ...}`` for the zoning district at *lat/lon*,
        or ``None`` if the county is unsupported or the query fails.
        """
        county_cfg = ARCGIS_ENDPOINTS.get(county, {})
        layer = county_cfg.get("zoning")
        if not layer:
            logger.debug("No ArcGIS zoning endpoint configured for county '%s'", county)
            return None

        attrs = self._query_point(layer["url"], lat, lon)
        if attrs is None:
            return None

        return {
            "code": attrs.get(layer["code_field"], ""),
            "name": attrs.get(layer["name_field"], ""),
        }

    def query_flu(self, county: str, lat: float, lon: float) -> Optional[dict]:
        """
        Return ``{"code": ..., "name": ...}`` for the Future Land Use category at
        *lat/lon*, or ``None`` if unsupported or query fails.
        """
        county_cfg = ARCGIS_ENDPOINTS.get(county, {})
        layer = county_cfg.get("flu")
        if not layer:
            logger.debug("No ArcGIS FLU endpoint configured for county '%s'", county)
            return None

        attrs = self._query_point(layer["url"], lat, lon)
        if attrs is None:
            return None

        return {
            "code": attrs.get(layer["code_field"], ""),
            "name": attrs.get(layer["name_field"], ""),
        }
