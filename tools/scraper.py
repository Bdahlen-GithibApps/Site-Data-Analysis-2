"""
tools/scraper.py — Web scraping utilities for county property appraiser systems.

Extracted from app.py. Includes:
- get_resilient_session(): requests.Session with retry strategy
- scrape_pinellas_property(): PCPAO parcel data scraper
- expand_city_name(): Pinellas city abbreviation expander
- strip_dor_code(): Florida DOR code prefix stripper
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Any

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def _load_city_map() -> Dict[str, str]:
    path = Path(__file__).parent.parent / "data" / "pinellas" / "maps.json"
    with path.open() as f:
        data = json.load(f)
    return data.get("city_map", {})


def expand_city_name(city_abbr: str) -> str:
    if not city_abbr:
        return "Unincorporated Pinellas"
    city_map = _load_city_map()
    return city_map.get(city_abbr.strip().upper(), city_abbr)


def _load_dor_use_codes() -> Dict[str, Any]:
    path = Path(__file__).parent.parent / "data" / "fl_dor_use_codes.json"
    if path.exists():
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    return {}


_DOR_USE_CODES: Dict[str, Any] = {}


def lookup_dor_use_code(raw: str) -> str:
    """
    Given a raw DOR land use string from a property appraiser system
    (e.g. '48 WAREHOUSING' or '048' or '0048 Warehousing...'), extract
    the DOR code number and return a formatted string:
        '048 — Warehousing, distribution terminals... (Industrial)'
    Falls back to cleaning the raw string if no match found.
    """
    global _DOR_USE_CODES
    if not _DOR_USE_CODES:
        _DOR_USE_CODES = _load_dor_use_codes()

    if not raw:
        return ""
    text = raw.strip()

    # Extract leading numeric code (1-3 digits)
    m = re.match(r'^(\d{1,3})\b', text)
    if m:
        code_num = m.group(1).zfill(3)  # zero-pad to 3 digits
        entry = _DOR_USE_CODES.get(code_num)
        if entry:
            category = entry.get("category", "")
            desc = entry["description"]
            if category:
                return f"{code_num} — {desc} ({category})"
            return f"{code_num} — {desc}"
        # Code found but not in our table — return cleaned text
        rest = text[m.end():].strip()
        return f"{code_num} — {rest}" if rest else code_num

    # No leading code — return as-is, cleaned
    return text


# Keep old name as alias for backward compatibility
def strip_dor_code(land_use_text: str) -> str:
    return lookup_dor_use_code(land_use_text)



def get_resilient_session() -> requests.Session:
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


def scrape_pinellas_property(parcel_id: str) -> Dict[str, Any]:
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


def _pasco_spatial_lookup(session: requests.Session, cx: float, cy: float) -> Dict[str, str]:
    """Given a parcel centroid (web mercator), return zoning and FLUM codes."""
    geom = json.dumps({"x": cx, "y": cy, "spatialReference": {"wkid": 102100}})
    params = {
        "geometry": geom,
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "inSR": "102100",
        "returnGeometry": "false",
        "f": "json",
    }

    zoning_code = ""
    zoning_desc = ""
    flum_code = ""
    flum_desc = ""

    try:
        rz = session.get(
            "https://services6.arcgis.com/Mo4MddfRHpFwT7UF/arcgis/rest/services/Zoning_Areas/FeatureServer/9/query",
            params={**params, "outFields": "ZONEID,ZN_TYPE"},
            timeout=15,
        )
        zfeats = rz.json().get("features", [])
        if zfeats:
            zone_id = zfeats[0]["attributes"].get("ZONEID")
            zoning_code = str(zfeats[0]["attributes"].get("ZN_TYPE") or "").strip()
            if zone_id:
                rd = session.get(
                    "https://services6.arcgis.com/Mo4MddfRHpFwT7UF/arcgis/rest/services/Zoning_Areas/FeatureServer/10/query",
                    params={"where": f"ZONEID={zone_id}", "outFields": "ZN_TYPE,ZN_DESC", "returnGeometry": "false", "f": "json"},
                    timeout=15,
                )
                dfeats = rd.json().get("features", [])
                if dfeats:
                    zoning_desc = str(dfeats[0]["attributes"].get("ZN_DESC") or "").strip()
    except Exception:
        pass

    try:
        rf = session.get(
            "https://services6.arcgis.com/Mo4MddfRHpFwT7UF/arcgis/rest/services/Future_Landuse_2025/FeatureServer/7/query",
            params={**params, "outFields": "FLU_CODE,DESCRIPTION"},
            timeout=15,
        )
        ffeats = rf.json().get("features", [])
        if ffeats:
            flum_code = str(ffeats[0]["attributes"].get("FLU_CODE") or "").strip()
            flum_desc = str(ffeats[0]["attributes"].get("DESCRIPTION") or "").strip()
    except Exception:
        pass

    return {
        "zoning": zoning_code,
        "zoning_description": zoning_desc,
        "future_land_use": flum_code,
        "flum_description": flum_desc,
    }


def scrape_pasco_property(parcel_id: str) -> Dict[str, Any]:
    """Fetch parcel data from Pasco County ArcGIS REST service, including zoning and FLUM."""
    session = get_resilient_session()
    url = "https://maps.pascopa.com/arcgis/rest/services/Parcels/MapServer/3/query"
    pid = parcel_id.strip()
    where = f"ParcelID='{pid.replace(chr(39), chr(39)+chr(39))}'"
    try:
        r = session.get(
            url,
            params={
                "where": where,
                "outFields": "NAD_NAME_1,NAD_NAME_2,PHYS_STREET,PHYS_CITY,PHYS_STATE,PHYS_ZIP,TR_AC,VAL_ACRES,DIR_CLASS",
                "returnGeometry": "true",
                "f": "json",
            },
            timeout=15,
        )
        r.raise_for_status()
        d = r.json()
        features = d.get("features", [])
        if not features:
            return {"success": False, "error": "Parcel not found in Pasco County records"}
        feat = features[0]
        a = feat.get("attributes", {})

        owner_parts = [str(a.get("NAD_NAME_1") or "").strip(), str(a.get("NAD_NAME_2") or "").strip()]
        owner = " ".join(p for p in owner_parts if p)

        street = str(a.get("PHYS_STREET") or "").strip()
        city = str(a.get("PHYS_CITY") or "").strip().title()
        state = str(a.get("PHYS_STATE") or "FL").strip() or "FL"
        zip_code = str(a.get("PHYS_ZIP") or "").strip()
        address_parts = [street, city, f"{state} {zip_code}".strip()]
        address = ", ".join(p for p in address_parts if p)

        acres_raw = a.get("TR_AC") if a.get("TR_AC") is not None else a.get("VAL_ACRES")
        try:
            acres = float(acres_raw or 0)
            acres_str = f"{acres:.2f}" if acres else ""
        except Exception:
            acres_str = str(acres_raw or "")

        dir_class = str(a.get("DIR_CLASS") or "").strip().zfill(3)
        land_use = lookup_dor_use_code(dir_class)

        # Spatial zoning + FLUM lookup using parcel centroid
        spatial = {}
        rings = (feat.get("geometry") or {}).get("rings", [[]])
        pts = rings[0] if rings else []
        if pts:
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            spatial = _pasco_spatial_lookup(session, cx, cy)

        return {
            "success": True,
            "parcel_id": pid,
            "owner": owner,
            "address": address,
            "city": city,
            "zip": zip_code,
            "land_use": land_use,
            "site_area_sqft": "",
            "site_area_acres": acres_str,
            **spatial,
        }
    except Exception as exc:
        return {"success": False, "error": f"Error querying Pasco ArcGIS: {str(exc)}"}
