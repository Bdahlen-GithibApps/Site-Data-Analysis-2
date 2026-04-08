"""
Shared helper utilities for the Dev Code Lookup app.

Includes numeric helpers, UI component factories, parcel ID validation,
and the zoning map URL builder.
"""
from __future__ import annotations

import re
import json
import logging
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote

from nicegui import ui

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data directory
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).parent.parent / "data" / "pinellas"


def _load_maps() -> dict:
    with open(_DATA_DIR / "maps.json") as f:
        return json.load(f)


_MAPS: dict | None = None


def _get_maps() -> dict:
    global _MAPS
    if _MAPS is None:
        _MAPS = _load_maps()
    return _MAPS


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

def safe_float(val: Any, default: float = 0.0) -> float:
    """Convert a value to float, returning *default* on failure."""
    if val is None or val == "":
        return default
    try:
        return float(str(val).replace(",", ""))
    except (TypeError, ValueError):
        return default


def safe_int(val: Any, default: int = 0) -> int:
    """Convert a value to int, returning *default* on failure."""
    if val is None or val == "":
        return default
    try:
        return int(float(str(val).replace(",", "")))
    except (TypeError, ValueError):
        return default


def fmt_num(val: Any) -> str:
    """Format a number with thousands separators; return '' for empty/None."""
    if val is None or val == "":
        return ""
    try:
        n = float(str(val).replace(",", ""))
        if n == int(n):
            return f"{int(n):,}"
        return f"{n:,.2f}"
    except (TypeError, ValueError):
        return str(val)


# ---------------------------------------------------------------------------
# Parcel ID validation
# ---------------------------------------------------------------------------

def validate_parcel_id(parcel_id: str) -> tuple[bool, str]:
    """Return (is_valid, error_message) for a raw parcel ID string."""
    if not parcel_id:
        return False, "Parcel ID cannot be empty"
    if len(parcel_id) > 30:
        return False, "Parcel ID must be 30 characters or less"
    if not re.match(r"^[A-Za-z0-9\-\s\.]+$", parcel_id):
        return False, "Invalid characters in parcel ID"
    return True, ""


# ---------------------------------------------------------------------------
# NiceGUI component helpers
# ---------------------------------------------------------------------------

def labeled_input(
    label: str,
    *,
    value: Any = "",
    placeholder: str = "",
    classes: str = "w-full",
    input_classes: str = "w-full",
    input_props: str = "",
) -> ui.input:
    """Render a label + input pair and return the input element."""
    with ui.column().classes(classes):
        ui.label(label).classes("field-label")
        input_el = ui.input(value=value, placeholder=placeholder)
        if input_classes:
            input_el.classes(input_classes)
        if input_props:
            input_el.props(input_props)
        return input_el


def labeled_select(
    label: str,
    options: Any,
    *,
    value: Any = None,
    classes: str = "w-full",
    select_classes: str = "w-full",
    select_props: str = "",
    with_input: bool = False,
) -> ui.select:
    """Render a label + select pair and return the select element."""
    with ui.column().classes(classes):
        ui.label(label).classes("field-label")
        select_el = ui.select(options, value=value, with_input=with_input)
        if select_classes:
            select_el.classes(select_classes)
        if select_props:
            select_el.props(select_props)
        return select_el


# ---------------------------------------------------------------------------
# Zoning map URL helpers
# ---------------------------------------------------------------------------

def _build_map_url_with_address(
    map_url: Optional[str],
    address: str,
    city: str,
    zip_code: str,
) -> Optional[str]:
    """Append address as a ``?find=`` parameter for ArcGIS apps that support it."""
    if not map_url or not address:
        return map_url
    if not any(
        token in map_url.lower()
        for token in ("arcgis.com/apps", "webappviewer", "informationlookup", "experiencebuilder")
    ):
        return map_url

    search = address.strip()
    if city:
        city_lower = city.strip().lower()
        if city_lower and city_lower not in search.lower():
            search = f"{search}, {city}, FL"
        else:
            search = f"{search}, FL"
    if zip_code:
        zip_clean = zip_code.strip()
        if zip_clean and zip_clean not in search:
            search = f"{search} {zip_clean}"

    parsed = urlparse(map_url)
    query = parse_qs(parsed.query)
    if "find" in query:
        return map_url
    query["find"] = [search]
    new_query = urlencode(query, doseq=True, quote_via=quote)
    return urlunparse(parsed._replace(query=new_query))


def get_zoning_map_url(
    city: str,
    address: str = "",
    zip_code: str = "",
) -> Optional[str]:
    """Return the best zoning map URL for *city*, optionally deep-linked to an address."""
    zoning_map_urls: dict = _get_maps().get("zoning_map_urls", {})

    if not city:
        base = zoning_map_urls.get("Unincorporated Pinellas")
        return _build_map_url_with_address(base, address, "", zip_code)

    # Exact match first
    base = zoning_map_urls.get(city)

    # Fuzzy match
    if not base:
        city_lower = city.strip().lower()
        for key, url in zoning_map_urls.items():
            if key.lower() in city_lower or city_lower in key.lower():
                base = url
                break

    # Unincorporated fallback
    if not base and "unincorporated" in city.lower():
        base = zoning_map_urls.get("Unincorporated Pinellas")

    # County fallback for any Pinellas city we don't have a specific URL for
    if not base:
        base = zoning_map_urls.get("Unincorporated Pinellas")

    return _build_map_url_with_address(base, address, city, zip_code)
