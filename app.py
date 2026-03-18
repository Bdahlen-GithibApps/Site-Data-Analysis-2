"""
Pinellas County Development Code Lookup — NiceGUI App

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
from typing import Any, Dict, List

from nicegui import ui

from agents.zoning_agent import ZoningAgent
from agents.parking_agent import ParkingAgent
from agents.landscape_agent import LandscapeAgent
from tools.scraper import scrape_pinellas_property, expand_city_name
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
    "owner": "",
    "land_use": "",
    "site_area_acres": "",
    "site_area_sqft": "",
    # Code inputs (manual or from lookup)
    "zoning": "",
    "future_land_use": "",
    # Parking inputs
    "use_type": "",
    "building_sf": "",
    "num_units": "",
}

ui_refs: Dict[str, Any] = {}


# ──────────────────────────────────────────────────────────────────────
# Requirements calculation
# ──────────────────────────────────────────────────────────────────────

def build_requirements_markdown() -> str:
    county = state.get("county", "Pinellas")
    zoning_code = (state.get("zoning") or "").strip().upper()
    flu_code = (state.get("future_land_use") or "").strip().upper()
    site_sf = safe_float(state.get("site_area_sqft"))

    if not zoning_code and not flu_code:
        return "*Enter Zoning and/or Future Land Use to see requirements.*"

    lines: List[str] = []

    # Dimensional standards
    zd = _zoning_agent.get_zoning_standards(county, zoning_code) if zoning_code else None
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
        lines.append(f"⚠️ Zoning district **{zoning_code}** not found in data tables.")
        lines.append("")

    # FLUM
    flu = _zoning_agent.get_flum_standards(county, flu_code) if flu_code else None
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
            compat = _zoning_agent.check_compatibility(county, zoning_code, flu_code)
            if compat.get("compatible"):
                lines.append(f"✅ Zoning **{zoning_code}** is consistent with FLU **{flu_code}**")
            else:
                lines.append(f"⚠️ Zoning **{zoning_code}** may not be consistent with FLU **{flu_code}** — compatible: {', '.join(flu.get('compatible_zoning', []))}")
            lines.append("")
    elif flu_code:
        lines.append(f"⚠️ FLU category **{flu_code}** not found in data tables.")
        lines.append("")

    # Code references
    lines.append("---")
    lines.append("**Code References:**")
    lines.append("Ch. 138, Art. III — Zoning Districts · Sec. 138-3501 — Building Height · Sec. 138-3505 — Setbacks · Comprehensive Plan — Future Land Use Element")

    return "\n".join(lines)


def build_parking_markdown() -> str:
    county = state.get("county", "Pinellas")
    use_type = state.get("use_type", "")
    building_sf = safe_float(state.get("building_sf"))
    num_units = safe_int(state.get("num_units"))

    if not use_type:
        return "*Select a proposed use type to calculate parking requirements.*"

    result = _parking_agent.calculate(county, use_type, building_sf, num_units)

    if "error" in result:
        return f"⚠️ {result['error']}"

    lines: List[str] = []
    lines.append(f"### Parking Analysis — {use_type}")
    lines.append(f"**Rate:** {result['rate_description']}")
    if result.get("max_limit_description"):
        lines.append(f"**Maximum:** {result['max_limit_description']}")
    lines.append("")

    unit = result.get("unit", "")
    calc_spaces = result.get("required_spaces", 0)

    if calc_spaces == 0:
        if unit == "1,000 sf GFA":
            lines.append("*Enter building SF to calculate.*")
        else:
            lines.append(f"*Enter number of {unit}s to calculate.*")
        return "\n".join(lines)

    if unit == "1,000 sf GFA" and building_sf > 0:
        lines.append(f"Building area: **{fmt_num(building_sf)} sf GFA**")
    elif num_units > 0:
        lines.append(f"Units ({unit}): **{num_units}**")

    lines.append("")
    lines.append("| Requirement | Spaces |")
    lines.append("|-------------|--------|")
    lines.append(f"| **Required Minimum** | **{calc_spaces}** |")
    if result.get("max_spaces"):
        lines.append(f"| Maximum Allowed | {result['max_spaces']} |")
    lines.append(f"| ADA Accessible | {result['ada_spaces']} |")
    lines.append(f"| Bicycle | {result['bicycle_spaces']} |")
    lines.append("")

    # Stall dimensions
    lines.append("**Stall Dimensions (Table 138-3602.d):**")
    lines.append("")
    lines.append("| Layout | Stall | Aisle |")
    lines.append("|--------|-------|-------|")
    lines.append("| 90° | 9' × 18' | 24' (two-way) |")
    lines.append("| 60° | 9' × 18' | 18' (one-way) |")
    lines.append("| 45° | 9' × 18' | 15' (one-way) |")
    lines.append("| Parallel | 8' × 22' | 12' (one-way) |")
    lines.append("| ADA | 12' × 18' | — |")
    lines.append("")
    lines.append("---")
    lines.append("**Code References:** Sec. 138-3602 — Motor Vehicle Parking · Sec. 138-3603 — Bicycle Parking")

    return "\n".join(lines)


def build_landscape_markdown() -> str:
    county = state.get("county", "Pinellas")
    reqs = _landscape_agent.get_requirements(county)

    if not reqs.get("available"):
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
    lines.append("**Code References:** Ch. 138, Art. IV — Landscaping & Tree Protection · Sec. 138-3800 thru 138-3804")

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


def refresh_all() -> None:
    refresh_requirements()
    refresh_parking()
    refresh_landscape()


def set_field(key: str, value: Any) -> None:
    state[key] = value
    if key in ui_refs:
        if hasattr(ui_refs[key], "value") and ui_refs[key].value != value:
            ui_refs[key].value = value
            ui_refs[key].update()
    if key in ("zoning", "future_land_use", "site_area_sqft"):
        refresh_requirements()
    if key in ("use_type", "building_sf", "num_units"):
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
                    )
                    county_input = labeled_select(
                        "County",
                        ["Pinellas", "Hillsborough", "Pasco"],
                        value=state.get("county", "Pinellas"),
                        classes="col-4 center-select",
                    )
                    ui_refs["parcel_id_input"] = parcel_input
                    ui_refs["county_input"] = county_input
                    parcel_input.on("change", lambda e: state.__setitem__("parcel_id", e.value))
                    county_input.on("change", lambda e: state.__setitem__("county", e.value))

                def do_lookup() -> None:
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
                    if county != "Pinellas":
                        ui.notify("Property lookup is only implemented for Pinellas County right now.", type="warning")
                        return

                    ui.notify("Fetching property data...", type="info")
                    result = scrape_pinellas_property(parcel_id)
                    if not result.get("success"):
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
                    }
                    for state_key, result_key in field_map.items():
                        val = result.get(result_key, "") or ""
                        state[state_key] = val
                        if state_key in ui_refs:
                            ui_refs[state_key].value = val
                            ui_refs[state_key].update()

                    # Expand city name
                    state["city"] = expand_city_name(result.get("city", "") or "")
                    if "city" in ui_refs:
                        ui_refs["city"].value = state["city"]
                        ui_refs["city"].update()

                    refresh_zoning_button()
                    refresh_all()
                    ui.notify("Property data retrieved.", type="positive")

                ui.button("LOOKUP PROPERTY DATA", on_click=do_lookup, color="primary").classes("q-mt-md w-full")

                # Zoning map button
                ui.label("Zoning & Land Use Map").classes("section-title q-mt-md")

                def open_zoning_map() -> None:
                    city = state.get("city", "")
                    address = state.get("address", "")
                    zip_code = state.get("zip", "")
                    map_url = get_zoning_map_url(city, address, zip_code)
                    if map_url:
                        ui.navigate.to(map_url, new_tab=True)
                    else:
                        ui.notify("No zoning map URL found for this municipality.", type="warning")

                zoning_btn = ui.button("OPEN ZONING AND LAND USE MAP", on_click=open_zoning_map).classes("q-mt-sm w-full")
                ui_refs["zoning_button"] = zoning_btn
                zoning_status = ui.label("").classes("muted q-mt-xs")
                zoning_status.visible = False
                ui_refs["zoning_status"] = zoning_status

                def refresh_zoning_button() -> None:
                    city = state.get("city", "")
                    address = state.get("address", "")
                    zip_code = state.get("zip", "")
                    map_url = get_zoning_map_url(city, address, zip_code)

                    label_city = city.upper() if city else ""
                    if "unincorporated" in (city or "").lower():
                        label_city = "PINELLAS COUNTY"
                    label = f"OPEN {label_city} ZONING AND LAND USE MAP" if label_city else "OPEN ZONING AND LAND USE MAP"
                    ui_refs["zoning_button"].text = label

                    if map_url:
                        ui_refs["zoning_button"].enable()
                        ui_refs["zoning_status"].text = ""
                        ui_refs["zoning_status"].visible = False
                    else:
                        ui_refs["zoning_button"].disable()
                        ui_refs["zoning_status"].text = "No zoning map link found for this municipality."
                        ui_refs["zoning_status"].visible = True

                refresh_zoning_button()

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
                    ui_refs[key].on("change", lambda e, k=key: set_field(k, e.value))

        # RIGHT COLUMN — Zoning + FLU inputs
        with ui.column().classes("col-6"):
            with ui.card().classes("section-card w-full"):
                ui.label("Zoning & Land Use (from Map)").classes("section-title")
                ui.label("Look up zoning and FLU on the map, then enter or select below.").classes("muted q-mb-sm")

                zoning_options = _zoning_agent.get_zoning_options(county)
                flu_options = _zoning_agent.get_flum_options(county)

                zoning_select = labeled_select(
                    "Zoning District",
                    zoning_options,
                    value=state.get("zoning") or None,
                    classes="code-field",
                    with_input=True,
                )
                flu_select = labeled_select(
                    "Future Land Use (FLUM)",
                    flu_options,
                    value=state.get("future_land_use") or None,
                    classes="code-field",
                    with_input=True,
                )
                ui_refs["zoning_select"] = zoning_select
                ui_refs["flu_select"] = flu_select

                zoning_select.on("change", lambda e: set_field("zoning", e.value or ""))
                flu_select.on("change", lambda e: set_field("future_land_use", e.value or ""))

            with ui.card().classes("section-card q-mt-md w-full"):
                ui.label("Parking Input").classes("section-title")

                use_options = _parking_agent.get_use_type_options(county)
                use_select = labeled_select(
                    "Proposed Use Type",
                    use_options,
                    value=state.get("use_type") or None,
                    classes="code-field",
                    with_input=True,
                )
                bldg_input = labeled_input(
                    "Building Area (SF GFA)",
                    value=state.get("building_sf", ""),
                    placeholder="e.g. 15000",
                    classes="code-field",
                )
                units_input = labeled_input(
                    "Number of Units / Seats / Beds",
                    value=state.get("num_units", ""),
                    placeholder="e.g. 24",
                    classes="code-field",
                )

                use_select.on("change", lambda e: set_field("use_type", e.value or ""))
                bldg_input.on("change", lambda e: set_field("building_sf", e.value))
                units_input.on("change", lambda e: set_field("num_units", e.value))


def render_tab_requirements() -> None:
    ui.label("Development Requirements").classes("text-h5 q-mb-md")
    with ui.card().classes("section-card w-full"):
        md = ui.markdown(build_requirements_markdown()).classes("q-mt-sm")
        ui_refs["requirements_md"] = md


def render_tab_parking() -> None:
    ui.label("Parking Analysis").classes("text-h5 q-mb-md")
    with ui.card().classes("section-card w-full"):
        md = ui.markdown(build_parking_markdown()).classes("q-mt-sm")
        ui_refs["parking_md"] = md


def render_tab_landscape() -> None:
    ui.label("Landscape Requirements").classes("text-h5 q-mb-md")
    with ui.card().classes("section-card w-full"):
        md = ui.markdown(build_landscape_markdown()).classes("q-mt-sm")
        ui_refs["landscape_md"] = md


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
    """
)

# ──────────────────────────────────────────────────────────────────────
# Main layout
# ──────────────────────────────────────────────────────────────────────
ui.label("Pinellas County Development Code Lookup").classes("text-h4 q-mb-sm")
ui.label("Unincorporated Pinellas County, FL — Chapter 138 Land Development Code").classes("muted q-mb-md")

with ui.tabs().classes("tabs-left") as tabs:
    tab1 = ui.tab("Property Lookup")
    tab2 = ui.tab("Requirements")
    tab3 = ui.tab("Parking")
    tab4 = ui.tab("Landscape")

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

ui.run(
    title="Dev Code Lookup",
    port=8080,
    reload=True,
    show=True,
)
