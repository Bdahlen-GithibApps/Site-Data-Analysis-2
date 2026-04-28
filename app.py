"""
Florida Development Code Lookup — NiceGUI App

Multi-agent frontend with 4 tabs:
  1. Property Lookup — County + Parcel ID → PCPAO scrape → auto-fill
  2. Requirements  — Zoning dimensional standards + FLUM density/intensity
  3. Parking        — Use-based parking calculation + ADA + bicycle
  4. Landscape      — Buffer, tree canopy, and irrigation requirements

Run:
    pip install -r requirements.txt
    python app.py
"""

from __future__ import annotations

import math
import os
import re
from typing import Any, Dict, List
from urllib.parse import quote_plus

from nicegui import ui, run

from agents.zoning_agent import ZoningAgent
from agents.parking_agent import ParkingAgent
from agents.landscape_agent import LandscapeAgent
from agents.infrastructure_agent import InfrastructureAgent
from agents.environmental_agent import EnvironmentalAgent
from agents import get_code_urls, get_code_url
from tools.scraper import (
    scrape_pinellas_property,
    scrape_pasco_property,
    scrape_hillsborough_property,
    expand_city_name,
    lookup_dor_use_code,
    get_pinellas_adjacent_uses,
)
from tools.helpers import (
    safe_float,
    safe_int,
    fmt_num,
    validate_parcel_id,
    labeled_input,
    labeled_select,
    get_zoning_map_url,
)

# ──────────────────────────────────────────────────────────────────────
# Agent instances
# ──────────────────────────────────────────────────────────────────────

_zoning_agent = ZoningAgent()
_parking_agent = ParkingAgent()
_landscape_agent = LandscapeAgent()
_infra_agent = InfrastructureAgent()
_env_agent = EnvironmentalAgent()


def _build_parcel_links(county: str, parcel_id: str, address: str, city: str) -> List[Dict[str, str]]:
    """Return a list of {label, url} dicts for quick-access links relevant to the parcel."""
    fema_query = quote_plus(f"{address} {city}".strip())
    fema_url = f"https://msc.fema.gov/portal/search?AddressQuery={fema_query}#searchresultsanchor"
    parcel_q = quote_plus(parcel_id.strip()) if parcel_id else ""
    links = []
    if county == "Pasco":
        # Use stable landing/search pages for reliability; old deep-links 404 frequently.
        links.append({"label": "Property Appraiser", "url": "https://search.pascopa.com/"})
        links.append({"label": "Parcel Map (GIS)", "url": "http://maps.pascopa.com/"})
        links.append({"label": "Deed / OR Records", "url": "https://www.pascoclerk.com/"})
        links.append({"label": "Development Services", "url": "https://www.pascocountyfl.gov/162/Development-Review"})
        if parcel_q:
            links.append({
                "label": "Pasco Parcel Search",
                "url": f"https://www.google.com/search?q=site%3Asearch.pascopa.com+{parcel_q}",
            })
    elif county == "Hillsborough":
        links.append({"label": "Property Appraiser", "url": "https://gis.hcpafl.org/propertysearch/"})
        links.append({"label": "Parcel Map (GIS)", "url": "https://gis.hcpafl.org/propertysearch/"})
        links.append({"label": "Deed / OR Records", "url": "https://publicaccess.hillsclerk.com/oripublicaccess/"})
        links.append({"label": "Development Services", "url": "https://hcfl.gov/"})
        if parcel_q:
            links.append({
                "label": "Hillsborough Parcel Search",
                "url": f"https://www.google.com/search?q=site%3Agis.hcpafl.org+propertysearch+{parcel_q}",
            })
    elif county == "Pinellas":
        links.append({"label": "Property Appraiser", "url": "https://www.pcpao.gov/quick-search?qu=1"})
        links.append({"label": "Parcel Map (GIS)", "url": "https://www.pcpao.gov/gis.html?v=5&home="})
        links.append({"label": "Deed / OR Records", "url": "https://officialrecords.mypinellasclerk.org/"})
        links.append({"label": "Building & DRS", "url": "https://pinellas.gov/building-and-development-review-services/"})
        if parcel_q:
            links.append({
                "label": "Pinellas Parcel Search",
                "url": f"https://www.google.com/search?q=site%3Apcpao.gov+{parcel_q}",
            })
    else:
        # Unsupported counties: avoid showing incorrect county-specific links.
        county_q = county.replace(" ", "+")
        links.append({"label": "County Property Search", "url": f"https://www.google.com/search?q={county_q}+County+Property+Appraiser+parcel+search"})
        links.append({"label": "County GIS", "url": f"https://www.google.com/search?q={county_q}+County+GIS+parcel+map"})
        links.append({"label": "County Development Services", "url": f"https://www.google.com/search?q={county_q}+County+development+services"})
    # FEMA flood map — same for all counties
    links.append({"label": "FEMA Flood Map", "url": fema_url})
    # SWFWMD ePermitting
    links.append({"label": "SWFWMD ePermitting", "url": "https://www.swfwmd.state.fl.us/permits/epermitting"})
    return links

# ──────────────────────────────────────────────────────────────────────
# App state
# ──────────────────────────────────────────────────────────────────────

state: Dict[str, Any] = {
    "county": "Pinellas",
    "parcel_id": "",
    # Lookup results
    "address": "",
    "city": "",
    "zip": "",
    "lat": None,
    "lon": None,
    "owner": "",
    "land_use": "",
    "site_area_acres": "",
    "site_area_sqft": "",
    # Code inputs (manual or from lookup)
    "zoning": "",
    "future_land_use": "",
    # Parking inputs — list of {use_type, building_sf, num_units} dicts
    "parking_uses": [],
    # Legacy single-use keys kept for backward compat
    "use_type": "",
    "building_sf": "",
    "num_units": "",
    # Site Information (SIR)
    "tax_parcel": "",
    "site_views": "",
    "adjoining_uses": "",
    "proposed_zoning": "",
    # Subdivision (SIR)
    "platting": "",
    "takings_easements": "",
    # Infrastructure (SIR)
    "utilities_water": "",
    "utilities_reclaim": "",
    "utilities_sewer": "",
    "utilities_storm": "",
    "utilities_gas": "",
    "utilities_electric": "",
    "easements_required": "",
    "utility_extensions": "",
    "roadway_improvements": "",
    "signalization": "",
    "encroachments": "",
    "additional_access": "",
    # Environmental (SIR)
    "impact_studies": "",
    "stormwater_treatment": "",
    "wetlands_flood": "",
    "flood_elevation": "",
    "natural_cultural": "",
    "env_considerations": "",
    "geotechnical": "",
    "traffic_study": "",
    # Building (SIR)
    "building_code": "Florida Building Code",
    "construction_methods": "",
    "fire_route": "",
    # Fees (SIR)
    "fee_fire_plan_review": "",
    "fee_bldg_plan_review": "",
    "fee_site_plan_review": "",
    "fee_bldg_permit": "",
    "fee_demo_permit": "",
    "fee_dedication": "",
    "fee_securities": "",
    "fee_lot_line_adj": "",
    "fee_pre_app": "",
    "fee_coastal_dev": "",
    # Schedule (SIR)
    "sched_lot_line_adj": "",
    "sched_entitlements": "",
    "sched_perm_steps": "",
    "sched_local": "",
    "sched_wmd": "",
    "sched_fdep": "",
    "sched_fdot": "",
    "sched_staff_meetings": "",
    "sched_public_meetings": "",
}

ui_refs: Dict[str, Any] = {}

# Fee section labels used in the Fees tab and Excel export.
FEE_SECTION_LABELS = {
    "application_fees":   "Application & Permit Fees",
    "impact_fees":        "Impact Fees",
    "pre_app":            "Pre-Application Meeting",
    "perm_steps":         "Permitting Steps",
    "local_permits":      "Local Permitting (County / City)",
    "wmd":                "SWFWMD Permitting",
    "fdep":               "FDEP Permitting",
    "fdot":               "FDOT Permitting",
    "dedication":         "ROW Dedication / Easements",
    "securities":         "Securities & Utility Connection Fees",
    "coastal_dev_permit": "Coastal Development Permit",
    "entitlements":       "Entitlements Process",
    "lot_line":           "Lot Line / Subdivision",
    "staff_meetings":     "Required Staff Meetings",
    "public_meetings":    "Required Public Meetings",
}


# ──────────────────────────────────────────────────────────────────────
# Requirements calculation
# ──────────────────────────────────────────────────────────────────────

def build_requirements_markdown() -> str:
    county = state.get("county", "Pinellas")
    city = state.get("city", "")
    zoning_code = (state.get("zoning") or "").strip().upper()
    flu_code = (state.get("future_land_use") or "").strip().upper()
    site_sf = safe_float(state.get("site_area_sqft"))

    if not zoning_code and not flu_code:
        return "*Enter Zoning and/or Future Land Use to see requirements.*"

    lines: List[str] = []

    # Dimensional standards
    zd = _zoning_agent.get_zoning_standards(county, zoning_code, city) if zoning_code else None
    if zd:
        lines.append(f"### Zoning: {zoning_code} — {zd['name']}")
        lines.append(f"**Category:** {zd['category']}")
        lines.append(f"**Allowed Uses:** {zd.get('allowed_uses_summary', '')}")
        lines.append("")
        lines.append("| Standard | Value |")
        lines.append("|----------|-------|")
        lines.append(f"| Min Lot Area | {zd.get('min_lot_area', 'N/A')} |")
        if zd.get("min_lot_width"):
            lines.append(f"| Min Lot Width | {zd['min_lot_width']} |")
        if zd.get("min_lot_depth"):
            lines.append(f"| Min Lot Depth | {zd['min_lot_depth']} |")

        # Setbacks
        for key, label in [
            ("setback_front_structure", "Front (Structure)"),
            ("setback_front_porch", "Front (Porch/Deck)"),
            ("setback_front", "Front"),
            ("setback_front_garage", "Front (Garage)"),
            ("setback_side_interior", "Side (Interior)"),
            ("setback_side_street", "Side (Street)"),
            ("setback_side_abutting_nonresidential", "Side (Abut Non-Res)"),
            ("setback_side_abutting_residential", "Side (Abut Res)"),
            ("setback_rear", "Rear"),
        ]:
            val = zd.get(key)
            if val is not None:
                lines.append(f"| Setback — {label} | {val} ft |")

        if zd.get("max_height"):
            lines.append(f"| **Max Height** | **{zd['max_height']} ft** |")
        if zd.get("max_height_near_residential"):
            lines.append(f"| Max Height (near Res) | {zd['max_height_near_residential']} ft |")

        lines.append("")
        if zd.get("notes"):
            lines.append(f"*{zd['notes']}*")
        lines.append("")

        # Lot size check
        min_sf = zd.get("min_lot_area_sf")
        if min_sf and site_sf > 0:
            if site_sf < min_sf:
                lines.append(f"⚠️ **Site area ({fmt_num(site_sf)} sf) is below minimum ({fmt_num(min_sf)} sf)**")
            else:
                lines.append(f"✅ Site area ({fmt_num(site_sf)} sf) meets minimum ({fmt_num(min_sf)} sf)")
            lines.append("")
    elif zoning_code:
        zoning_ref = get_code_url(county, "zoning", city)
        if zoning_ref:
            lines.append(f"⚠️ Zoning district **{zoning_code}** not found in compiled data. "
                         f"Look up standards in [{zoning_ref['section']}]({zoning_ref['url']})")
        else:
            lines.append(f"⚠️ Zoning district **{zoning_code}** not found in data tables.")
        lines.append("")

    # FLUM
    flu = _zoning_agent.get_flum_standards(county, flu_code, city) if flu_code else None
    if flu:
        lines.append(f"### Future Land Use: {flu_code} — {flu['name']}")
        lines.append("")
        lines.append("| Standard | Value |")
        lines.append("|----------|-------|")
        if flu.get("max_density_du_per_acre"):
            lines.append(f"| Max Density | {flu['max_density_du_per_acre']} du/acre |")
        if flu.get("max_far"):
            lines.append(f"| Max FAR | {flu['max_far']} |")
        if flu.get("max_isratio"):
            lines.append(f"| Max IS Ratio | {flu['max_isratio'] * 100:.0f}% |")
        lines.append(f"| Compatible Zoning | {', '.join(flu.get('compatible_zoning', []))} |")
        lines.append("")

        # Density/intensity calcs
        if site_sf > 0:
            acres = site_sf / 43560
            lines.append("**Calculated Limits (based on site area):**")
            lines.append("")
            if flu.get("max_density_du_per_acre"):
                max_units = math.floor(flu["max_density_du_per_acre"] * acres)
                lines.append(f"- Max Dwelling Units: **{max_units} du** ({flu['max_density_du_per_acre']} du/ac × {acres:.3f} ac)")
            if flu.get("max_far"):
                max_bldg = math.floor(flu["max_far"] * site_sf)
                lines.append(f"- Max Building Area: **{fmt_num(max_bldg)} sf** (FAR {flu['max_far']} × {fmt_num(site_sf)} sf)")
            if flu.get("max_isratio"):
                max_imperv = math.floor(flu["max_isratio"] * site_sf)
                lines.append(f"- Max Impervious: **{fmt_num(max_imperv)} sf** ({flu['max_isratio'] * 100:.0f}% × {fmt_num(site_sf)} sf)")
            lines.append("")

        # Compatibility check
        if zoning_code and flu.get("compatible_zoning"):
            compat = _zoning_agent.check_compatibility(county, zoning_code, flu_code, city)
            if compat.get("compatible"):
                lines.append(f"✅ Zoning **{zoning_code}** is consistent with FLU **{flu_code}**")
            else:
                lines.append(f"⚠️ Zoning **{zoning_code}** may not be consistent with FLU **{flu_code}** — compatible: {', '.join(flu.get('compatible_zoning', []))}")
            lines.append("")
    elif flu_code:
        flum_ref = get_code_url(county, "flum", city)
        if flum_ref:
            lines.append(f"⚠️ FLU category **{flu_code}** not found in compiled data. "
                         f"Look up in [{flum_ref['section']}]({flum_ref['url']})")
        else:
            lines.append(f"⚠️ FLU category **{flu_code}** not found in data tables.")
        lines.append("")

    # Code references — dynamic based on jurisdiction
    city_lower = city.strip().lower()
    lines.append("---")
    lines.append("**Code References:**")
    code_urls = get_code_urls(county, city)
    if code_urls:
        jur_label = code_urls.get("label", county)
        zoning_ref = code_urls.get("zoning", {})
        flum_ref = code_urls.get("flum", {})
        refs = []
        if zoning_ref:
            refs.append(f"[{zoning_ref['section']}]({zoning_ref['url']})")
        if flum_ref:
            refs.append(f"[{flum_ref['section']}]({flum_ref['url']})")
        lines.append(f"**{jur_label}:** " + " · ".join(refs))
    else:
        jurisdiction = _zoning_agent.get_jurisdiction_name(county, city)
        lines.append(f"{jurisdiction} — Zoning Districts & Future Land Use Element")

    return "\n".join(lines)


def build_parking_markdown() -> str:
    county = state.get("county", "Pinellas")
    city = state.get("city", "")
    uses = state.get("parking_uses", [])

    if not uses or not any(r.get("use_type") for r in uses):
        return "*Add at least one proposed use type to calculate parking requirements.*"

    lines: List[str] = []
    total_required = 0
    total_ada = 0
    total_bicycle = 0
    any_error = False
    data_source = ""
    source_section = ""
    source_url = ""
    last_dims: dict = {}

    for row in uses:
        use_type = row.get("use_type", "")
        building_sf = safe_float(row.get("building_sf", ""))
        num_units = safe_int(row.get("num_units", ""))
        if not use_type:
            continue

        result = _parking_agent.calculate(county, use_type, building_sf, num_units, city=city)

        if not data_source:
            data_source = result.get("data_source", county)
            source_section = result.get("source_section", "")
            source_url = result.get("source_url", "")
            last_dims = result.get("dimensions", {})

        if "error" in result:
            lines.append(f"⚠️ **{use_type}:** {result['error']}")
            any_error = True
            continue

        unit = result.get("unit", "")
        calc_spaces = result.get("required_spaces", 0)

        lines.append(f"#### {use_type}")
        lines.append(f"**Rate:** {result['rate_description']}")
        if result.get("max_limit_description"):
            lines.append(f"**Maximum:** {result['max_limit_description']}")

        if calc_spaces == 0:
            if unit == "1,000 sf GFA":
                lines.append("*Enter building SF to calculate.*")
            else:
                lines.append(f"*Enter number of {unit}s to calculate.*")
            lines.append("")
            continue

        if unit == "1,000 sf GFA" and building_sf > 0:
            lines.append(f"Building area: **{fmt_num(building_sf)} sf GFA**")
        elif num_units > 0:
            lines.append(f"Units ({unit}): **{num_units}**")

        lines.append(f"Required: **{calc_spaces}** spaces &nbsp;|&nbsp; ADA: {result['ada_spaces']} &nbsp;|&nbsp; Bicycle: {result['bicycle_spaces']}")
        if result.get("max_spaces"):
            lines.append(f"Maximum allowed: {result['max_spaces']}")
        lines.append("")

        total_required += calc_spaces
        total_ada += result.get("ada_spaces", 0)
        total_bicycle += result.get("bicycle_spaces", 0)

    if len([r for r in uses if r.get("use_type")]) > 1 and total_required > 0:
        lines.append("---")
        lines.append("### Totals")
        lines.append("")
        lines.append("| Requirement | Spaces |")
        lines.append("|-------------|--------|")
        lines.append(f"| **Total Required Minimum** | **{total_required}** |")
        lines.append(f"| ADA Accessible (total) | {total_ada} |")
        lines.append(f"| Bicycle (total) | {total_bicycle} |")
        lines.append("")

    if total_required > 0 and last_dims:
        # Build dimensions table dynamically from data
        lines.append("**Stall Dimensions:**")
        lines.append("")
        lines.append("| Layout | Stall | Aisle (one-way) | Aisle (two-way) |")
        lines.append("|--------|-------|-----------------|-----------------|")
        for key in ("90_degree", "60_degree", "45_degree", "parallel"):
            d = last_dims.get(key)
            if not d:
                continue
            angle_label = f"{d.get('angle', '')}°" if d.get("angle") else "Parallel"
            w = d.get("stall_width", "")
            dep = d.get("stall_depth", "")
            a1 = d.get("aisle_width_one_way", "—")
            a2 = d.get("aisle_width_two_way", "—")
            stall = f"{int(w)}' × {int(dep)}'" if w and dep else "—"
            a1s = f"{int(a1)}'" if isinstance(a1, (int, float)) else a1
            a2s = f"{int(a2)}'" if isinstance(a2, (int, float)) else a2
            lines.append(f"| {angle_label} | {stall} | {a1s} | {a2s} |")
        ada = last_dims.get("accessible")
        if ada:
            stall = f"{int(ada['stall_width'])}' × {int(ada['stall_depth'])}'" if ada.get("stall_width") else "—"
            lines.append(f"| ADA | {stall} | — | — |")
        lines.append("")

        # Data source notice
        lines.append("---")
        if source_section:
            lines.append(f"**Source:** {source_section}")
        if data_source:
            lines.append(f"**Data from:** {data_source}")
        if city and not _parking_agent.has_city_data(city):
            parking_ref = get_code_url(county, "parking", city)
            lines.append("")
            if parking_ref:
                lines.append(
                    f"⚠️ *City-specific parking standards for **{city}** are not yet compiled into data tables. "
                    f"Showing **{county} County** standards as a reference. "
                    f"Verify requirements in [{parking_ref['section']}]({parking_ref['url']}).*"
                )
            else:
                lines.append(
                    f"⚠️ *City-specific parking standards for **{city}** are not yet available. "
                    f"Showing **{county} County** standards as a reference. "
                    f"Verify requirements with the city before submitting.*"
                )

    return "\n".join(lines)


def build_landscape_markdown() -> str:
    county = state.get("county", "Pinellas")
    city = state.get("city", "")
    reqs = _landscape_agent.get_requirements(county, city=city)

    if not reqs.get("available"):
        land_ref = get_code_url(county, "landscape", city)
        if land_ref:
            return (f"*Landscape data tables not yet compiled for this jurisdiction. "
                    f"Refer to [{land_ref['section']}]({land_ref['url']}) for requirements.*")
        return f"*{reqs.get('message', 'Landscape data not available for this county.')}*"

    lines: List[str] = []
    lines.append(f"### Landscape Requirements — {county} County")
    if reqs.get("code_reference"):
        lines.append(f"*{reqs['code_reference']}*")
    lines.append("")

    # Perimeter Buffers
    lines.append("#### Perimeter Buffers")
    buffer_types = reqs.get("buffer_types", {})
    for key in ("type_A", "type_B", "type_C"):
        bt = buffer_types.get(key)
        if bt:
            lines.append(f"**{bt.get('label', key)}** — Min {bt.get('min_width_ft', '?')} ft wide, "
                         f"{bt.get('trees_per_100ft', '?')} tree(s) per 100 lf")
            if bt.get("notes"):
                lines.append(f"  - {bt['notes']}")
    lines.append("")

    # Adjacency matrix
    adjacency = reqs.get("adjacency_matrix", {})
    adj_display = {k: v for k, v in adjacency.items() if not k.startswith("_")}
    if adj_display:
        lines.append("**Required Buffer by Adjacency:**")
        lines.append("")
        lines.append("| Scenario | Buffer Type |")
        lines.append("|----------|-------------|")
        for scenario, buf_type in adj_display.items():
            label = scenario.replace("_", " ").title()
            buf_label = buf_type.replace("_", " ").upper() if buf_type else "—"
            lines.append(f"| {label} | {buf_label} |")
        lines.append("")

    # Parking Lot Landscaping
    parking_lot = reqs.get("parking_lot", {})
    if parking_lot:
        lines.append("#### Parking Lot Landscaping")
        for section_key, section in parking_lot.items():
            if section_key == "code_reference":
                continue
            if isinstance(section, dict):
                rule = section.get("rule") or section.get("notes", "")
                if rule:
                    lines.append(f"- {rule}")
        lines.append("")

    # Tree Canopy
    canopy = reqs.get("tree_canopy", {})
    heritage = reqs.get("tree_canopy_heritage", {})
    if canopy or heritage:
        lines.append("#### Tree Canopy Requirements")
        if canopy.get("min_canopy_coverage_pct"):
            lines.append(f"- Min {canopy['min_canopy_coverage_pct']}% canopy coverage at {canopy.get('target_years', 15)} years")
        if canopy.get("notes"):
            lines.append(f"  - {canopy['notes']}")
        if heritage:
            lines.append(f"- **Heritage Trees** (≥{heritage.get('min_dbh_inches', 24)}\" DBH): {heritage.get('mitigation', '')}")
        lines.append("")

    # Irrigation
    irrigation = reqs.get("irrigation", {})
    if irrigation:
        lines.append("#### Irrigation")
        lines.append(f"- Required: {'Yes' if irrigation.get('required') else 'No'}")
        lines.append(f"- Type: {irrigation.get('type', 'N/A')}")
        if irrigation.get("notes"):
            lines.append(f"- {irrigation['notes']}")
        lines.append("")

    # Sight Triangles
    sight = reqs.get("sight_triangles", {})
    if sight:
        lines.append("#### Sight Triangles")
        lines.append(f"- Intersection triangle: {sight.get('intersection_sight_triangle_ft', '?')} ft")
        lines.append(f"- Driveway triangle: {sight.get('driveway_sight_triangle_ft', '?')} ft")
        lines.append(f"- Max plant height in triangle: {sight.get('max_height_in_triangle_ft', '?')} ft")
        lines.append("")

    # Plant Materials
    plant = reqs.get("plant_materials", {})
    if plant:
        lines.append("#### Plant Material Standards")
        lines.append(f"- Canopy tree minimum: {plant.get('canopy_tree_min_height_ft', '?')} ft height / {plant.get('canopy_tree_min_caliper_in', '?')}\" caliper")
        lines.append(f"- Florida-Friendly minimum: {plant.get('florida_friendly_pct', '?')}% of required plantings")
        if plant.get("invasive_species_prohibited"):
            lines.append("- Invasive species (FDEP/IFAS list) are prohibited")
        lines.append("")

    lines.append("---")
    land_ref = get_code_url(county, "landscape", city)
    if land_ref:
        lines.append(f"**Code References:** [{land_ref['section']}]({land_ref['url']})")
    else:
        lines.append("**Code References:** Verify landscape requirements with the local jurisdiction.")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# Refresh functions
# ──────────────────────────────────────────────────────────────────────

def refresh_requirements() -> None:
    if "requirements_md" in ui_refs:
        ui_refs["requirements_md"].set_content(build_requirements_markdown())


def refresh_parking() -> None:
    if "parking_md" in ui_refs:
        ui_refs["parking_md"].set_content(build_parking_markdown())


def refresh_landscape() -> None:
    if "landscape_md" in ui_refs:
        ui_refs["landscape_md"].set_content(build_landscape_markdown())


def refresh_fees() -> None:
    if "_fees_refresh" in ui_refs:
        ui_refs["_fees_refresh"]()


def refresh_all() -> None:
    refresh_requirements()
    refresh_parking()
    refresh_landscape()
    refresh_fees()


def set_field(key: str, value: Any) -> None:
    state[key] = value
    if key in ui_refs:
        if hasattr(ui_refs[key], "value") and ui_refs[key].value != value:
            ui_refs[key].value = value
            ui_refs[key].update()
    if key in ("zoning", "future_land_use", "site_area_sqft"):
        refresh_requirements()
    if key == "parking_uses":
        refresh_parking()


# ──────────────────────────────────────────────────────────────────────
# Tab renderers
# ──────────────────────────────────────────────────────────────────────

def render_tab_lookup() -> None:
    county = state.get("county", "Pinellas")
    ui.label("Property Lookup & Site Data").classes("text-h5 q-mb-md")

    with ui.row().classes("w-full items-start no-wrap gap-8"):
        # LEFT COLUMN — Lookup
        with ui.column().classes("col-6"):
            with ui.card().classes("section-card w-full"):
                ui.label("Property Lookup").classes("section-title")
                with ui.row().classes("w-full items-start no-wrap gap-4"):
                    parcel_input = labeled_input(
                        "Parcel ID",
                        value=state.get("parcel_id", ""),
                        placeholder="e.g. 19-31-17-73166-001-0010",
                        classes="col-8",
                        input_props="autocomplete=off",
                    )
                    county_input = labeled_select(
                        "County",
                        ["Pinellas", "Hillsborough", "Pasco"],
                        value=state.get("county", "Pinellas"),
                        classes="col-4 center-select",
                    )
                    ui_refs["parcel_id_input"] = parcel_input
                    ui_refs["county_input"] = county_input
                    parcel_input.on("update:model-value", lambda e: state.__setitem__("parcel_id", e.args))
                    county_input.on("update:model-value", lambda e: state.__setitem__("county", e.args))

                async def do_lookup() -> None:
                    parcel_id = (parcel_input.value or state.get("parcel_id") or "").strip()
                    county = county_input.value or state.get("county", "Pinellas")
                    state["parcel_id"] = parcel_id
                    state["county"] = county

                    if not parcel_id:
                        ui.notify("Please enter a parcel ID.", type="warning")
                        return
                    is_valid, error_msg = validate_parcel_id(parcel_id)
                    if not is_valid:
                        ui.notify(error_msg, type="negative")
                        return
                    lookup_btn.disable()
                    ui.notify("Fetching property data...", type="info")
                    if county == "Pasco":
                        result = await run.io_bound(scrape_pasco_property, parcel_id)
                    elif county == "Pinellas":
                        result = await run.io_bound(scrape_pinellas_property, parcel_id)
                    elif county == "Hillsborough":
                        result = await run.io_bound(scrape_hillsborough_property, parcel_id)
                    else:
                        lookup_btn.enable()
                        ui.notify(
                            f"Parcel lookup is not yet implemented for {county} County. "
                            "Use Pinellas, Pasco, or Hillsborough for automated parcel data, or enter fields manually.",
                            type="warning",
                            timeout=8000,
                        )
                        return
                    if not result.get("success"):
                        lookup_btn.enable()
                        ui.notify(result.get("error", "Lookup failed"), type="negative")
                        return

                    # Populate state + UI
                    field_map = {
                        "address": "address",
                        "city": "city",
                        "zip": "zip",
                        "owner": "owner",
                        "land_use": "land_use",
                        "site_area_sqft": "site_area_sqft",
                        "site_area_acres": "site_area_acres",
                        "adjoining_uses": "adjoining_uses",
                    }
                    for state_key, result_key in field_map.items():
                        val = result.get(result_key, "") or ""
                        state[state_key] = val
                        if state_key in ui_refs:
                            ui_refs[state_key].value = val
                            ui_refs[state_key].update()

                    # Persist parcel-derived coordinates for downstream spatial lookups.
                    state["lat"] = result.get("lat")
                    state["lon"] = result.get("lon")

                    # Auto-fill Tax Parcel ID from lookup result
                    pid_val = result.get("parcel_id", "") or ""
                    if pid_val:
                        state["tax_parcel"] = pid_val
                        if "tax_parcel" in ui_refs:
                            ui_refs["tax_parcel"].value = pid_val
                            ui_refs["tax_parcel"].update()

                    # For Pinellas, fetch adjacent uses if scraper did not already provide them.
                    if county == "Pinellas" and parcel_id and not state.get("adjoining_uses"):
                        try:
                            ui.notify("Fetching adjacent parcel data...", type="info")
                            adj = await run.io_bound(get_pinellas_adjacent_uses, parcel_id)
                            if adj:
                                state["adjoining_uses"] = adj
                                if "adjoining_uses" in ui_refs:
                                    ui_refs["adjoining_uses"].value = adj
                                    ui_refs["adjoining_uses"].update()
                        except Exception:
                            pass  # Adjacent lookup is best-effort

                    # Expand city abbreviation only for Pinellas tax-district values.
                    raw_city = result.get("city", "") or ""
                    if county == "Pinellas":
                        state["city"] = expand_city_name(raw_city)
                    else:
                        state["city"] = raw_city
                    if "city" in ui_refs:
                        ui_refs["city"].value = state["city"]
                        ui_refs["city"].update()

                    # Enrich land use with official DOR description
                    raw_land_use = result.get("land_use", "") or ""
                    enriched = lookup_dor_use_code(raw_land_use)
                    state["land_use"] = enriched
                    if "land_use" in ui_refs:
                        ui_refs["land_use"].value = enriched
                        ui_refs["land_use"].update()

                    # Auto-populate zoning + FLUM when the parcel scraper returns spatial codes.
                    if county in ("Pasco", "Hillsborough"):
                        zoning_val = result.get("zoning", "") or ""
                        flu_val = result.get("future_land_use", "") or ""
                        zoning_desc = result.get("zoning_description", "") or ""
                        flum_desc = result.get("flum_description", "") or ""
                        if zoning_val:
                            set_field("zoning", zoning_val)
                            if "zoning_select" in ui_refs:
                                zoning_display = f"{zoning_val} — {zoning_desc}" if zoning_desc else zoning_val
                                ui_refs["zoning_select"].value = zoning_display
                                ui_refs["zoning_select"].update()
                        if flu_val:
                            set_field("future_land_use", flu_val)
                            if "flu_select" in ui_refs:
                                flu_display = f"{flu_val} — {flum_desc}" if flum_desc else flu_val
                                ui_refs["flu_select"].value = flu_display
                                ui_refs["flu_select"].update()
                        label_parts = []
                        if zoning_val:
                            label_parts.append(f"Zoning: {zoning_val}" + (f" — {zoning_desc}" if zoning_desc else ""))
                        if flu_val:
                            label_parts.append(f"FLU: {flu_val}" + (f" — {flum_desc}" if flum_desc else ""))
                        if "zoning_city_label" in ui_refs:
                            ui_refs["zoning_city_label"].text = " · ".join(label_parts) if label_parts else "Zoning/FLU not found for this parcel."
                            ui_refs["zoning_city_label"].update()
                    else:
                        if "zoning_city_label" in ui_refs:
                            detected_city = state.get("city", "")
                            code_entry = get_code_urls(county, detected_city)
                            if code_entry:
                                jur_label = code_entry.get("label", detected_city)
                                ui_refs["zoning_city_label"].text = (
                                    f"City detected: {detected_city} ({jur_label}) — "
                                    "open the zoning map above, find the zoning code, then enter it below."
                                )
                            else:
                                ui_refs["zoning_city_label"].text = (
                                    f"City detected: {detected_city} — open the zoning map above, "
                                    "find the zoning code, then enter it below."
                                )
                            ui_refs["zoning_city_label"].update()

                    # Populate code reference links
                    ref_container = ui_refs.get("_code_refs_row")
                    if ref_container is not None:
                        detected_city = state.get("city", "")
                        code_entry = get_code_urls(county, detected_city)
                        ref_container.clear()
                        with ref_container:
                            if code_entry:
                                jur_label = code_entry.get("label", county)
                                ui.label(f"{jur_label} — Land Development Code:").classes("text-weight-bold text-caption")
                                for topic, icon in [("zoning", "gavel"), ("parking", "local_parking"),
                                                     ("landscape", "park"), ("flum", "map")]:
                                    ref = code_entry.get(topic)
                                    if ref:
                                        ui.button(
                                            ref["section"],
                                            on_click=lambda _, u=ref["url"]: ui.navigate.to(u, new_tab=True),
                                            icon=icon,
                                        ).props("outline dense").classes("link-btn")
                            else:
                                ui.label("No LDC references available for this jurisdiction.").classes("muted")

                    refresh_all()
                    ui.notify("Property data retrieved.", type="positive")

                    # Auto-run infrastructure lookup using the resolved address + city
                    ui.notify("Fetching infrastructure data...", type="info")
                    infra_result = await run.io_bound(
                        _infra_agent.lookup,
                        state.get("address", ""),
                        state.get("city", ""),
                        state.get("zip", ""),
                        state.get("county", "Pinellas"),
                        state.get("lat"),
                        state.get("lon"),
                    )
                    if not infra_result.get("error"):
                        for key, value in infra_result.items():
                            if key == "error" or not value:
                                continue
                            state[key] = value
                            ref = ui_refs.get(key)
                            if ref is not None and hasattr(ref, "value"):
                                ref.value = value
                                ref.update()
                        ui.notify("Infrastructure data populated.", type="positive")

                    # Auto-run environmental lookup
                    ui.notify("Fetching environmental data...", type="info")
                    env_result = await run.io_bound(
                        _env_agent.lookup,
                        state.get("address", ""),
                        state.get("city", ""),
                        state.get("zip", ""),
                        state.get("county", "Pinellas"),
                        state.get("lat"),
                        state.get("lon"),
                    )
                    flood_zone = env_result.pop("_flood_zone", "")
                    if not env_result.get("error"):
                        for key, value in env_result.items():
                            if key == "error" or not value:
                                continue
                            state[key] = value
                            ref = ui_refs.get(key)
                            if ref is not None and hasattr(ref, "value"):
                                ref.value = value
                                ref.update()
                        zone_msg = f" (FEMA Zone {flood_zone})" if flood_zone else ""
                        ui.notify(f"Environmental data populated{zone_msg}.", type="positive")

                    # Populate Quick Links
                    links_row_ref = ui_refs.get("_links_row")
                    if links_row_ref is not None:
                        links_row_ref.clear()
                        parcel_links = _build_parcel_links(
                            county,
                            parcel_id,
                            state.get("address", ""),
                            state.get("city", ""),
                        )
                        with links_row_ref:
                            for lnk in parcel_links:
                                ui.button(
                                    lnk["label"],
                                    on_click=lambda _, u=lnk["url"]: ui.navigate.to(u, new_tab=True),
                                    icon="open_in_new",
                                ).props("outline dense").classes("link-btn")
                    lookup_btn.enable()

                lookup_btn = ui.button("LOOKUP PROPERTY DATA", color="primary").classes("q-mt-md w-full")
                lookup_btn.on_click(do_lookup)

            # Lookup summary
            with ui.card().classes("section-card q-mt-md w-full"):
                ui.label("Lookup Summary").classes("section-title")
                ui_refs["address"] = labeled_input("Address", value=state.get("address", ""), classes="lookup-field")
                ui_refs["city"] = labeled_input("City / Municipality", value=state.get("city", ""), classes="lookup-field")
                ui_refs["zip"] = labeled_input("Zip", value=state.get("zip", ""), classes="lookup-field")
                ui_refs["owner"] = labeled_input("Owner", value=state.get("owner", ""), classes="lookup-field")
                ui_refs["land_use"] = labeled_input("Land Use (DOR)", value=state.get("land_use", ""), classes="lookup-field")
                ui_refs["site_area_acres"] = labeled_input("Site Area (acres)", value=state.get("site_area_acres", ""), classes="lookup-field")
                ui_refs["site_area_sqft"] = labeled_input("Site Area (sf)", value=state.get("site_area_sqft", ""), classes="lookup-field")

                for key in ("address", "city", "zip", "owner", "land_use", "site_area_acres", "site_area_sqft"):
                    ui_refs[key].on("update:model-value", lambda e, k=key: set_field(k, e.args))

            # Site description (SIR manual fields)
            with ui.card().classes("section-card q-mt-md w-full"):
                ui.label("Site Description").classes("section-title")
                ui_refs["tax_parcel"] = labeled_input("Tax Parcel ID(s)", value=state.get("tax_parcel", ""), placeholder="e.g. 24-31-16-53478-000-0210", classes="lookup-field")
                ui_refs["site_views"] = labeled_input("Description of Site Views", value=state.get("site_views", ""), placeholder="e.g. Construction bordering left, storefront north", classes="lookup-field")
                ui_refs["adjoining_uses"] = labeled_input("Adjoining Property Uses and Zoning", value=state.get("adjoining_uses", ""), placeholder="e.g. Zoning: DC-1, Uses: Retail", classes="lookup-field")
                ui_refs["proposed_zoning"] = labeled_input("Proposed Zoning / Designation", value=state.get("proposed_zoning", ""), placeholder="e.g. CBD", classes="lookup-field")
                for key in ("tax_parcel", "site_views", "adjoining_uses", "proposed_zoning"):
                    ui_refs[key].on("update:model-value", lambda e, k=key: set_field(k, e.args))

            # Quick Links — populated after lookup
            with ui.card().classes("section-card q-mt-md w-full"):
                ui.label("Quick Links").classes("section-title")
                links_row = ui.row().classes("w-full flex-wrap gap-2 q-mt-xs")
                ui_refs["_links_row"] = links_row
                with links_row:
                    ui.label("Look up a parcel to generate links.").classes("muted")
        with ui.column().classes("col-6"):
            with ui.card().classes("section-card w-full"):
                ui.label("Zoning & Land Use").classes("section-title")
                ui.label(
                    "After looking up a parcel, open the zoning map for the detected city. "
                    "Find the zoning code on the map and type it in below — "
                    "the requirements tabs will populate automatically."
                ).classes("muted q-mb-sm")

                zoning_city_label = ui.label("Look up a parcel first to detect the city.").classes("text-caption text-italic q-mb-sm")
                ui_refs["zoning_city_label"] = zoning_city_label

                def open_zoning_map() -> None:
                    city = state.get("city", "").strip()
                    address = state.get("address", "").strip()
                    zip_code = state.get("zip", "").strip()
                    if not city:
                        ui.notify("Look up a property first to detect the city.", type="warning")
                        return
                    map_url = get_zoning_map_url(city, address, zip_code)
                    if map_url:
                        ui.navigate.to(map_url, new_tab=True)
                    else:
                        ui.notify(f"No zoning map URL available for {city}.", type="warning")

                ui.button("OPEN ZONING MAP", on_click=open_zoning_map, icon="map").classes("q-mb-md w-full")

                def on_zoning_changed(e) -> None:
                    raw = (e.value or "").strip()
                    code = raw.split(" — ")[0].strip()  # strip display suffix e.g. "MPUD — Name" → "MPUD"
                    set_field("zoning", code)
                    if code:
                        refresh_all()

                zoning_input = labeled_input(
                    "Zoning District",
                    value=state.get("zoning", ""),
                    placeholder="e.g. NT-1, CC-2, CG, DC-1 ...",
                    classes="code-field",
                )
                zoning_input.on_value_change(on_zoning_changed)
                ui_refs["zoning_select"] = zoning_input  # alias kept for run_analysis() compatibility

                flu_input = labeled_input(
                    "Future Land Use (FLUM)",
                    value=state.get("future_land_use", ""),
                    placeholder="e.g. CMU, RES-1, NC, R-6 ...",
                    classes="code-field",
                )
                flu_input.on_value_change(lambda e: set_field("future_land_use", (e.value or "").split(" — ")[0].strip()))
                ui_refs["flu_select"] = flu_input  # alias kept for run_analysis() compatibility

                # Code reference links — populated after parcel lookup
                code_refs_row = ui.row().classes("w-full flex-wrap gap-2 q-mt-md")
                ui_refs["_code_refs_row"] = code_refs_row
                with code_refs_row:
                    ui.label("Look up a parcel to see LDC code references.").classes("muted")



            with ui.card().classes("section-card q-mt-md w-full"):
                def run_analysis() -> None:
                    # Always read from the UI elements so a freshly-typed value is picked up
                    raw_z = (ui_refs["zoning_select"].value if "zoning_select" in ui_refs else "") or ""
                    raw_f = (ui_refs["flu_select"].value if "flu_select" in ui_refs else "") or ""
                    zoning = raw_z.split(" — ")[0].strip()
                    flu = raw_f.split(" — ")[0].strip()
                    if not zoning and not flu:
                        ui.notify("Set Zoning District and/or Future Land Use first.", type="warning")
                        return
                    # Sync UI values into state
                    state["zoning"] = zoning
                    state["future_land_use"] = flu
                    refresh_all()
                    tabs.set_value(tab2)
                    ui.notify("Analysis complete — see Requirements, Parking, and Landscape tabs.", type="positive")

                ui.button("RUN CODE ANALYSIS", on_click=run_analysis, color="primary").classes("w-full")
                ui.label("Pulls all zoning, FLU, parking, and landscape requirements from code.").classes("muted q-mt-xs")


def render_tab_requirements() -> None:
    ui.label("Development Requirements").classes("text-h5 q-mb-md")
    with ui.card().classes("section-card w-full"):
        md = ui.markdown(build_requirements_markdown()).classes("q-mt-sm")
        ui_refs["requirements_md"] = md


def render_tab_parking() -> None:
    county = state.get("county", "Pinellas")
    city = state.get("city", "")
    ui.label("Parking Analysis").classes("text-h5 q-mb-md")

    with ui.card().classes("section-card w-full"):
        ui.label("Parking Input").classes("section-title")
        ui.label("Add one row per use type. For a PUD with multiple uses, add each separately.").classes("muted q-mb-sm")

        use_options = _parking_agent.get_use_type_options(county, city=city)

        parking_rows_container = ui.column().classes("w-full gap-2")

        def _render_parking_rows() -> None:
            parking_rows_container.clear()
            uses = state.get("parking_uses", [])
            with parking_rows_container:
                for idx, row in enumerate(uses):
                    with ui.row().classes("w-full items-end no-wrap gap-2"):
                        with ui.column().classes("col-5"):
                            ui.label("Use Type").classes("text-caption text-grey-7")
                            ui.select(
                                use_options,
                                value=row.get("use_type") or None,
                                with_input=True,
                                on_change=lambda e, i=idx: (
                                    state["parking_uses"].__setitem__(i, {**state["parking_uses"][i], "use_type": e.value or ""}),
                                    refresh_parking(),
                                ),
                            ).classes("w-full")

                        with ui.column().classes("col-3"):
                            ui.label("Building SF GFA").classes("text-caption text-grey-7")
                            ui.input(
                                placeholder="e.g. 15000",
                                value=row.get("building_sf", ""),
                                on_change=lambda e, i=idx: (
                                    state["parking_uses"].__setitem__(i, {**state["parking_uses"][i], "building_sf": e.value or ""}),
                                    refresh_parking(),
                                ),
                            ).classes("w-full")

                        with ui.column().classes("col-3"):
                            ui.label("Units / Seats / Beds").classes("text-caption text-grey-7")
                            ui.input(
                                placeholder="e.g. 24",
                                value=row.get("num_units", ""),
                                on_change=lambda e, i=idx: (
                                    state["parking_uses"].__setitem__(i, {**state["parking_uses"][i], "num_units": e.value or ""}),
                                    refresh_parking(),
                                ),
                            ).classes("w-full")

                        with ui.column().classes("col-1 items-center"):
                            ui.label("").classes("text-caption")
                            def _remove_row(i=idx) -> None:
                                state["parking_uses"].pop(i)
                                _render_parking_rows()
                                refresh_parking()

                            ui.button(icon="delete", on_click=_remove_row).props("flat round dense color=negative")

        def _add_parking_row() -> None:
            state["parking_uses"].append({"use_type": "", "building_sf": "", "num_units": ""})
            _render_parking_rows()

        if not state.get("parking_uses"):
            state["parking_uses"] = [{"use_type": "", "building_sf": "", "num_units": ""}]
        _render_parking_rows()

        with ui.row().classes("q-mt-sm gap-2"):
            ui.button("+ ADD USE", on_click=_add_parking_row, icon="add").props("outline")
            ui.button("CALCULATE PARKING", on_click=refresh_parking, color="primary").props("icon=calculate")

    with ui.card().classes("section-card q-mt-md w-full"):
        md = ui.markdown(build_parking_markdown()).classes("q-mt-sm")
        ui_refs["parking_md"] = md


def render_tab_landscape() -> None:
    ui.label("Landscape Requirements").classes("text-h5 q-mb-md")
    with ui.card().classes("section-card w-full"):
        md = ui.markdown(build_landscape_markdown()).classes("q-mt-sm")
        ui_refs["landscape_md"] = md


def _sir_textarea(label: str, key: str) -> None:
    """Helper: labeled textarea wired to state — uses same pattern as labeled_input."""
    with ui.column().classes("w-full q-mt-sm"):
        ui.label(label).classes("field-label")
        inp = ui.textarea(value=state.get(key, "")).props("outlined rows=5").classes("w-full sir-textarea")
        inp.on("update:model-value", lambda e, k=key: state.__setitem__(k, e.args))
        ui_refs[key] = inp


def _sir_input(label: str, key: str, placeholder: str = "") -> None:
    """Helper: labeled single-line input wired to state — uses same pattern as labeled_input."""
    with ui.column().classes("w-full q-mt-sm"):
        ui.label(label).classes("field-label")
        inp = ui.input(value=state.get(key, ""), placeholder=placeholder).props("outlined dense").classes("w-full")
        inp.on("update:model-value", lambda e, k=key: state.__setitem__(k, e.args))
        ui_refs[key] = inp


def render_tab_infrastructure() -> None:
    ui.label("Infrastructure & Utilities").classes("text-h5 q-mb-md")

    with ui.row().classes("w-full items-center gap-4 q-mb-md"):
        infra_status = ui.label("").classes("muted")

        def do_infra_lookup() -> None:
            address = state.get("address", "").strip()
            city = state.get("city", "").strip()
            zip_code = state.get("zip", "").strip()
            county = state.get("county", "Pinellas")
            lat = state.get("lat")
            lon = state.get("lon")

            if not address:
                ui.notify("Look up a property first to populate the address.", type="warning")
                return

            infra_status.text = "Querying GIS services…"
            infra_status.update()

            result = _infra_agent.lookup(address, city, zip_code, county, lat, lon)

            if result.get("error"):
                ui.notify(result["error"], type="negative")
                infra_status.text = result["error"]
                infra_status.update()
                return

            populated = []
            for key, value in result.items():
                if key == "error" or not value:
                    continue
                state[key] = value
                ref = ui_refs.get(key)
                if ref is not None and hasattr(ref, "value"):
                    ref.value = value
                    ref.update()
                populated.append(key)

            count = len(populated)
            if count:
                ui.notify(f"Infrastructure data populated — {count} fields filled.", type="positive")
                infra_status.text = f"Auto-fill complete: {count} fields populated from {state.get('county', 'County')} GIS."
            else:
                ui.notify("No data returned from GIS services. Try looking up the property first.", type="warning")
                infra_status.text = "No data returned."
            infra_status.update()

        ui.button("LOOKUP INFRASTRUCTURE", on_click=do_infra_lookup).props("icon=search")
        ui.label("Populates utilities, roads, and easements from the county GIS based on the looked-up parcel.").classes("muted")

    with ui.row().classes("w-full items-start no-wrap gap-8"):
        with ui.column().classes("col-6"):
            with ui.card().classes("section-card w-full"):
                ui.label("Public / Private Utilities").classes("section-title")
                _sir_input("Water Provider", "utilities_water", "e.g. City of St. Petersburg")
                _sir_input("Reclaimed Water Provider", "utilities_reclaim", "e.g. City of St. Petersburg")
                _sir_input("Sanitary Sewer Provider", "utilities_sewer", "e.g. City of St. Petersburg")
                _sir_input("Stormwater / Drainage", "utilities_storm", "e.g. City of St. Petersburg")
                _sir_input("Gas Provider", "utilities_gas", "e.g. TECO Peoples Gas")
                _sir_input("Electric Provider", "utilities_electric", "e.g. Duke Energy Florida")

            with ui.card().classes("section-card q-mt-md w-full"):
                ui.label("Easements & Extensions").classes("section-title")
                _sir_textarea("Easements Required", "easements_required")
                _sir_textarea("Utility Extensions Required", "utility_extensions")

            with ui.card().classes("section-card q-mt-md w-full"):
                ui.label("Subdivision").classes("section-title")
                _sir_textarea("Platting / Subdivision Requirements", "platting")
                _sir_textarea("Anticipated Takings / Easements", "takings_easements")

        with ui.column().classes("col-6"):
            with ui.card().classes("section-card w-full"):
                ui.label("Roadway & Access").classes("section-title")
                _sir_textarea("Anticipated Roadway Improvements / ROW Dedication", "roadway_improvements")
                _sir_input("Signalization Required", "signalization", "e.g. N/A")
                _sir_textarea("Potential Encroachments", "encroachments")
                _sir_textarea("Additional Access Available", "additional_access")


def render_tab_environmental() -> None:
    ui.label("Environmental").classes("text-h5 q-mb-md")

    with ui.row().classes("w-full items-center gap-4 q-mb-md"):
        env_status = ui.label("").classes("muted")

        def do_env_lookup() -> None:
            address = state.get("address", "").strip()
            city = state.get("city", "").strip()
            zip_code = state.get("zip", "").strip()
            county = state.get("county", "Pinellas")
            lat = state.get("lat")
            lon = state.get("lon")
            if not address:
                ui.notify("Look up a property first to populate the address.", type="warning")
                return
            env_status.text = f"Querying FEMA and {county} County GIS..."
            env_status.update()
            result = _env_agent.lookup(address, city, zip_code, county, lat, lon)
            flood_zone = result.pop("_flood_zone", "")
            if result.get("error"):
                ui.notify(result["error"], type="negative")
                env_status.text = result["error"]
                env_status.update()
                return
            populated = []
            for key, value in result.items():
                if key == "error" or not value:
                    continue
                state[key] = value
                ref = ui_refs.get(key)
                if ref is not None and hasattr(ref, "value"):
                    ref.value = value
                    ref.update()
                populated.append(key)
            zone_msg = f" — FEMA Zone {flood_zone}" if flood_zone else ""
            env_status.text = f"Auto-fill complete: {len(populated)} fields populated{zone_msg}."
            env_status.update()
            ui.notify(f"Environmental data populated{zone_msg}.", type="positive")

        ui.button("LOOKUP ENVIRONMENTAL", on_click=do_env_lookup).props("icon=nature")
        ui.label("Queries FEMA flood zones, CCCL proximity, and applies county-specific FL standards.").classes("muted")

    with ui.row().classes("w-full items-start no-wrap gap-8"):
        with ui.column().classes("col-6"):
            with ui.card().classes("section-card w-full"):
                ui.label("Stormwater & Flooding").classes("section-title")
                _sir_textarea("Storm Water Treatment Requirements", "stormwater_treatment")
                _sir_textarea("Wetlands or Flood Plains Present", "wetlands_flood")
                _sir_textarea("Setback / Elevation for Flood Plain", "flood_elevation")

            with ui.card().classes("section-card q-mt-md w-full"):
                ui.label("Studies & Impact").classes("section-title")
                _sir_input("Impact Studies Required", "impact_studies", "e.g. N/A or Traffic, NRA")
                _sir_input("Traffic Study Required", "traffic_study", "e.g. Not included")

        with ui.column().classes("col-6"):
            with ui.card().classes("section-card w-full"):
                ui.label("Resources & Conditions").classes("section-title")
                _sir_textarea("Natural or Cultural Resources", "natural_cultural")
                _sir_textarea("Environmental Considerations", "env_considerations")
                _sir_textarea("Geotechnical Considerations", "geotechnical")

            with ui.card().classes("section-card q-mt-md w-full"):
                ui.label("Building").classes("section-title")
                _sir_input("Current Building Code", "building_code", "e.g. Florida Building Code")
                _sir_textarea("Unique Construction Methods (Sinkholes, Piles, CHHA, etc.)", "construction_methods")
                _sir_input("Fire Route Considerations", "fire_route", "e.g. N/A")


def _load_fees_data(county: str, city: str = "") -> tuple:
    """Load fees.json for the jurisdiction. Tries city-specific first, falls back to county.

    Returns (fees_dict, source_label) where source_label describes which
    jurisdiction the fees came from.
    """
    import json, pathlib
    from agents import city_slug as _cs

    # Try city-specific first
    if city:
        slug = _cs(city)
        if slug:
            path = pathlib.Path(__file__).parent / "data" / slug / "fees.json"
            if path.exists():
                try:
                    return json.loads(path.read_text(encoding="utf-8")), city
                except Exception:
                    pass

    # Fall back to county
    path = pathlib.Path(__file__).parent / "data" / county.lower() / "fees.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            label = f"{county} County"
            if city:
                label += f" (no city-specific fee data for {city})"
            return data, label
        except Exception:
            return {}, county
    return {}, county


def build_fees_schedule_text() -> str:
    """Build a plain-text summary of the Fees & Schedule tab for Excel export."""
    county = state.get("county", "Pinellas")
    city = state.get("city", "")
    fees, data_label = _load_fees_data(county, city)

    if not fees:
        if city:
            return f"No fee data available for {city} or {county} County."
        return f"No fee data available for {county} County."

    lines: List[str] = [f"Showing fees for: {data_label}"]
    source = fees.get("_source", "")
    note = fees.get("_note", "")
    if source:
        lines.append(f"Source: {source}")
    if note:
        lines.append(f"Note: {note}")

    for key in fees.get("_sections", list(FEE_SECTION_LABELS.keys())):
        label = FEE_SECTION_LABELS.get(key, key.replace("_", " ").title())
        content = (fees.get(key) or "").strip()
        if not content:
            continue
        lines.append("")
        lines.append(f"{label}:")
        for line in content.split("\n"):
            line = line.strip()
            if line:
                lines.append(f"- {line}")

    return "\n".join(lines)


def render_tab_fees_schedule() -> None:
    county = state.get("county", "Pinellas")
    city = state.get("city", "")
    ui.label("Fees & Schedule").classes("text-h5 q-mb-md")

    # Scrollable results area
    results_area = ui.column().classes("w-full gap-2")

    def do_fetch_fees() -> None:
        current_county = state.get("county", "Pinellas")
        current_city = state.get("city", "")
        fees, data_label = _load_fees_data(current_county, current_city)
        results_area.clear()

        if not fees:
            with results_area:
                msg = f"No fee data available for {current_county} County"
                if current_city:
                    msg = f"No fee data available for {current_city} or {current_county} County"
                ui.label(msg + ".").classes("muted")
            return

        source = fees.get("_source", "")
        note = fees.get("_note", "")

        with results_area:
            # Show which jurisdiction's fees are displayed
            ui.label(f"Showing fees for: {data_label}").classes("text-weight-bold text-primary q-mb-xs")
            if source:
                ui.label(f"Source: {source}").classes("muted text-caption")
            if note:
                ui.label(f"Note: {note}").classes("muted text-caption q-mb-sm")

            for key in fees.get("_sections", list(FEE_SECTION_LABELS.keys())):
                label = FEE_SECTION_LABELS.get(key, key.replace("_", " ").title())
                content = fees.get(key, "")
                if not content:
                    continue
                with ui.expansion(label, icon="attach_money").classes("w-full fee-expansion"):
                    for line in content.strip().split("\n"):
                        line = line.strip()
                        if not line:
                            continue
                        if line.endswith(":") or (line.startswith("  —") is False and ":" not in line and len(line) < 60):
                            ui.label(line).classes("text-weight-bold q-mt-xs")
                        else:
                            ui.label(line).classes("fee-line")

    # Auto-load on tab open and store callback for refresh
    ui_refs["_fees_refresh"] = do_fetch_fees
    if state.get("county"):
        do_fetch_fees()


# ──────────────────────────────────────────────────────────────────────
# Excel export
# ──────────────────────────────────────────────────────────────────────

def generate_excel_report() -> None:
    """Export all current state fields to a formatted .xlsx file."""
    import pathlib
    from datetime import datetime

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        ui.notify("openpyxl not installed — run: pip install openpyxl", type="negative")
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Site Data Report"

    def _excel_safe(value: Any, max_len: int = 32000) -> str:
        """Return text safe for Excel cells (strip control chars, cap length)."""
        if value is None:
            return ""
        s = str(value)
        # Excel/openpyxl rejects most ASCII control chars except tab/newline/carriage return.
        s = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", s)
        if len(s) > max_len:
            s = s[:max_len] + "\n... [truncated]"
        return s

    # ── Column widths ──
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 58

    # ── Styles ──
    _hdr_font    = Font(name="Calibri", bold=True, size=13, color="FFFFFF")
    _hdr_fill    = PatternFill("solid", fgColor="0B1F3A")
    _sec_font    = Font(name="Calibri", bold=True, size=10, color="FFFFFF")
    _sec_fill    = PatternFill("solid", fgColor="1B3A6B")
    _lbl_font    = Font(name="Calibri", bold=True, size=10, color="101820")
    _val_font    = Font(name="Calibri", size=10, color="2C3E50")
    _thin_side   = Side(style="thin", color="C9D3E1")
    _btm_border  = Border(bottom=_thin_side)
    _wrap_top    = Alignment(wrap_text=True, vertical="top")
    _center      = Alignment(horizontal="center", vertical="center")

    _row = [1]  # mutable counter

    def _next() -> int:
        r = _row[0]; _row[0] += 1; return r

    def write_header(text: str) -> None:
        r = _next()
        ws.row_dimensions[r].height = 22
        for col in (1, 2):
            c = ws.cell(row=r, column=col)
            c.fill = _hdr_fill
        ca = ws.cell(row=r, column=1, value=text)
        ca.font = _hdr_font
        ca.alignment = _center

    def write_section(text: str) -> None:
        _next()  # blank spacer row
        r = _next()
        ws.row_dimensions[r].height = 16
        for col in (1, 2):
            c = ws.cell(row=r, column=col)
            c.fill = _sec_fill
        ca = ws.cell(row=r, column=1, value=text)
        ca.font = _sec_font

    def write_field(label: str, value: Any) -> None:
        r = _next()
        safe_label = _excel_safe(label, max_len=200)
        safe_value = _excel_safe(value)
        ca = ws.cell(row=r, column=1, value=safe_label)
        ca.font = _lbl_font
        ca.border = _btm_border
        cb = ws.cell(row=r, column=2, value=safe_value)
        cb.font = _val_font
        cb.border = _btm_border
        cb.alignment = _wrap_top
        if safe_value and "\n" in safe_value:
            ws.row_dimensions[r].height = max(15, safe_value.count("\n") * 15 + 15)

    def _clean_md(text: str) -> str:
        """Convert markdown-ish text into readable plain text for Excel."""
        if not text:
            return ""
        t = str(text)
        t = t.replace("&nbsp;|&nbsp;", " | ")
        t = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", r"\1 (\2)", t)
        t = t.replace("**", "").replace("*", "")
        return _excel_safe(t)

    def write_analysis_sheet(sheet_name: str, title: str, content: str) -> None:
        """Write auto-generated tab output to a dedicated worksheet."""
        aws = wb.create_sheet(sheet_name[:31])
        aws.column_dimensions["A"].width = 3
        aws.column_dimensions["B"].width = 165

        # Header
        aws.merge_cells("A1:B1")
        hc = aws.cell(row=1, column=1, value=title)
        hc.font = _hdr_font
        hc.fill = _hdr_fill
        hc.alignment = _center

        # Context row
        aws.merge_cells("A2:B2")
        ctx = aws.cell(
            row=2,
            column=1,
            value=_excel_safe(f"County: {state.get('county', '')}    City: {state.get('city', '')}    Parcel: {state.get('parcel_id', '')}"),
        )
        ctx.font = Font(name="Calibri", size=10, color="2C3E50")
        ctx.fill = PatternFill("solid", fgColor="EAF0F8")
        ctx.alignment = Alignment(horizontal="left", vertical="center")

        r = 4
        for raw in _clean_md(content).splitlines():
            line = raw.strip()
            if not line or line == "---":
                r += 1
                continue

            font = Font(name="Calibri", size=10, color="2C3E50")
            if line.startswith("### "):
                line = line[4:].strip()
                font = Font(name="Calibri", bold=True, size=12, color="0B1F3A")
            elif line.startswith("#### "):
                line = line[5:].strip()
                font = Font(name="Calibri", bold=True, size=11, color="1B3A6B")

            cell = aws.cell(row=r, column=2, value=_excel_safe(line))
            cell.font = font
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            line_count = max(1, line.count("\n") + (len(line) // 120))
            aws.row_dimensions[r].height = max(18, 15 * line_count)
            r += 1

    # ── Report header ──
    write_header("DEVELOPMENT CODE LOOKUP REPORT")
    write_field("Generated", datetime.now().strftime("%Y-%m-%d  %H:%M"))
    write_field("County", state.get("county", ""))
    write_field("Parcel ID", state.get("parcel_id", ""))

    # ── Property Data ──
    write_section("PROPERTY DATA")
    write_field("Address", state.get("address", ""))
    write_field("City / Municipality", state.get("city", ""))
    write_field("Zip Code", state.get("zip", ""))
    write_field("Owner", state.get("owner", ""))
    write_field("Land Use (DOR)", state.get("land_use", ""))
    write_field("Site Area (acres)", state.get("site_area_acres", ""))
    write_field("Site Area (sf)", state.get("site_area_sqft", ""))

    # ── Site Description ──
    write_section("SITE DESCRIPTION")
    write_field("Tax Parcel ID(s)", state.get("tax_parcel", ""))
    write_field("Description of Site Views", state.get("site_views", ""))
    write_field("Adjoining Property Uses and Zoning", state.get("adjoining_uses", ""))
    write_field("Proposed Zoning / Designation", state.get("proposed_zoning", ""))

    # ── Zoning & Land Use ──
    write_section("ZONING & LAND USE")
    write_field("Zoning District", state.get("zoning", ""))
    write_field("Future Land Use (FLUM)", state.get("future_land_use", ""))

    # ── Parking ──
    write_section("PARKING")
    parking_uses = state.get("parking_uses", [])
    if parking_uses:
        for i, row in enumerate(parking_uses, 1):
            use_type = row.get("use_type", "")
            if not use_type:
                continue
            prefix = f"Use {i}: {use_type}"
            write_field(prefix + " — Building SF GFA", row.get("building_sf", ""))
            write_field(prefix + " — Units / Seats / Beds", row.get("num_units", ""))
    else:
        write_field("Proposed Use Type", state.get("use_type", ""))
        write_field("Building Area (SF GFA)", state.get("building_sf", ""))
        write_field("Number of Units / Seats / Beds", state.get("num_units", ""))

    # ── Infrastructure & Utilities ──
    write_section("INFRASTRUCTURE & UTILITIES")
    write_field("Water Provider", state.get("utilities_water", ""))
    write_field("Reclaimed Water Provider", state.get("utilities_reclaim", ""))
    write_field("Sanitary Sewer Provider", state.get("utilities_sewer", ""))
    write_field("Stormwater / Drainage", state.get("utilities_storm", ""))
    write_field("Gas Provider", state.get("utilities_gas", ""))
    write_field("Electric Provider", state.get("utilities_electric", ""))
    write_field("Easements Required", state.get("easements_required", ""))
    write_field("Utility Extensions Required", state.get("utility_extensions", ""))
    write_field("Roadway Improvements / ROW Dedication", state.get("roadway_improvements", ""))
    write_field("Signalization Required", state.get("signalization", ""))
    write_field("Potential Encroachments", state.get("encroachments", ""))
    write_field("Additional Access Available", state.get("additional_access", ""))

    # ── Subdivision ──
    write_section("SUBDIVISION")
    write_field("Platting / Subdivision Requirements", state.get("platting", ""))
    write_field("Anticipated Takings / Easements", state.get("takings_easements", ""))

    # ── Environmental ──
    write_section("ENVIRONMENTAL")
    write_field("Storm Water Treatment Requirements", state.get("stormwater_treatment", ""))
    write_field("Wetlands or Flood Plains Present", state.get("wetlands_flood", ""))
    write_field("Setback / Elevation for Flood Plain", state.get("flood_elevation", ""))
    write_field("Natural or Cultural Resources", state.get("natural_cultural", ""))
    write_field("Environmental Considerations", state.get("env_considerations", ""))
    write_field("Geotechnical Considerations", state.get("geotechnical", ""))
    write_field("Impact Studies Required", state.get("impact_studies", ""))
    write_field("Traffic Study Required", state.get("traffic_study", ""))

    # ── Building ──
    write_section("BUILDING")
    write_field("Current Building Code", state.get("building_code", ""))
    write_field("Unique Construction Methods", state.get("construction_methods", ""))
    write_field("Fire Route Considerations", state.get("fire_route", ""))

    # ── Fees ──
    write_section("FEES")
    write_field("Fire Plan Review", state.get("fee_fire_plan_review", ""))
    write_field("Building Plan Review", state.get("fee_bldg_plan_review", ""))
    write_field("Site Plan Review", state.get("fee_site_plan_review", ""))
    write_field("Building Permit", state.get("fee_bldg_permit", ""))
    write_field("Demo Permit", state.get("fee_demo_permit", ""))
    write_field("ROW Dedication / Easements", state.get("fee_dedication", ""))
    write_field("Securities & Utility Connection", state.get("fee_securities", ""))
    write_field("Lot Line Adjustment", state.get("fee_lot_line_adj", ""))
    write_field("Pre-Application Meeting", state.get("fee_pre_app", ""))
    write_field("Coastal Development Permit", state.get("fee_coastal_dev", ""))

    # ── Schedule ──
    write_section("SCHEDULE")
    write_field("Lot Line Adjustment", state.get("sched_lot_line_adj", ""))
    write_field("Entitlements Process", state.get("sched_entitlements", ""))
    write_field("Permitting Steps", state.get("sched_perm_steps", ""))
    write_field("Local Permitting (County / City)", state.get("sched_local", ""))
    write_field("SWFWMD Permitting", state.get("sched_wmd", ""))
    write_field("FDEP Permitting", state.get("sched_fdep", ""))
    write_field("FDOT Permitting", state.get("sched_fdot", ""))
    write_field("Required Staff Meetings", state.get("sched_staff_meetings", ""))
    write_field("Required Public Meetings", state.get("sched_public_meetings", ""))

    # ── Generated analysis output moved to dedicated worksheets ──
    write_section("AUTO-GENERATED TAB OUTPUTS")
    write_field("Requirements Analysis", "See worksheet: Requirements Output")
    write_field("Parking Analysis", "See worksheet: Parking Output")
    write_field("Landscape Analysis", "See worksheet: Landscape Output")
    write_field("Fees & Schedule", "See worksheet: Fees Output")

    write_analysis_sheet("Requirements Output", "Requirements Analysis", build_requirements_markdown())
    write_analysis_sheet("Parking Output", "Parking Analysis", build_parking_markdown())
    write_analysis_sheet("Landscape Output", "Landscape Analysis", build_landscape_markdown())
    write_analysis_sheet("Fees Output", "Fees & Schedule", build_fees_schedule_text())

    # ── Save ──
    reports_dir = pathlib.Path(__file__).parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    pid = (state.get("parcel_id") or "unknown").replace("-", "").replace(" ", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{pid}_{ts}.xlsx" if pid != "unknown" else f"report_{ts}.xlsx"
    out_path = reports_dir / filename
    wb.save(str(out_path))
    try:
        # Also trigger a browser download so users can pick a save location.
        ui.download(str(out_path), filename=filename)
    except Exception:
        # Keep local file save even if browser download isn't available.
        pass
    ui.notify(f"Saved locally: {out_path.resolve()}", type="positive", timeout=10000)


def export_excel_report() -> None:
    """Safe export entrypoint: try formatted export, fall back to plain export."""
    import pathlib
    from datetime import datetime

    try:
        generate_excel_report()
        return
    except Exception as exc:
        logger.exception("Formatted Excel export failed: %s", exc)

    # Fallback export so users are never blocked.
    try:
        import openpyxl
    except ImportError:
        ui.notify("Excel export failed and openpyxl is not installed.", type="negative")
        return

    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Fallback Export"
        ws.column_dimensions["A"].width = 36
        ws.column_dimensions["B"].width = 120
        ws.cell(row=1, column=1, value="Field")
        ws.cell(row=1, column=2, value="Value")

        r = 2
        for k, v in state.items():
            ws.cell(row=r, column=1, value=str(k))
            ws.cell(row=r, column=2, value=str(v) if v is not None else "")
            r += 1

        # Add generated analysis text blocks.
        for title, content in (
            ("Requirements Output", build_requirements_markdown()),
            ("Parking Output", build_parking_markdown()),
            ("Landscape Output", build_landscape_markdown()),
            ("Fees Output", build_fees_schedule_text()),
        ):
            ws.cell(row=r, column=1, value=title)
            ws.cell(row=r, column=2, value=str(content) if content else "")
            r += 1

        reports_dir = pathlib.Path(__file__).parent / "reports"
        reports_dir.mkdir(exist_ok=True)
        pid = (state.get("parcel_id") or "unknown").replace("-", "").replace(" ", "_")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{pid}_{ts}_fallback.xlsx" if pid != "unknown" else f"report_{ts}_fallback.xlsx"
        out_path = reports_dir / filename
        wb.save(str(out_path))

        try:
            ui.download(str(out_path), filename=filename)
        except Exception:
            pass

        ui.notify(
            f"Formatted export failed; fallback file saved locally: {out_path.resolve()}",
            type="warning",
            timeout=12000,
        )
    except Exception as exc:
        logger.exception("Fallback Excel export failed: %s", exc)
        ui.notify("Excel export failed. Check terminal logs for details.", type="negative", timeout=12000)


# ──────────────────────────────────────────────────────────────────────
# CSS (adapted from proposal app)
# ──────────────────────────────────────────────────────────────────────
ui.add_css(
    """
    @import url("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap");
    :root {
        --navy: #0b1f3a;
        --navy-2: #122c54;
        --ink: #101820;
        --paper: #f7f8fb;
        --panel: #ffffff;
        --border: #c9d3e1;
        --field-radius: 8px;
        --font-sans: "IBM Plex Sans", "Noto Sans", sans-serif;
    }
    body, .q-app {
        background: var(--paper);
        color: var(--ink);
        font-family: var(--font-sans);
    }
    .q-tab-panel { padding: 0; }
    .text-h4, .text-h5, .text-h6, .section-title, .q-tab__label {
        font-family: Arial, sans-serif;
        letter-spacing: 0.2px;
    }
    .tab-card, .section-card {
        background: transparent;
        border: none;
        border-radius: 0;
        padding: 0;
        box-shadow: none;
    }
    .section-title {
        font-weight: 700;
        color: var(--navy);
        margin-top: 6px;
        font-size: 1.05rem;
    }
    .field-label {
        font-weight: 600;
        color: var(--navy);
        font-size: 0.85rem;
        margin-bottom: 1px;
        line-height: 0.1;
    }
    .muted { color: #55657d; font-size: 0.85rem; }
    .q-field__control {
        border: 1px solid var(--border);
        border-radius: var(--field-radius);
        background: #ffffff;
        padding: 8px 10px;
        box-shadow: 0 2px 6px rgba(11, 31, 58, 0.06);
        align-items: center;
        overflow: visible;
    }
    .q-field:not(.q-field--textarea) .q-field__control {
        min-height: 40px;
        height: 40px;
    }
    .sir-textarea .q-field__control {
        min-height: 120px !important;
        align-items: flex-start !important;
    }
    .sir-textarea .q-field__native {
        min-height: 100px !important;
        height: auto !important;
        overflow-y: auto !important;
        resize: vertical;
        vertical-align: top !important;
        align-items: flex-start !important;
        text-align: left !important;
        padding-top: 6px !important;
    }
    .q-field--focused .q-field__control {
        border-color: var(--navy);
        box-shadow: 0 0 0 2px rgba(11, 31, 58, 0.12);
    }
    .q-field__label {
        color: var(--navy) !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        position: absolute !important;
        top: -22px !important;
        left: 8px !important;
        transform: none !important;
        background: var(--paper) !important;
        padding: 0 4px !important;
        z-index: 2 !important;
        line-height: 1 !important;
        pointer-events: none !important;
    }
    .q-field__native, .q-field__input { color: #5b667a; padding: 0; font-weight: 400; }
    .q-field__native::placeholder, .q-field__input::placeholder {
        color: #9aa5b1;
        font-family: var(--font-sans);
        font-weight: 300;
    }
    .q-field__control:before, .q-field__control:after { display: none; }
    .center-select .q-field__control,
    .center-select .q-field__control-container,
    .center-select .q-select__selection {
        align-items: center !important;
    }
    .q-tabs { border-bottom: 1px solid var(--border); }
    .tabs-left { width: fit-content; align-self: flex-start; }
    .tabs-left .q-tabs__content { justify-content: flex-start; }
    .q-tab {
        background: #eef2f7;
        border: 1px solid var(--border);
        border-bottom: none;
        border-radius: 12px 12px 0 0;
        margin-right: 8px;
        padding: 8px 16px;
    }
    .q-tab--active { background: #f7f9fc; }
    .q-tab__indicator { height: 2px; background: #ff3b30; }
    .q-btn {
        background: #5a8fcf;
        color: #ffffff;
        border-radius: 8px;
        text-transform: uppercase;
        font-weight: 600;
        padding: 10px 16px;
        box-shadow: 0 4px 10px rgba(11, 31, 58, 0.12);
    }
    .q-btn:hover { background: #4f80bc; }
    .lookup-field { width: 500px !important; max-width: 500px !important; }
    .lookup-field .q-field__control { width: 500px !important; }
    .lookup-field input { width: 500px !important; }
    .code-field { width: 500px !important; max-width: 500px !important; }
    .code-field .q-field__control { width: 500px !important; }
    .code-field input { width: 500px !important; }
    .fee-expansion { border: 1px solid var(--border); border-radius: 6px; margin-bottom: 4px; }
    .fee-expansion .q-expansion-item__content { padding: 8px 16px 12px; }
    .fee-line { font-size: 0.85rem; color: #2c3e50; padding: 1px 0; line-height: 1.5; white-space: pre-wrap; }
    .link-btn { font-size: 0.8rem !important; text-transform: none !important; font-weight: 500; }
    .export-btn { font-size: 0.85rem !important; font-weight: 600; }
    """
)

# ──────────────────────────────────────────────────────────────────────
# Main layout
# ──────────────────────────────────────────────────────────────────────
ui.label("Development Code Lookup").classes("text-h4 q-mb-sm")
ui.label("Florida — Pinellas · Pasco · Hillsborough Counties · Land Development Code & Comprehensive Plan").classes("muted q-mb-md")

with ui.row().classes("w-full items-center justify-between q-mb-sm"):
    ui.button(
        "EXPORT TO EXCEL",
        on_click=export_excel_report,
        icon="download",
        color="positive",
    ).props("outline").classes("export-btn")
    ui.label("Exports all fields from every tab to a .xlsx file in the reports/ folder.").classes("muted")

with ui.tabs().classes("tabs-left") as tabs:
    tab1 = ui.tab("Property Lookup")
    tab2 = ui.tab("Requirements")
    tab3 = ui.tab("Parking")
    tab4 = ui.tab("Landscape")
    tab5 = ui.tab("Infrastructure")
    tab6 = ui.tab("Environmental")
    tab7 = ui.tab("Fees & Schedule")

with ui.tab_panels(tabs, value=tab1).classes("w-full"):
    with ui.tab_panel(tab1):
        with ui.card().classes("w-full tab-card"):
            render_tab_lookup()
    with ui.tab_panel(tab2):
        with ui.card().classes("w-full tab-card"):
            render_tab_requirements()
    with ui.tab_panel(tab3):
        with ui.card().classes("w-full tab-card"):
            render_tab_parking()
    with ui.tab_panel(tab4):
        with ui.card().classes("w-full tab-card"):
            render_tab_landscape()
    with ui.tab_panel(tab5):
        with ui.card().classes("w-full tab-card"):
            render_tab_infrastructure()
    with ui.tab_panel(tab6):
        with ui.card().classes("w-full tab-card"):
            render_tab_environmental()
    with ui.tab_panel(tab7):
        with ui.card().classes("w-full tab-card"):
            render_tab_fees_schedule()

app_port = int(os.getenv("PORT", os.getenv("APP_PORT", "8081")))

ui.run(
    title="Dev Code Lookup",
    host=os.getenv("APP_HOST", "0.0.0.0"),
    port=app_port,
    show=False,
    reload=False,
    reconnect_timeout=30,
)
