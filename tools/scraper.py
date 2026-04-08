"""
Web scraping utilities for the Dev Code Lookup app.

Contains county property appraiser scrapers and HTTP session helpers.
"""
from __future__ import annotations

import re
import json
import logging
from pathlib import Path
from typing import Dict, Any

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data" / "pinellas"

_MAPS_CACHE: dict | None = None


def _get_maps() -> dict:
    global _MAPS_CACHE
    if _MAPS_CACHE is None:
        with open(_DATA_DIR / "maps.json") as f:
            _MAPS_CACHE = json.load(f)
    return _MAPS_CACHE


# ---------------------------------------------------------------------------
# HTTP session
# ---------------------------------------------------------------------------

def get_resilient_session() -> requests.Session:
    """Return an HTTP session with automatic retry logic."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# ---------------------------------------------------------------------------
# City / land-use name helpers
# ---------------------------------------------------------------------------

def expand_city_name(city_abbr: str) -> str:
    """Expand PCPAO city abbreviation to a full display name."""
    if not city_abbr:
        return "Unincorporated Pinellas"
    city_map: dict = _get_maps().get("city_map", {})
    return city_map.get(city_abbr.strip().upper(), city_abbr)


def strip_dor_code(land_use_text: str) -> str:
    """Remove leading DOR numeric code from a land-use string, e.g. '01 Single Family' → 'Single Family'."""
    if not land_use_text:
        return ""
    text = land_use_text.strip()
    if text and text[0].isdigit():
        parts = text.split(" ", 1)
        if len(parts) > 1:
            return parts[1].strip()
    return text


# ---------------------------------------------------------------------------
# Pinellas County scraper
# ---------------------------------------------------------------------------

def scrape_pinellas_property(parcel_id: str) -> Dict[str, Any]:
    """
    Query PCPAO for a Pinellas County parcel and return a standardised dict.

    Returns:
        dict with keys: success, parcel_id, address, city, zip, owner,
        land_use, site_area_sqft, site_area_acres, legal_description,
        strap, tax_district
    """
    session = get_resilient_session()
    url = "https://www.pcpao.gov/dal/quicksearch/searchProperty"

    normalized_parcel = parcel_id.strip()
    if "-" not in normalized_parcel and len(normalized_parcel) == 18:
        normalized_parcel = (
            f"{normalized_parcel[0:2]}-{normalized_parcel[2:4]}-{normalized_parcel[4:6]}-"
            f"{normalized_parcel[6:11]}-{normalized_parcel[11:14]}-{normalized_parcel[14:18]}"
        )

    payload = {
        "draw": "1", "start": "0", "length": "10",
        "search[value]": "", "search[regex]": "false",
        "input": normalized_parcel, "searchsort": "parcel_number",
        "url": "https://www.pcpao.gov",
    }
    for i in range(11):
        payload[f"columns[{i}][data]"] = str(i)
        payload[f"columns[{i}][name]"] = ""
        payload[f"columns[{i}][searchable]"] = "true"
        payload[f"columns[{i}][orderable]"] = "true" if i >= 2 else "false"
        payload[f"columns[{i}][search][value]"] = ""
        payload[f"columns[{i}][search][regex]"] = "false"

    try:
        response = session.post(url, data=payload, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("recordsTotal", 0) == 0:
            return {"success": False, "error": "Parcel not found in PCPAO database"}
        if not data.get("data"):
            return {"success": False, "error": "No property data returned"}

        row = data["data"][0]
        owner = BeautifulSoup(row[2] if len(row) > 2 else "", "html.parser").get_text(strip=True)
        address = BeautifulSoup(row[5] if len(row) > 5 else "", "html.parser").get_text(strip=True)
        tax_district = BeautifulSoup(row[6] if len(row) > 6 else "", "html.parser").get_text(strip=True)
        city = expand_city_name(tax_district)
        property_use = strip_dor_code(
            BeautifulSoup(row[7] if len(row) > 7 else "", "html.parser").get_text(strip=True)
        )
        legal_desc = BeautifulSoup(row[8] if len(row) > 8 else "", "html.parser").get_text(strip=True)

        sqft = None
        acres = None
        zip_code = None
        strap = None

        try:
            parts = normalized_parcel.split("-")
            if len(parts) == 6:
                parts[0], parts[2] = parts[2], parts[0]
                strap = "".join(parts)
            else:
                strap = normalized_parcel.replace("-", "")

            detail_url = (
                f"https://www.pcpao.gov/property-details"
                f"?s={strap}&input={normalized_parcel}&search_option=parcel_number"
            )
            html = session.get(detail_url, timeout=30).text
            soup = BeautifulSoup(html, "html.parser")
            txt = soup.get_text(" ", strip=True)

            m = re.search(
                r"Land Area:\s*[^\d]*([\d,]+)\s*sf\s*\|\s*[^\d]*([\d.]+)\s*acres",
                txt,
                flags=re.IGNORECASE,
            )
            if m:
                sqft = int(m.group(1).replace(",", ""))
                acres = float(m.group(2))

            z = re.search(r"FL\s*(\d{5})", txt)
            if z:
                zip_code = z.group(1)
        except Exception:
            pass

        return {
            "success": True,
            "parcel_id": normalized_parcel,
            "address": address,
            "city": city,
            "zip": zip_code or "",
            "owner": owner,
            "land_use": property_use,
            "site_area_sqft": f"{sqft:,}" if sqft else "",
            "site_area_acres": f"{acres:.2f}" if acres else "",
            "legal_description": legal_desc,
            "strap": strap or "",
            "tax_district": tax_district,
        }
    except Exception as exc:
        return {"success": False, "error": f"Error querying PCPAO API: {str(exc)}"}
