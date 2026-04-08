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

import json
import logging
import pathlib
from typing import Any, Dict, Optional

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


GEOCODE_URL = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"

_CITY_LOOKUP_PATH = pathlib.Path(__file__).parent.parent / "data" / "pinellas" / "cities.json"


def _load_city_lookup() -> dict:
    """Load the Pinellas city lookup JSON (cities.json)."""
    try:
        with open(_CITY_LOOKUP_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _get_city_meta(city_name: str, lookup: dict) -> Optional[dict]:
    """Return the metadata dict for a city from the lookup, or None."""
    if not city_name:
        return None
    key = city_name.strip().lower()
    if "unincorporated" in key:
        for data in lookup.values():
            if isinstance(data, dict) and data.get("type") == "county_service":
                return data
    meta = lookup.get(key)
    if not meta:
        for name_key, data in lookup.items():
            if isinstance(data, dict) and (name_key in key or key in name_key):
                return data
    return meta


class ArcGISClient:
    """Query ArcGIS REST Feature Services for zoning/FLU by point location."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self._session = requests.Session()

    def _geocode_single_line(self, single_line: str) -> Optional[tuple]:
        """Geocode a complete SingleLine address string. Returns (lat, lon) or None."""
        try:
            resp = self._session.get(
                GEOCODE_URL,
                params={"SingleLine": single_line, "maxLocations": 1, "f": "json"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            candidates = resp.json().get("candidates", [])
            if candidates and candidates[0].get("score", 0) >= 70:
                loc = candidates[0]["location"]
                return float(loc["y"]), float(loc["x"])  # lat, lon
        except Exception as exc:
            logger.warning("Geocode failed for '%s': %s", single_line, exc)
        return None

    def geocode_address(
        self, address: str, city: str = "", zip_code: str = ""
    ) -> Optional[tuple]:
        """
        Geocode a street address via the ArcGIS World Geocoder.

        Returns (lat, lon) on success, None on failure.
        Requires a score >= 70 to avoid low-confidence matches.
        """
        search = address.strip()
        if city:
            search = f"{search}, {city}, FL"
        if zip_code and zip_code not in search:
            search = f"{search} {zip_code}"
        return self._geocode_single_line(search)

    def lookup_city_zoning(self, city_name: str, address: str) -> Dict[str, Any]:
        """
        Programmatic zoning + FLU lookup using city-specific ArcGIS endpoints
        sourced from data/pinellas/cities.json.

        Returns one of:
          {"success": True, "zoning_code": ..., "future_land_use": ...,
           "zoning_description": ..., "future_land_use_description": ..., "jurisdiction": ...}
          {"success": False, "open_map": True, "map_url": ..., "error": ...}
          {"success": False, "error": ...}
        """
        if not address:
            return {"success": False, "error": "Address required for zoning lookup"}

        lookup = _load_city_lookup()
        city_lower = (city_name or "").strip().lower()

        # ── St. Petersburg — confirmed live ArcGIS endpoints ──────────────────
        if "st. petersburg" in city_lower or "st petersburg" in city_lower:
            try:
                coords = self._geocode_single_line(f"{address}, St. Petersburg, FL")
                if not coords:
                    return {"success": False, "error": "Could not geocode address for St. Petersburg"}

                lat, lon = coords
                geom_params = {
                    "geometry": f"{lon},{lat}",
                    "geometryType": "esriGeometryPoint",
                    "inSR": "4326",
                    "spatialRel": "esriSpatialRelIntersects",
                    "returnGeometry": "false",
                    "f": "json",
                }

                z_resp = self._session.get(
                    "https://egis.stpete.org/arcgis/rest/services/ServicesDOTS/Zoning/MapServer/0/query",
                    params={**geom_params, "outFields": "ZONECLASS,ZONEDESC"},
                    timeout=self.timeout,
                )
                z_resp.raise_for_status()
                z_features = z_resp.json().get("features", [])
                zoning_code = zoning_desc = ""
                if z_features:
                    za = z_features[0]["attributes"]
                    zoning_code = za.get("ZONECLASS", "") or ""
                    zoning_desc = za.get("ZONEDESC", "") or ""

                flu_resp = self._session.get(
                    "https://egis.stpete.org/arcgis/rest/services/ServicesDOTS/Zoning/MapServer/2/query",
                    params={**geom_params, "outFields": "LANDUSECODE,LANDUSEDESC"},
                    timeout=self.timeout,
                )
                flu_resp.raise_for_status()
                flu_features = flu_resp.json().get("features", [])
                flu_code = flu_desc = ""
                if flu_features:
                    fa = flu_features[0]["attributes"]
                    flu_code = fa.get("LANDUSECODE", "") or ""
                    flu_desc = fa.get("LANDUSEDESC", "") or ""

                if not zoning_code and not flu_code:
                    return {"success": False, "error": "No zoning data found at this address in St. Petersburg"}

                return {
                    "success": True,
                    "zoning_code": zoning_code,
                    "zoning_description": zoning_desc,
                    "future_land_use": flu_code,
                    "future_land_use_description": flu_desc,
                    "jurisdiction": "St. Petersburg",
                }
            except Exception as exc:
                return {"success": False, "error": f"St. Pete zoning API error: {exc}"}

        # ── Cities with a zoning_api entry in cities.json ─────────────────────
        meta = _get_city_meta(city_name, lookup)
        zoning_api = (meta or {}).get("zoning_api")
        if zoning_api:
            try:
                city_suffix = (meta or {}).get("geocode_city_suffix") or f"{city_name}, FL"
                coords = self._geocode_single_line(f"{address}, {city_suffix}")
                if not coords:
                    return {"success": False, "error": f"Could not geocode address for {city_name}"}

                lat, lon = coords
                geom_params = {
                    "geometry": f"{lon},{lat}",
                    "geometryType": "esriGeometryPoint",
                    "inSR": "4326",
                    "spatialRel": "esriSpatialRelIntersects",
                    "outFields": "*",
                    "returnGeometry": "false",
                    "f": "json",
                }

                z_resp = self._session.get(zoning_api, params=geom_params, timeout=self.timeout)
                z_resp.raise_for_status()
                z_features = z_resp.json().get("features", [])
                if not z_features:
                    return {"success": False, "error": f"No zoning data found at this address in {city_name}"}

                attrs = z_features[0]["attributes"]
                zoning_code = (
                    attrs.get("ZONING") or attrs.get("ZONECLASS") or
                    attrs.get("ZONE_CD") or attrs.get("ZONE_CODE") or ""
                )
                zoning_desc = (
                    attrs.get("ZONEDESC") or attrs.get("ZONE_DESC") or
                    attrs.get("ZONING_DESCRIPTION") or ""
                )

                flu_code = flu_desc = ""
                flu_api = (meta or {}).get("flu_api")
                if flu_api:
                    flu_resp = self._session.get(flu_api, params=geom_params, timeout=self.timeout)
                    flu_resp.raise_for_status()
                    flu_features = flu_resp.json().get("features", [])
                    if flu_features:
                        fa = flu_features[0]["attributes"]
                        flu_code = (
                            fa.get("LANDUSECODE") or fa.get("FLU_CODE") or
                            fa.get("LANDUSE") or fa.get("FUTURE_LAND_USE") or ""
                        )
                        flu_desc = (
                            fa.get("LANDUSEDESC") or fa.get("FLU_DESC") or
                            fa.get("LAND_USE_DESCRIPTION") or ""
                        )

                return {
                    "success": True,
                    "zoning_code": zoning_code,
                    "zoning_description": zoning_desc,
                    "future_land_use": flu_code,
                    "future_land_use_description": flu_desc,
                    "jurisdiction": city_name,
                }
            except Exception as exc:
                return {"success": False, "error": f"{city_name} zoning API error: {exc}"}

        # ── No API — signal caller to open the map viewer ─────────────────────
        map_url = None
        if meta:
            for url_key in ("zoning_flu_app", "zoning_flu_lookup_app", "zoning_app", "gis_viewer_app", "open_data_hub"):
                if meta.get(url_key):
                    map_url = meta[url_key]
                    break
        return {
            "success": False,
            "open_map": True,
            "map_url": map_url,
            "error": f"No zoning API configured for {city_name} — open GIS map instead.",
        }

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
