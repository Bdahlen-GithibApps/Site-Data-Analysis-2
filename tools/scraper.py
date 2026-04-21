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

_HILLSBOROUGH_PARCELS_URL = "https://services.arcgis.com/apTfC6SUmnNfnxuF/arcgis/rest/services/HC_Parcels/FeatureServer/0/query"
_HILLSBOROUGH_ZONING_URL = "https://services.arcgis.com/apTfC6SUmnNfnxuF/arcgis/rest/services/Zoning/FeatureServer/0/query"
_HILLSBOROUGH_FLUM_BASE = "https://services.arcgis.com/apTfC6SUmnNfnxuF/arcgis/rest/services/Future_Land_Use_Element/FeatureServer"
_HILLSBOROUGH_FLUM_LAYERS = [1, 2, 0, 3]  # Tampa, Temple Terrace, Plant City, Unincorporated


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


def _fmt_adj(use_map: Dict[str, str]) -> str:
    if not use_map:
        return ""
    parts = list(use_map.values())
    return "Adjacent land uses: " + "; ".join(parts[:6])  # cap at 6 for readability


def _pasco_adjacent_uses(session: requests.Session, parcel_id: str, rings: list) -> str:
    """Return formatted adjacent land use string using parcel envelope + Pasco ArcGIS."""
    pts = rings[0] if rings else []
    if not pts:
        return ""
    min_x = min(p[0] for p in pts)
    max_x = max(p[0] for p in pts)
    min_y = min(p[1] for p in pts)
    max_y = max(p[1] for p in pts)
    pad = 15  # ~50 ft in web mercator metres
    envelope = json.dumps({
        "xmin": min_x - pad, "ymin": min_y - pad,
        "xmax": max_x + pad, "ymax": max_y + pad,
        "spatialReference": {"wkid": 102100},
    })
    try:
        r = session.get(
            "https://maps.pascopa.com/arcgis/rest/services/Parcels/MapServer/3/query",
            params={
                "geometry": envelope,
                "geometryType": "esriGeometryEnvelope",
                "inSR": "102100",
                "spatialRel": "esriSpatialRelIntersects",
                "where": f"ParcelID <> '{parcel_id.replace(chr(39), chr(39)+chr(39))}'",
                "outFields": "DIR_CLASS,PHYS_CITY",
                "returnGeometry": "false",
                "f": "json",
            },
            timeout=15,
        )
        feats = r.json().get("features", [])
        seen: Dict[str, str] = {}
        for f in feats:
            a = f.get("attributes") or {}
            code = str(a.get("DIR_CLASS") or "").strip().zfill(3)
            desc = lookup_dor_use_code(code)
            if desc and code not in seen:
                seen[code] = desc
        return _fmt_adj(seen)
    except Exception:
        return ""


def get_pinellas_adjacent_uses(parcel_id: str) -> str:
    """Query EGIS Pinellas Parcels for geometry of parcel then find adjacent USE_CODEs."""
    session = get_resilient_session()
    base = "https://egis.pinellas.gov/gis/rest/services/PublicWebGIS/Parcels/MapServer/1/query"
    digits = re.sub(r"[^0-9]", "", parcel_id)
    dsp = parcel_id.strip()
    where = (
        f"PARCELID_DSP1='{dsp}' OR PARCELID_DSP2='{dsp}'"
        + (f" OR STRAP='{digits}' OR PARCELID='{digits}'" if digits else "")
    )
    try:
        # Step 1: get geometry of subject parcel
        r = session.get(base, params={
            "where": where, "outFields": "PARCELID",
            "returnGeometry": "true", "outSR": "4326", "f": "json",
        }, timeout=15)
        feats = r.json().get("features", [])
        if not feats:
            return ""
        rings = (feats[0].get("geometry") or {}).get("rings", [])
        pts = rings[0] if rings else []
        if not pts:
            return ""
        # Step 2: build envelope and query adjacent parcels
        min_x = min(p[0] for p in pts)
        max_x = max(p[0] for p in pts)
        min_y = min(p[1] for p in pts)
        max_y = max(p[1] for p in pts)
        pad = 0.0003  # ~30 m in decimal degrees
        envelope = json.dumps({
            "xmin": min_x - pad, "ymin": min_y - pad,
            "xmax": max_x + pad, "ymax": max_y + pad,
            "spatialReference": {"wkid": 4326},
        })
        excl = f"PARCELID<>'{digits}'" if digits else "1=1"
        r2 = session.get(base, params={
            "geometry": envelope,
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "where": excl,
            "outFields": "USE_CODE,LAND_USE_CODE",
            "returnGeometry": "false",
            "f": "json",
        }, timeout=15)
        feats2 = r2.json().get("features", [])
        seen: Dict[str, str] = {}
        for f in feats2:
            a = f.get("attributes") or {}
            code = str(a.get("USE_CODE") or a.get("LAND_USE_CODE") or "").strip()
            desc = lookup_dor_use_code(code)
            if desc and code not in seen:
                seen[code] = desc
        return _fmt_adj(seen)
    except Exception:
        return ""


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


_PASCO_ZIP_CITY: Dict[str, str] = {
    "33523": "Dade City",
    "33524": "Dade City",
    "33525": "Dade City",
    "33526": "Dade City",
    "33540": "Zephyrhills",
    "33541": "Zephyrhills",
    "33542": "Zephyrhills",
    "33543": "Wesley Chapel",
    "33544": "Wesley Chapel",
    "33545": "Wesley Chapel",
    "33556": "Odessa",
    "33558": "Lutz",
    "33559": "Lutz",
    "33576": "San Antonio",
    "33597": "Trilby",
    "34610": "Spring Hill",
    "34637": "Land O' Lakes",
    "34638": "Land O' Lakes",
    "34639": "Land O' Lakes",
    "34652": "New Port Richey",
    "34653": "New Port Richey",
    "34654": "New Port Richey",
    "34655": "New Port Richey",
    "34667": "Hudson",
    "34668": "Port Richey",
    "34669": "Hudson",
    "34690": "Holiday",
    "34691": "Holiday",
}


def _pasco_reverse_geocode_city(session: requests.Session, cx: float, cy: float):
    """Given a web-mercator centroid, return (city_name, zip5) from Census geocoder."""
    import math
    # Convert Web Mercator (EPSG:3857) to WGS84
    lon = cx / 20037508.342 * 180.0
    lat = math.degrees(2.0 * math.atan(math.exp(cy / 20037508.342 * math.pi)) - math.pi / 2.0)
    try:
        r = session.get(
            "https://geocoding.geo.census.gov/geocoder/geographies/coordinates",
            params={
                "x": f"{lon:.6f}",
                "y": f"{lat:.6f}",
                "benchmark": "Public_AR_Census2020",
                "vintage": "Census2020_Census2020",
                "layers": "all",
                "format": "json",
            },
            timeout=10,
        )
        geo = r.json().get("result", {}).get("geographies", {})
        found_zip = ""
        # Try ZIP code tabulation area first to capture zip
        for zcta in geo.get("Zip Code Tabulation Areas", []):
            z = str(zcta.get("BASENAME", "") or zcta.get("NAME", "")).strip().replace("ZCTA5 ", "")
            if z.isdigit() and len(z) == 5:
                found_zip = z
                break
        # Prefer incorporated place name
        for place in geo.get("Incorporated Places", []):
            name = str(place.get("NAME", "")).strip().title()
            if name:
                return name, found_zip
        # Fall back to ZIP → city lookup
        if found_zip:
            city = _PASCO_ZIP_CITY.get(found_zip, "")
            return city, found_zip
    except Exception:
        pass
    return "", ""


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
        state_code = str(a.get("PHYS_STATE") or "FL").strip() or "FL"
        zip_code = str(a.get("PHYS_ZIP") or "").strip()

        # Compute centroid from geometry (needed for spatial lookups + city fallback)
        rings = (feat.get("geometry") or {}).get("rings", [[]])
        pts = rings[0] if rings else []
        cx = cy = None
        if pts:
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)

        # Vacant land often has no PHYS_CITY — use Census reverse geocoder to fill it
        if (not city or not zip_code) and cx is not None:
            geo_city, geo_zip = _pasco_reverse_geocode_city(session, cx, cy)
            if not city:
                city = geo_city
            if not zip_code and geo_zip:
                zip_code = geo_zip

        # If still no city, fall back to unincorporated label
        if not city:
            city = "Unincorporated Pasco"

        # Build site address — if no physical street, match PA website which shows "No Physical Address"
        if street:
            addr_loc = f"{state_code} {zip_code}".strip()
            address_parts = [p for p in [street, city, addr_loc] if p]
            address = ", ".join(address_parts)
        else:
            address = "No Physical Address"

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
        if cx is not None:
            spatial = _pasco_spatial_lookup(session, cx, cy)

        adj_uses = _pasco_adjacent_uses(session, pid, rings)

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
            "adjoining_uses": adj_uses,
            **spatial,
        }
    except Exception as exc:
        return {"success": False, "error": f"Error querying Pasco ArcGIS: {str(exc)}"}


def _hillsborough_folio_variants(parcel_id: str) -> tuple[str, str]:
    digits = re.sub(r"[^0-9]", "", parcel_id or "")
    folio = digits[:10] if len(digits) >= 10 else digits
    dotted = f"{folio[:6]}.{folio[6:]}" if len(folio) == 10 else folio
    return folio, dotted


def _hillsborough_spatial_lookup(session: requests.Session, cx: float, cy: float) -> Dict[str, str]:
    geom = json.dumps({"x": cx, "y": cy, "spatialReference": {"wkid": 2237}})
    params = {
        "geometry": geom,
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "inSR": "2237",
        "returnGeometry": "false",
        "f": "json",
    }

    zoning_code = ""
    zoning_desc = ""
    flum_code = ""
    flum_desc = ""

    try:
        rz = session.get(
            _HILLSBOROUGH_ZONING_URL,
            params={**params, "outFields": "NZONE,NZONE_DESC,LandDevCode,CATEGORY", "where": "1=1"},
            timeout=15,
        )
        zfeats = rz.json().get("features", [])
        if zfeats:
            a = zfeats[0].get("attributes", {})
            zoning_code = str(a.get("NZONE") or a.get("LandDevCode") or "").strip()
            zoning_desc = str(a.get("NZONE_DESC") or a.get("CATEGORY") or "").strip()
    except Exception:
        pass

    for layer_id in _HILLSBOROUGH_FLUM_LAYERS:
        try:
            rf = session.get(
                f"{_HILLSBOROUGH_FLUM_BASE}/{layer_id}/query",
                params={**params, "where": "1=1", "outFields": "FLUE,FLU_DESC,JURISDICTION"},
                timeout=15,
            )
            ffeats = rf.json().get("features", [])
            if not ffeats:
                continue
            a = ffeats[0].get("attributes", {})
            flum_code = str(a.get("FLUE") or "").strip()
            flum_desc = str(a.get("FLU_DESC") or "").strip()
            if flum_code or flum_desc:
                break
        except Exception:
            continue

    return {
        "zoning": zoning_code,
        "zoning_description": zoning_desc,
        "future_land_use": flum_code,
        "flum_description": flum_desc,
    }


def scrape_hillsborough_property(parcel_id: str) -> Dict[str, Any]:
    """Fetch parcel data from Hillsborough County ArcGIS, including zoning and FLUM where available."""
    session = get_resilient_session()
    folio, folio_dotted = _hillsborough_folio_variants(parcel_id)
    if not folio:
        return {"success": False, "error": "Enter a valid Hillsborough folio or parcel number."}

    safe_folio = folio.replace(chr(39), chr(39) + chr(39))
    safe_dotted = folio_dotted.replace(chr(39), chr(39) + chr(39))
    where = f"FOLIO='{safe_folio}' OR FOLIO_NUMB='{safe_dotted}'"

    try:
        r = session.get(
            _HILLSBOROUGH_PARCELS_URL,
            params={
                "where": where,
                "outFields": "FOLIO,FOLIO_NUMB,OWNER,SITE_ADDR,SITE_CITY,SITE_ZIP,ACREAGE,DOR_CODE,LU_GRP",
                "returnGeometry": "true",
                "f": "json",
            },
            timeout=15,
        )
        r.raise_for_status()
        d = r.json()
        features = d.get("features", [])
        if not features:
            return {"success": False, "error": "Parcel not found in Hillsborough County records"}

        feat = features[0]
        a = feat.get("attributes", {})

        folio_out = str(a.get("FOLIO") or folio).strip()
        owner = str(a.get("OWNER") or "").strip()
        street = str(a.get("SITE_ADDR") or "").strip()
        city = str(a.get("SITE_CITY") or "").strip().title()
        zip_code = str(a.get("SITE_ZIP") or "").strip()

        if not city:
            city = "Unincorporated Hillsborough"

        address = ", ".join([p for p in [street, city, f"FL {zip_code}".strip()] if p]) if street else "No Physical Address"

        acres_val = a.get("ACREAGE")
        try:
            acres = float(acres_val or 0)
        except Exception:
            acres = 0.0
        acres_str = f"{acres:.2f}" if acres > 0 else ""
        sqft_str = f"{int(round(acres * 43560)):,}" if acres > 0 else ""

        dor_code = str(a.get("DOR_CODE") or "").strip()
        dor_trim = dor_code[:3].zfill(3) if dor_code else ""
        land_use = lookup_dor_use_code(dor_trim) if dor_trim else str(a.get("LU_GRP") or "").strip()

        rings = (feat.get("geometry") or {}).get("rings", [[]])
        pts = rings[0] if rings else []
        spatial: Dict[str, str] = {}
        if pts:
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            spatial = _hillsborough_spatial_lookup(session, cx, cy)

        return {
            "success": True,
            "parcel_id": folio_out,
            "owner": owner,
            "address": address,
            "city": city,
            "zip": zip_code,
            "land_use": land_use,
            "site_area_sqft": sqft_str,
            "site_area_acres": acres_str,
            "adjoining_uses": "",
            **spatial,
        }
    except Exception as exc:
        return {"success": False, "error": f"Error querying Hillsborough ArcGIS: {str(exc)}"}
