"""
Pinellas County Development Code Lookup — NiceGUI App

Single-file app with 3 tabs:
  1. Property Lookup — County + Parcel ID → PCPAO scrape → auto-fill
  2. Requirements  — Zoning dimensional standards + FLUM density/intensity
  3. Parking        — Use-based parking calculation + ADA + bicycle

Run:
    pip install -r requirements.txt
    python app.py
"""

from __future__ import annotations

import math
import re
import logging
from typing import Dict, Any, Optional, List

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from nicegui import ui
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote

logger = logging.getLogger(__name__)

ZONING_DISTRICTS = {
    # ── SINGLE FAMILY RESIDENTIAL ──
    "R-A": {
        "name": "Residential Agriculture",
        "category": "Single Family Residential",
        "allowed_uses_summary": "Single family detached, accessory uses, agriculture and livestock for personal use, commercial agriculture with special approval.",
        "min_lot_area": "2 acres",
        "min_lot_area_sf": 87120,
        "min_lot_width": "90'",
        "min_lot_depth": "100'",
        "setback_front_structure": 25,
        "setback_front_porch": 15,
        "setback_side_interior": 15,
        "setback_side_street": 20,
        "setback_rear": 20,
        "max_height": 35,
        "notes": "Footnote 3: Front structure/front porch. Footnote 4: Side interior/side street.",
    },
    "R-E": {
        "name": "Residential Estate",
        "category": "Single Family Residential",
        "allowed_uses_summary": "Single family detached, accessory uses, agriculture and livestock for personal use.",
        "min_lot_area": "32,000 sf",
        "min_lot_area_sf": 32000,
        "min_lot_width": "90'",
        "min_lot_depth": "100'",
        "setback_front_structure": 25,
        "setback_front_porch": 15,
        "setback_side_interior": 15,
        "setback_side_street": 20,
        "setback_rear": 20,
        "max_height": 35,
        "notes": "Footnote 3: Front structure/front porch. Footnote 4: Side interior/side street.",
    },
    "R-R": {
        "name": "Rural Residential",
        "category": "Single Family Residential",
        "allowed_uses_summary": "Single family detached, accessory uses, agriculture and livestock for personal use.",
        "min_lot_area": "16,000 sf",
        "min_lot_area_sf": 16000,
        "min_lot_width": "90'",
        "min_lot_depth": "100'",
        "setback_front_structure": 25,
        "setback_front_porch": 15,
        "setback_side_interior": 10,
        "setback_side_street": 15,
        "setback_rear": 15,
        "max_height": 35,
        "notes": "Footnote 3: Front structure/front porch. Footnote 4: Side interior/side street.",
    },
    "R-1": {
        "name": "Single Family Residential",
        "category": "Single Family Residential",
        "allowed_uses_summary": "Single family detached, accessory uses.",
        "min_lot_area": "9,500 sf",
        "min_lot_area_sf": 9500,
        "min_lot_width": "80'",
        "min_lot_depth": "90'",
        "setback_front_structure": 20,
        "setback_front_porch": 10,
        "setback_side_interior": 6,
        "setback_side_street": 10,
        "setback_rear": 10,
        "max_height": 35,
        "notes": "Footnote 3: Front structure/front porch. Footnote 4: Side interior/side street.",
    },
    "R-2": {
        "name": "Single Family Residential",
        "category": "Single Family Residential",
        "allowed_uses_summary": "Single family detached, accessory uses.",
        "min_lot_area": "7,500 sf",
        "min_lot_area_sf": 7500,
        "min_lot_width": "70'",
        "min_lot_depth": "80'",
        "setback_front_structure": 20,
        "setback_front_porch": 10,
        "setback_side_interior": 6,
        "setback_side_street": 10,
        "setback_rear": 10,
        "max_height": 35,
        "notes": "Footnote 3: Front structure/front porch. Footnote 4: Side interior/side street.",
    },
    "R-3": {
        "name": "Single Family Residential",
        "category": "Single Family Residential",
        "allowed_uses_summary": "Single family detached, accessory uses.",
        "min_lot_area": "6,000 sf",
        "min_lot_area_sf": 6000,
        "min_lot_width": "60'",
        "min_lot_depth": "80'",
        "setback_front_structure": 20,
        "setback_front_porch": 10,
        "setback_side_interior": 6,
        "setback_side_street": 10,
        "setback_rear": 10,
        "max_height": 35,
        "notes": "Footnote 3: Front structure/front porch. Footnote 4: Side interior/side street.",
    },
    "RMH": {
        "name": "Residential Mobile/Manufactured Home",
        "category": "Single Family Residential",
        "allowed_uses_summary": "Mobile home parks, mobile home subdivisions, single family detached, accessory uses.",
        "min_lot_area": "6,000 sf (subdivision); Park: 15 acres; Spaces: 3,500 sf",
        "min_lot_area_sf": 6000,
        "min_lot_width": "60'",
        "min_lot_depth": "80'",
        "setback_front_structure": 20,
        "setback_front_porch": 10,
        "setback_side_interior": 6,
        "setback_side_street": 10,
        "setback_rear": 10,
        "max_height": 35,
        "notes": "Park requirements differ from subdivision. See code for park-specific setbacks.",
    },

    # ── MULTI-FAMILY RESIDENTIAL ──
    "R-4": {
        "name": "One, Two & Three Family Residential",
        "category": "Multi-Family Residential",
        "allowed_uses_summary": "Single family detached, single family attached, duplex, triplex, accessory uses.",
        "min_lot_area": "5,000 sf (SFD); 2,800 sf (SFA); 7,500 sf (duplex/triplex)",
        "min_lot_area_sf": 5000,
        "min_lot_width": "50'",
        "min_lot_depth": "80'",
        "setback_front_structure": 20,
        "setback_front_porch": 10,
        "setback_side_interior": 6,
        "setback_side_street": 10,
        "setback_rear": 10,
        "max_height": 35,
        "notes": "Footnote 5: Side interior unit/side end unit/side street for attached units (0'/5'/10').",
    },
    "R-5": {
        "name": "Urban Residential",
        "category": "Multi-Family Residential",
        "allowed_uses_summary": "Single family detached, single family attached, duplex, triplex, multi-family, accessory uses.",
        "min_lot_area": "3,000 sf",
        "min_lot_area_sf": 3000,
        "min_lot_width": "N/A",
        "min_lot_depth": "N/A",
        "setback_front_structure": 10,
        "setback_front_garage": 20,
        "setback_side_interior": 5,
        "setback_side_street": 10,
        "setback_rear": 5,
        "max_height": 45,
        "max_height_note": "35' for SFD; 45' for all other uses",
        "notes": "Footnote 6: Front structure/front garage. Footnote 7: Rear structure/alley-accessible garages (10'/5').",
    },
    "RM": {
        "name": "Multi-family Residential",
        "category": "Multi-Family Residential",
        "allowed_uses_summary": "Single family detached, single family attached, duplex, triplex, multi-family, accessory uses.",
        "min_lot_area": "3,000 sf (SFD); 1,400 sf (SFA/duplex/triplex); 7,500 sf (all other)",
        "min_lot_area_sf": 3000,
        "min_lot_width": "N/A (SFD); 20' (SFA); 75' (all other)",
        "min_lot_depth": "N/A (SFD); 70' (SFA); 80' (all other)",
        "setback_front_structure": 10,
        "setback_front_garage": 20,
        "setback_side_interior": 5,
        "setback_side_street": 10,
        "setback_rear": 5,
        "max_height": 50,
        "max_height_note": "35' for SFD; 45' for SFA/duplex/triplex; 50' for all other",
        "notes": "Footnote 5: SFA side = 0'/5'/10' (interior/end/street). Footnote 6: Front structure/front garage.",
    },
    "RPD": {
        "name": "Residential Planned Development",
        "category": "Multi-Family Residential",
        "allowed_uses_summary": "Single family, multi-family, accessory uses, certain nonresidential uses (see Code).",
        "min_lot_area": "Per Development Master Plan, or per R-4 standards if no DMP",
        "min_lot_area_sf": None,
        "min_lot_width": "Per DMP",
        "min_lot_depth": "Per DMP",
        "setback_front_structure": None,
        "setback_side_interior": None,
        "setback_rear": None,
        "max_height": None,
        "notes": "All standards per Development Master Plan, or per R-4 if no DMP is in place.",
    },

    # ── OFFICE AND COMMERCIAL ──
    "LO": {
        "name": "Limited Office",
        "category": "Office and Commercial",
        "allowed_uses_summary": "Limited office and professional uses.",
        "min_lot_area": "6,000 sf",
        "min_lot_area_sf": 6000,
        "min_lot_width": "60'",
        "min_lot_depth": "80'",
        "setback_front": 5,
        "setback_side_interior": 10,
        "setback_rear": 10,
        "max_height": 45,
        "notes": "Nonresidential districts have front setbacks on all road frontages (no side street setback distinction).",
    },
    "GO": {
        "name": "General Office",
        "category": "Office and Commercial",
        "allowed_uses_summary": "Offices, clinics, studios and professional uses.",
        "min_lot_area": "6,000 sf",
        "min_lot_area_sf": 6000,
        "min_lot_width": "60'",
        "min_lot_depth": "80'",
        "setback_front": 5,
        "setback_side_interior": 10,
        "setback_rear": 10,
        "max_height": 75,
        "max_height_near_residential": 45,
        "notes": "Footnote 8: 75' normal / 45' within 50 ft of residential zoned property.",
    },
    "C-1": {
        "name": "Neighborhood Commercial",
        "category": "Office and Commercial",
        "allowed_uses_summary": "Neighborhood scale retail and restaurants, personal services, service stations, etc.",
        "min_lot_area": "6,000 sf",
        "min_lot_area_sf": 6000,
        "min_lot_width": "60'",
        "min_lot_depth": "80'",
        "setback_front": 5,
        "setback_side_abutting_nonresidential": 0,
        "setback_side_abutting_residential": 10,
        "setback_rear": None,
        "max_height": 45,
        "notes": "Footnote 9: Side 0' abutting nonresidential / 10' abutting residential.",
    },
    "C-2": {
        "name": "General Commercial and Services",
        "category": "Office and Commercial",
        "allowed_uses_summary": "Retail, offices, auto repair, personal/business services, restaurants, hotels, wholesale/distribution, research/development, multi-family residential, recreation, etc.",
        "min_lot_area": "10,000 sf",
        "min_lot_area_sf": 10000,
        "min_lot_width": "80'",
        "min_lot_depth": "100'",
        "setback_front": 5,
        "setback_side_abutting_nonresidential": 0,
        "setback_side_abutting_residential": 20,
        "setback_rear": None,
        "max_height": 75,
        "max_height_near_residential": 45,
        "notes": "Footnote 8: 75'/45'. Footnote 9: Side 0'/20'. Multi-family residential is allowed.",
    },
    "CP": {
        "name": "Commercial Parkway",
        "category": "Office and Commercial",
        "allowed_uses_summary": "Retail, restaurants, hotels, residential, offices, research/development, institutions, etc.",
        "min_lot_area": "1 acre",
        "min_lot_area_sf": 43560,
        "min_lot_width": "N/A",
        "min_lot_depth": "N/A",
        "setback_front": 5,
        "setback_side_abutting_nonresidential": 0,
        "setback_side_abutting_residential": 15,
        "setback_rear": None,
        "max_height": 75,
        "max_height_near_residential": 45,
        "notes": "Footnote 8: 75'/45'. Footnote 9: Side 0'/15'.",
    },
    "CR": {
        "name": "Commercial Recreation",
        "category": "Office and Commercial",
        "allowed_uses_summary": "Marinas, golf, stables, parks, bowling alleys, etc.",
        "min_lot_area": "1 acre",
        "min_lot_area_sf": 43560,
        "min_lot_width": "150'",
        "min_lot_depth": "200'",
        "setback_front": 10,
        "setback_side_interior": 20,
        "setback_rear": 50,
        "max_height": None,
        "notes": "RV park/campground sites: 2,500 sf min, 25' width, 5' setbacks.",
    },

    # ── EMPLOYMENT AND INDUSTRIAL ──
    "E-1": {
        "name": "Employment-1",
        "category": "Employment and Industrial",
        "allowed_uses_summary": "Light manufacturing, offices, research and development, accessory retail.",
        "min_lot_area": "12,000 sf",
        "min_lot_area_sf": 12000,
        "min_lot_width": "80'",
        "min_lot_depth": "100'",
        "setback_front": 5,
        "setback_side_abutting_nonresidential": 0,
        "setback_side_abutting_residential": 10,
        "setback_rear": None,
        "max_height": 75,
        "max_height_near_residential": 45,
        "notes": "Footnote 8: 75'/45'. Footnote 9: Side 0'/10'.",
    },
    "E-2": {
        "name": "Employment-2",
        "category": "Employment and Industrial",
        "allowed_uses_summary": "Warehousing/storage, offices, recreation, retail, health/fitness, wholesale/distribution, auto repair.",
        "min_lot_area": "12,000 sf",
        "min_lot_area_sf": 12000,
        "min_lot_width": "80'",
        "min_lot_depth": "100'",
        "setback_front": 5,
        "setback_side_abutting_nonresidential": 0,
        "setback_side_abutting_residential": 20,
        "setback_rear": None,
        "max_height": 75,
        "max_height_near_residential": 45,
        "notes": "Footnote 8: 75'/45'. Footnote 9: Side 0'/20'.",
    },
    "I": {
        "name": "Heavy Industry",
        "category": "Employment and Industrial",
        "allowed_uses_summary": "Heavy manufacturing, concrete, fiberglass, office.",
        "min_lot_area": "25,000 sf",
        "min_lot_area_sf": 25000,
        "min_lot_width": "100'",
        "min_lot_depth": "200'",
        "setback_front": 20,
        "setback_side_abutting_nonresidential": 0,
        "setback_side_abutting_residential": 20,
        "setback_rear": None,
        "max_height": 100,
        "max_height_near_residential": 45,
        "notes": "Footnote 8: 100'/45'. Footnote 9: Side 0'/20'.",
    },
    "IPD": {
        "name": "Industrial Planned Development",
        "category": "Employment and Industrial",
        "allowed_uses_summary": "Industrial/employment parks with accessory support services.",
        "min_lot_area": "Per Development Master Plan, or per E-1 standards if no DMP",
        "min_lot_area_sf": None,
        "min_lot_width": "Per DMP",
        "min_lot_depth": "Per DMP",
        "setback_front": None,
        "setback_side_interior": None,
        "setback_rear": None,
        "max_height": None,
        "notes": "All standards per Development Master Plan, or per E-1 if no DMP is in place.",
    },

    # ── MIXED-USE ──
    "MXD": {
        "name": "Mixed-Use",
        "category": "Mixed-Use",
        "allowed_uses_summary": "Variety of residential and nonresidential uses.",
        "min_lot_area": "Per DMP, or per RM (residential) / C-2 (nonresidential) if no DMP",
        "min_lot_area_sf": None,
        "min_lot_width": "Per DMP",
        "min_lot_depth": "Per DMP",
        "setback_front": None,
        "setback_side_interior": None,
        "setback_rear": None,
        "max_height": None,
        "notes": "Per DMP, or RM standards for residential and C-2 standards for nonresidential if no DMP.",
    },

    # ── INSTITUTIONAL ──
    "LI": {
        "name": "Limited Institutional",
        "category": "Institutional",
        "allowed_uses_summary": "Assembly uses, educational facilities, fraternal/civic organizations, ALFs, day care.",
        "min_lot_area": "0.5 acre",
        "min_lot_area_sf": 21780,
        "min_lot_width": "100'",
        "min_lot_depth": "100'",
        "setback_front": 20,
        "setback_side_interior": 10,
        "setback_rear": None,
        "max_height": 50,
        "notes": "",
    },
    "GI": {
        "name": "General Institutional",
        "category": "Institutional",
        "allowed_uses_summary": "Educational facilities, museums, assembly uses, hospitals, government facilities, ALFs, etc.",
        "min_lot_area": "0.5 acre",
        "min_lot_area_sf": 21780,
        "min_lot_width": "100'",
        "min_lot_depth": "100'",
        "setback_front": 20,
        "setback_side_interior": 15,
        "setback_rear": None,
        "max_height": 50,
        "notes": "",
    },

    # ── ENVIRONMENTAL ──
    "AL": {
        "name": "Aquatic Lands",
        "category": "Environmental",
        "allowed_uses_summary": "Open space, natural resource management, docks and piers, stormwater facilities.",
        "min_lot_area": "N/A",
        "min_lot_area_sf": None,
        "min_lot_width": "N/A",
        "min_lot_depth": "N/A",
        "setback_front": None,
        "setback_side_interior": None,
        "setback_rear": None,
        "max_height": None,
        "notes": "No dimensional standards.",
    },
    "PC": {
        "name": "Preservation/Conservation",
        "category": "Environmental",
        "allowed_uses_summary": "Parks and open space, natural resource/wildlife management, environmental education, stormwater facilities, potable water devices.",
        "min_lot_area": "N/A",
        "min_lot_area_sf": None,
        "min_lot_width": "N/A",
        "min_lot_depth": "N/A",
        "setback_front": 20,
        "setback_side_interior": 20,
        "setback_rear": 20,
        "max_height": 35,
        "max_height_towers": 75,
        "notes": "Footnote 10: 35' structures / 75' observation towers and elevated walkways.",
    },
    "P-RM": {
        "name": "Preservation-Resource Management",
        "category": "Environmental",
        "allowed_uses_summary": "Natural resource/wildlife management, resource-based recreation, environmental education, water management facilities.",
        "min_lot_area": "N/A",
        "min_lot_area_sf": None,
        "min_lot_width": "N/A",
        "min_lot_depth": "N/A",
        "setback_front": 25,
        "setback_side_interior": 25,
        "setback_rear": 25,
        "max_height": 35,
        "max_height_towers": 75,
        "notes": "Footnote 10: 35' structures / 75' observation towers and elevated walkways.",
    },

    # ── RECREATIONAL ──
    "RBR": {
        "name": "Resource-Based Recreation",
        "category": "Recreational",
        "allowed_uses_summary": "Parks and open space, see Code for details.",
        "min_lot_area": "N/A",
        "min_lot_area_sf": None,
        "min_lot_width": "N/A",
        "min_lot_depth": "N/A",
        "setback_front": 25,
        "setback_side_interior": 25,
        "setback_rear": 25,
        "max_height": 45,
        "max_height_towers": 75,
        "notes": "Footnote 10: 45' structures / 75' observation towers and elevated walkways.",
    },
    "FBR": {
        "name": "Facilities-Based Recreation",
        "category": "Recreational",
        "allowed_uses_summary": "Parks and open space, skate parks, pools, courts, ballfields, fitness activities, community centers.",
        "min_lot_area": "N/A",
        "min_lot_area_sf": None,
        "min_lot_width": "N/A",
        "min_lot_depth": "N/A",
        "setback_front": 25,
        "setback_side_interior": 25,
        "setback_rear": 25,
        "max_height": 45,
        "max_height_towers": 75,
        "notes": "Footnote 10: 45' structures / 75' observation towers and elevated walkways.",
    },
}


# ──────────────────────────────────────────────────────────────────────
# FUTURE LAND USE MAP (FLUM) CATEGORIES
# Density/Intensity limits from Pinellas County Comprehensive Plan
# ──────────────────────────────────────────────────────────────────────

FLUM_CATEGORIES = {
    "RR": {
        "name": "Residential Rural",
        "max_density_du_per_acre": 2.5,
        "max_far": None,
        "max_isratio": 0.40,
        "compatible_zoning": ["R-A", "R-E"],
        "notes": "Low density, agricultural character areas.",
    },
    "RE": {
        "name": "Residential Estate",
        "max_density_du_per_acre": 2.5,
        "max_far": None,
        "max_isratio": 0.45,
        "compatible_zoning": ["R-E", "R-R"],
        "notes": "Estate-character residential areas.",
    },
    "RS": {
        "name": "Residential Suburban",
        "max_density_du_per_acre": 5.0,
        "max_far": None,
        "max_isratio": 0.55,
        "compatible_zoning": ["R-R", "R-1", "R-2"],
        "notes": "Suburban density residential areas.",
    },
    "RL": {
        "name": "Residential Low",
        "max_density_du_per_acre": 5.0,
        "max_far": None,
        "max_isratio": 0.65,
        "compatible_zoning": ["R-2", "R-3"],
        "notes": "Low density residential neighborhoods.",
    },
    "RLM": {
        "name": "Residential Low Medium",
        "max_density_du_per_acre": 10.0,
        "max_far": None,
        "max_isratio": 0.70,
        "compatible_zoning": ["R-3", "R-4"],
        "notes": "Transitional density between low and medium.",
    },
    "RM": {
        "name": "Residential Medium",
        "max_density_du_per_acre": 15.0,
        "max_far": None,
        "max_isratio": 0.75,
        "compatible_zoning": ["R-4", "R-5", "RM"],
        "notes": "Medium density residential.",
    },
    "RH": {
        "name": "Residential High",
        "max_density_du_per_acre": 30.0,
        "max_far": None,
        "max_isratio": 0.80,
        "compatible_zoning": ["R-5", "RM"],
        "notes": "High density residential.",
    },
    "RU": {
        "name": "Residential Urban",
        "max_density_du_per_acre": 30.0,
        "max_far": None,
        "max_isratio": 0.85,
        "compatible_zoning": ["R-5", "RM"],
        "notes": "Urban residential character.",
    },
    "CG": {
        "name": "Commercial General",
        "max_density_du_per_acre": None,
        "max_far": 0.55,
        "max_isratio": 0.90,
        "compatible_zoning": ["C-1", "C-2", "CP", "LO", "GO"],
        "notes": "General commercial uses.",
    },
    "OG": {
        "name": "Office General",  
        "max_density_du_per_acre": None,
        "max_far": 0.50,
        "max_isratio": 0.80,
        "compatible_zoning": ["LO", "GO"],
        "notes": "Office-oriented areas.",
    },
    "IL": {
        "name": "Industrial Limited",
        "max_density_du_per_acre": None,
        "max_far": 0.65,
        "max_isratio": 0.85,
        "compatible_zoning": ["E-1", "E-2"],
        "notes": "Light industrial and employment uses.",
    },
    "IG": {
        "name": "Industrial General",
        "max_density_du_per_acre": None,
        "max_far": 0.75,
        "max_isratio": 0.90,
        "compatible_zoning": ["E-2", "I"],
        "notes": "General industrial uses.",
    },
    "T/U": {
        "name": "Transportation/Utility",
        "max_density_du_per_acre": None,
        "max_far": None,
        "max_isratio": 0.90,
        "compatible_zoning": [],
        "notes": "Transportation and utility corridors/facilities.",
    },
    "P": {
        "name": "Preservation",
        "max_density_du_per_acre": None,
        "max_far": None,
        "max_isratio": 0.10,
        "compatible_zoning": ["PC", "P-RM", "AL"],
        "notes": "Environmentally sensitive lands.",
    },
    "R/OS": {
        "name": "Recreation/Open Space",
        "max_density_du_per_acre": None,
        "max_far": None,
        "max_isratio": 0.40,
        "compatible_zoning": ["RBR", "FBR"],
        "notes": "Active and passive recreation areas.",
    },
    "I/C": {
        "name": "Institutional/Community",
        "max_density_du_per_acre": None,
        "max_far": 0.65,
        "max_isratio": 0.80,
        "compatible_zoning": ["LI", "GI"],
        "notes": "Institutional and community facility areas.",
    },
}


# ──────────────────────────────────────────────────────────────────────
# PARKING REQUIREMENTS (Table 138-3602.a)
# Common commercial/institutional uses
# NOTE: This is a subset of the full parking table. The complete table
# is in Code Section 138-3602. These rates should be verified against
# the current code.
# ──────────────────────────────────────────────────────────────────────

PARKING_REQUIREMENTS = {
    # Residential
    "Single Family Detached": {"min_rate": "2 per dwelling unit", "min_per_unit": 2.0, "unit": "dwelling unit", "max_limit": None},
    "Single Family Attached": {"min_rate": "2 per dwelling unit", "min_per_unit": 2.0, "unit": "dwelling unit", "max_limit": None},
    "Duplex": {"min_rate": "2 per dwelling unit", "min_per_unit": 2.0, "unit": "dwelling unit", "max_limit": None},
    "Multi-Family (Studio/1BR)": {"min_rate": "1.25 per dwelling unit", "min_per_unit": 1.25, "unit": "dwelling unit", "max_limit": None},
    "Multi-Family (2+ BR)": {"min_rate": "1.5 per dwelling unit", "min_per_unit": 1.5, "unit": "dwelling unit", "max_limit": None},
    "ALF / Group Home": {"min_rate": "0.5 per bed/resident", "min_per_unit": 0.5, "unit": "bed", "max_limit": None},

    # Office
    "Office (General)": {"min_rate": "3 per 1,000 sf GFA", "min_per_unit": 3.0, "unit": "1,000 sf GFA", "max_limit": "4 per 1,000 sf GFA"},
    "Office (Medical/Dental)": {"min_rate": "4 per 1,000 sf GFA", "min_per_unit": 4.0, "unit": "1,000 sf GFA", "max_limit": "5 per 1,000 sf GFA"},
    
    # Retail / Commercial
    "Retail (General)": {"min_rate": "3 per 1,000 sf GFA", "min_per_unit": 3.0, "unit": "1,000 sf GFA", "max_limit": "5 per 1,000 sf GFA"},
    "Shopping Center": {"min_rate": "4 per 1,000 sf GFA", "min_per_unit": 4.0, "unit": "1,000 sf GFA", "max_limit": "5 per 1,000 sf GFA"},
    "Restaurant (Sit-down)": {"min_rate": "8 per 1,000 sf GFA", "min_per_unit": 8.0, "unit": "1,000 sf GFA", "max_limit": "12 per 1,000 sf GFA"},
    "Restaurant (Fast Food)": {"min_rate": "10 per 1,000 sf GFA", "min_per_unit": 10.0, "unit": "1,000 sf GFA", "max_limit": "15 per 1,000 sf GFA"},
    "Convenience Store": {"min_rate": "4 per 1,000 sf GFA", "min_per_unit": 4.0, "unit": "1,000 sf GFA", "max_limit": None},
    "Hotel/Motel": {"min_rate": "1 per guest room + 3 per 1,000 sf meeting/restaurant", "min_per_unit": 1.0, "unit": "guest room", "max_limit": None},

    # Industrial / Employment
    "Warehouse/Storage": {"min_rate": "1 per 1,000 sf GFA", "min_per_unit": 1.0, "unit": "1,000 sf GFA", "max_limit": "2 per 1,000 sf GFA"},
    "Light Manufacturing": {"min_rate": "2 per 1,000 sf GFA", "min_per_unit": 2.0, "unit": "1,000 sf GFA", "max_limit": "3 per 1,000 sf GFA"},
    "Self-Storage": {"min_rate": "1 per 5,000 sf GFA + 2 for office", "min_per_unit": 0.2, "unit": "1,000 sf GFA", "max_limit": None},

    # Institutional
    "Church/Place of Worship": {"min_rate": "1 per 3 seats in main assembly", "min_per_unit": 0.33, "unit": "seat", "max_limit": None},
    "School (Elementary/Middle)": {"min_rate": "2 per classroom", "min_per_unit": 2.0, "unit": "classroom", "max_limit": None},
    "School (High School)": {"min_rate": "5 per classroom", "min_per_unit": 5.0, "unit": "classroom", "max_limit": None},
    "Day Care": {"min_rate": "1 per 8 children capacity + 1 per employee", "min_per_unit": None, "unit": "special", "max_limit": None},
    "Hospital": {"min_rate": "2 per bed", "min_per_unit": 2.0, "unit": "bed", "max_limit": None},

    # Recreation
    "Fitness/Health Club": {"min_rate": "5 per 1,000 sf GFA", "min_per_unit": 5.0, "unit": "1,000 sf GFA", "max_limit": None},
    "Marina": {"min_rate": "0.5 per wet slip + 0.25 per dry slip", "min_per_unit": 0.5, "unit": "wet slip", "max_limit": None},
}


# ──────────────────────────────────────────────────────────────────────
# ADA ACCESSIBLE PARKING (Table 338-3602.c)
# Per ADA / Florida Building Code
# ──────────────────────────────────────────────────────────────────────

ADA_PARKING_TABLE = [
    {"total_spaces_min": 1, "total_spaces_max": 25, "accessible_required": 1},
    {"total_spaces_min": 26, "total_spaces_max": 50, "accessible_required": 2},
    {"total_spaces_min": 51, "total_spaces_max": 75, "accessible_required": 3},
    {"total_spaces_min": 76, "total_spaces_max": 100, "accessible_required": 4},
    {"total_spaces_min": 101, "total_spaces_max": 150, "accessible_required": 5},
    {"total_spaces_min": 151, "total_spaces_max": 200, "accessible_required": 6},
    {"total_spaces_min": 201, "total_spaces_max": 300, "accessible_required": 7},
    {"total_spaces_min": 301, "total_spaces_max": 400, "accessible_required": 8},
    {"total_spaces_min": 401, "total_spaces_max": 500, "accessible_required": 9},
    {"total_spaces_min": 501, "total_spaces_max": 1000, "accessible_required": 2, "note": "2% of total"},
]


# ──────────────────────────────────────────────────────────────────────
# PARKING STALL DIMENSIONS (Table 138-3602.d)
# ──────────────────────────────────────────────────────────────────────

PARKING_DIMENSIONS = {
    "90_degree": {"angle": 90, "stall_width": 9.0, "stall_depth": 18.0, "aisle_width_two_way": 24.0, "aisle_width_one_way": 24.0},
    "60_degree": {"angle": 60, "stall_width": 9.0, "stall_depth": 18.0, "aisle_width_two_way": 24.0, "aisle_width_one_way": 18.0},
    "45_degree": {"angle": 45, "stall_width": 9.0, "stall_depth": 18.0, "aisle_width_two_way": 24.0, "aisle_width_one_way": 15.0},
    "parallel": {"angle": 0, "stall_width": 8.0, "stall_depth": 22.0, "aisle_width_two_way": 24.0, "aisle_width_one_way": 12.0},
    "accessible": {"stall_width": 12.0, "stall_depth": 18.0, "note": "Diagonal or perpendicular accessible stalls"},
}


# ──────────────────────────────────────────────────────────────────────
# BICYCLE PARKING (Sec. 138-3603)
# ──────────────────────────────────────────────────────────────────────

BICYCLE_PARKING = {
    "general_rule": "1 bicycle space per 20 motor vehicle spaces required, minimum 2",
    "calculation": lambda motor_vehicle_spaces: max(2, motor_vehicle_spaces // 20),
}


def get_ada_spaces(total_spaces: int) -> int:
    """Calculate required ADA accessible spaces from total parking count."""
    for row in ADA_PARKING_TABLE:
        if row["total_spaces_min"] <= total_spaces <= row["total_spaces_max"]:
            if "note" in row and "%" in row["note"]:
                return max(row["accessible_required"], int(total_spaces * 0.02))
            return row["accessible_required"]
    # Over 1000
    return int(total_spaces * 0.02)


def get_zoning_requirements(zoning_code: str) -> Optional[dict]:
    """Look up dimensional standards for a zoning district."""
    code = zoning_code.upper().strip()
    return ZONING_DISTRICTS.get(code)


def get_flum_requirements(flum_code: str) -> Optional[dict]:
    """Look up FLUM category density/intensity standards."""
    code = flum_code.upper().strip()
    return FLUM_CATEGORIES.get(code)


def get_parking_rate(use_type: str) -> Optional[dict]:
    """Look up parking rate for a use type."""
    return PARKING_REQUIREMENTS.get(use_type)


PINELLAS_CITY_MAP = {
    "SP": "St. Petersburg", "ST PETERSBURG": "St. Petersburg", "ST. PETERSBURG": "St. Petersburg",
    "CLEARWATER": "Clearwater", "CW": "Clearwater", "CWD": "Clearwater",
    "LARGO": "Largo", "LA": "Largo",
    "PINELLAS PARK": "Pinellas Park", "PP": "Pinellas Park", "PPW": "Pinellas Park",
    "DUNEDIN": "Dunedin", "TARPON SPRINGS": "Tarpon Springs", "TS": "Tarpon Springs",
    "SEMINOLE": "Seminole", "KENNETH CITY": "Kenneth City", "GULFPORT": "Gulfport",
    "MB": "Madeira Beach", "MADEIRA BEACH": "Madeira Beach",
    "REDINGTON BEACH": "Redington Beach", "TREASURE ISLAND": "Treasure Island",
    "ST PETE BEACH": "St. Pete Beach", "SOUTH PASADENA": "South Pasadena",
    "BELLEAIR": "Belleair", "BELLEAIR BEACH": "Belleair Beach", "BELLEAIR BLUFFS": "Belleair Bluffs",
    "INDIAN ROCKS BEACH": "Indian Rocks Beach", "INDIAN SHORES": "Indian Shores",
    "NORTH REDINGTON BEACH": "North Redington Beach",
    "OLDSMAR": "Oldsmar", "SAFETY HARBOR": "Safety Harbor",
    "LFPW": "Unincorporated Pinellas (Lealman)", "LEALMAN": "Unincorporated Pinellas (Lealman)",
    "UNINCORPORATED": "Unincorporated Pinellas", "COUNTY": "Unincorporated Pinellas",
}


def expand_city_name(city_abbr: str) -> str:
    if not city_abbr:
        return "Unincorporated Pinellas"
    return PINELLAS_CITY_MAP.get(city_abbr.strip().upper(), city_abbr)


def strip_dor_code(land_use_text: str) -> str:
    if not land_use_text:
        return ""
    text = land_use_text.strip()
    if text and text[0].isdigit():
        parts = text.split(" ", 1)
        if len(parts) > 1:
            return parts[1].strip()
    return text


def get_resilient_session() -> requests.Session:
    session = requests.Session()
    retry_strategy = Retry(total=3, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET", "POST"])
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
        property_use = strip_dor_code(BeautifulSoup(row[7] if len(row) > 7 else "", "html.parser").get_text(strip=True))
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

            detail_url = f"https://www.pcpao.gov/property-details?s={strap}&input={normalized_parcel}&search_option=parcel_number"
            html = session.get(detail_url, timeout=30).text
            soup = BeautifulSoup(html, "html.parser")
            txt = soup.get_text(" ", strip=True)

            m = re.search(r"Land Area:\s*[^\d]*([\d,]+)\s*sf\s*\|\s*[^\d]*([\d.]+)\s*acres", txt, flags=re.IGNORECASE)
            if m:
                sqft = int(m.group(1).replace(",", ""))
                acres = float(m.group(2))

            z = re.search(r"FL\s*(\d{5})", txt)
            if z:
                zip_code = z.group(1)
        except Exception:
            pass

        return {
            "success": True, "parcel_id": normalized_parcel,
            "address": address, "city": city, "zip": zip_code or "",
            "owner": owner, "land_use": property_use,
            "site_area_sqft": f"{sqft:,}" if sqft else "",
            "site_area_acres": f"{acres:.2f}" if acres else "",
            "legal_description": legal_desc, "strap": strap or "",
            "tax_district": tax_district,
        }
    except Exception as exc:
        return {"success": False, "error": f"Error querying PCPAO API: {str(exc)}"}


# ---------------------------------------------------------------------
# Helper functions (matching proposal app patterns)
# ---------------------------------------------------------------------

def labeled_input(
    label: str,
    *,
    value: Any = "",
    placeholder: str = "",
    classes: str = "w-full",
    input_classes: str = "w-full",
    input_props: str = "",
) -> ui.input:
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
    options,
    *,
    value: Any = None,
    classes: str = "w-full",
    select_classes: str = "w-full",
    select_props: str = "",
    with_input: bool = False,
) -> ui.select:
    with ui.column().classes(classes):
        ui.label(label).classes("field-label")
        select_el = ui.select(options, value=value, with_input=with_input)
        if select_classes:
            select_el.classes(select_classes)
        if select_props:
            select_el.props(select_props)
        return select_el


def validate_parcel_id(parcel_id: str) -> tuple[bool, str]:
    if not parcel_id:
        return False, "Parcel ID cannot be empty"
    if len(parcel_id) > 30:
        return False, "Parcel ID must be 30 characters or less"
    if not re.match(r"^[A-Za-z0-9\-\s\.]+$", parcel_id):
        return False, "Invalid characters in parcel ID"
    return True, ""


def safe_float(val: Any, default: float = 0.0) -> float:
    if val is None or val == "":
        return default
    try:
        return float(str(val).replace(",", ""))
    except (TypeError, ValueError):
        return default


def safe_int(val: Any, default: int = 0) -> int:
    if val is None or val == "":
        return default
    try:
        return int(float(str(val).replace(",", "")))
    except (TypeError, ValueError):
        return default


def fmt_num(val: Any) -> str:
    if val is None or val == "":
        return ""
    try:
        n = float(str(val).replace(",", ""))
        if n == int(n):
            return f"{int(n):,}"
        return f"{n:,.2f}"
    except (TypeError, ValueError):
        return str(val)


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
# Zoning map URL helper (same pattern as proposal app)
# ──────────────────────────────────────────────────────────────────────

ZONING_MAP_URLS = {
    # Unincorporated Pinellas County
    "Unincorporated Pinellas": "https://pinellas-egis.maps.arcgis.com/apps/InformationLookup/index.html?appid=d28c337acb184a3986bade031bcdb627",
    "Unincorporated Pinellas (Lealman)": "https://pinellas-egis.maps.arcgis.com/apps/InformationLookup/index.html?appid=d28c337acb184a3986bade031bcdb627",
    # Major cities
    "St. Petersburg": "https://egis.stpete.org/portal/apps/webappviewer/index.html?id=f0ff270cad0940a2879b38e955319dfa",
    "Clearwater": "https://www.arcgis.com/apps/webappviewer/index.html?id=1787a41a5bc7484fa499f6f4a13539ac",
    "Largo": "https://www.arcgis.com/apps/webappviewer/index.html?id=5f1e359449bb4be6a98cc51450909603",
    "Pinellas Park": "https://pinellas-park.maps.arcgis.com/apps/webappviewer/index.html?id=0e17a532289848c4b7fcc2de3c993771",
    "Dunedin": "https://dunedin.maps.arcgis.com/apps/webappviewer/index.html?id=b9f8e53fa3de48fbb0321f56f5e9b4e7",
    "Tarpon Springs": "https://tarpon-springs.maps.arcgis.com/apps/webappviewer/index.html?id=c2e67a2cbb6847399af4ed29c12d1e74",
    "Seminole": "https://seminole-fl.maps.arcgis.com/apps/webappviewer/index.html?id=c5a3ee3f9f454e3e8c5ce76c7f2e4b44",
    "Safety Harbor": "https://cityofsafetyharbor.maps.arcgis.com/apps/webappviewer/index.html?id=0a0f3b7e0f5a4c66b7c64d74c5b0c8a8",
    "Oldsmar": "https://oldsmar.maps.arcgis.com/apps/webappviewer/index.html?id=df03f371de8045adb9a3f1c9fca6e6b8",
    # Beach communities + smaller towns
    "Gulfport": "https://pinellas-egis.maps.arcgis.com/apps/InformationLookup/index.html?appid=d28c337acb184a3986bade031bcdb627",
    "St. Pete Beach": "https://pinellas-egis.maps.arcgis.com/apps/InformationLookup/index.html?appid=d28c337acb184a3986bade031bcdb627",
    "Treasure Island": "https://pinellas-egis.maps.arcgis.com/apps/InformationLookup/index.html?appid=d28c337acb184a3986bade031bcdb627",
    "Madeira Beach": "https://pinellas-egis.maps.arcgis.com/apps/InformationLookup/index.html?appid=d28c337acb184a3986bade031bcdb627",
    "Redington Beach": "https://pinellas-egis.maps.arcgis.com/apps/InformationLookup/index.html?appid=d28c337acb184a3986bade031bcdb627",
    "North Redington Beach": "https://pinellas-egis.maps.arcgis.com/apps/InformationLookup/index.html?appid=d28c337acb184a3986bade031bcdb627",
    "Redington Shores": "https://pinellas-egis.maps.arcgis.com/apps/InformationLookup/index.html?appid=d28c337acb184a3986bade031bcdb627",
    "Indian Rocks Beach": "https://pinellas-egis.maps.arcgis.com/apps/InformationLookup/index.html?appid=d28c337acb184a3986bade031bcdb627",
    "Indian Shores": "https://pinellas-egis.maps.arcgis.com/apps/InformationLookup/index.html?appid=d28c337acb184a3986bade031bcdb627",
    "Belleair": "https://pinellas-egis.maps.arcgis.com/apps/InformationLookup/index.html?appid=d28c337acb184a3986bade031bcdb627",
    "Belleair Beach": "https://pinellas-egis.maps.arcgis.com/apps/InformationLookup/index.html?appid=d28c337acb184a3986bade031bcdb627",
    "Belleair Bluffs": "https://pinellas-egis.maps.arcgis.com/apps/InformationLookup/index.html?appid=d28c337acb184a3986bade031bcdb627",
    "South Pasadena": "https://pinellas-egis.maps.arcgis.com/apps/InformationLookup/index.html?appid=d28c337acb184a3986bade031bcdb627",
    "Kenneth City": "https://pinellas-egis.maps.arcgis.com/apps/InformationLookup/index.html?appid=d28c337acb184a3986bade031bcdb627",
}

# NOTE: Smaller beach communities and towns that don't have their own GIS
# viewer fall back to the Pinellas County unincorporated lookup app, which
# includes PPC zoning data for all jurisdictions within the county.
# [Unverified] Some city-specific app IDs above (Dunedin, Tarpon Springs,
# Seminole, Safety Harbor, Oldsmar) were constructed from search results
# and should be verified by opening each URL. If a city URL doesn't load,
# the county fallback will still work.


def _build_map_url_with_address(map_url: Optional[str], address: str, city: str, zip_code: str) -> Optional[str]:
    """Append address as a ?find= parameter for ArcGIS apps that support it."""
    if not map_url or not address:
        return map_url
    if not any(token in map_url.lower() for token in ("arcgis.com/apps", "webappviewer", "informationlookup", "experiencebuilder")):
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


def get_zoning_map_url(city: str, address: str = "", zip_code: str = "") -> Optional[str]:
    """Get zoning map URL for a city, optionally deep-linked to an address."""
    if not city:
        base = ZONING_MAP_URLS.get("Unincorporated Pinellas")
        return _build_map_url_with_address(base, address, "", zip_code)

    # Exact match first
    base = ZONING_MAP_URLS.get(city)

    # Fuzzy match
    if not base:
        city_lower = city.strip().lower()
        for key, url in ZONING_MAP_URLS.items():
            if key.lower() in city_lower or city_lower in key.lower():
                base = url
                break

    # Unincorporated fallback
    if not base and "unincorporated" in city.lower():
        base = ZONING_MAP_URLS.get("Unincorporated Pinellas")

    # County fallback for any Pinellas city we don't have a specific URL for
    if not base:
        base = ZONING_MAP_URLS.get("Unincorporated Pinellas")

    return _build_map_url_with_address(base, address, city, zip_code)


# ──────────────────────────────────────────────────────────────────────
# Requirements calculation
# ──────────────────────────────────────────────────────────────────────

def build_requirements_markdown() -> str:
    zoning_code = (state.get("zoning") or "").strip().upper()
    flu_code = (state.get("future_land_use") or "").strip().upper()
    site_sf = safe_float(state.get("site_area_sqft"))

    if not zoning_code and not flu_code:
        return "*Enter Zoning and/or Future Land Use to see requirements.*"

    lines: List[str] = []

    # Dimensional standards
    zd = ZONING_DISTRICTS.get(zoning_code)
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
    flu = FLUM_CATEGORIES.get(flu_code)
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
            if zoning_code in flu["compatible_zoning"]:
                lines.append(f"✅ Zoning **{zoning_code}** is consistent with FLU **{flu_code}**")
            else:
                lines.append(f"⚠️ Zoning **{zoning_code}** may not be consistent with FLU **{flu_code}** — compatible: {', '.join(flu['compatible_zoning'])}")
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
    use_type = state.get("use_type", "")
    building_sf = safe_float(state.get("building_sf"))
    num_units = safe_int(state.get("num_units"))

    if not use_type:
        return "*Select a proposed use type to calculate parking requirements.*"

    rate = PARKING_REQUIREMENTS.get(use_type)
    if not rate:
        return f"⚠️ Use type **{use_type}** not found in parking tables."

    lines: List[str] = []
    lines.append(f"### Parking Analysis — {use_type}")
    lines.append(f"**Rate:** {rate['min_rate']}")
    if rate.get("max_limit"):
        lines.append(f"**Maximum:** {rate['max_limit']}")
    lines.append("")

    # Calculate
    calc_spaces = 0
    max_spaces = None
    unit = rate.get("unit", "")

    if unit == "1,000 sf GFA" and building_sf > 0:
        calc_spaces = math.ceil(rate["min_per_unit"] * (building_sf / 1000))
        if rate.get("max_limit"):
            try:
                max_rate = float(rate["max_limit"].split(" ")[0])
                max_spaces = math.ceil(max_rate * (building_sf / 1000))
            except (ValueError, IndexError):
                pass
        lines.append(f"Building area: **{fmt_num(building_sf)} sf GFA**")
    elif unit == "dwelling unit" and num_units > 0:
        calc_spaces = math.ceil(rate["min_per_unit"] * num_units)
        lines.append(f"Dwelling units: **{num_units}**")
    elif num_units > 0 and rate.get("min_per_unit"):
        calc_spaces = math.ceil(rate["min_per_unit"] * num_units)
        lines.append(f"Units ({unit}): **{num_units}**")
    else:
        lines.append(f"*Enter {'building SF' if unit == '1,000 sf GFA' else 'number of ' + unit + 's'} to calculate.*")
        return "\n".join(lines)

    ada = get_ada_spaces(calc_spaces) if calc_spaces > 0 else 0
    bike = BICYCLE_PARKING["calculation"](calc_spaces) if calc_spaces > 0 else 0

    lines.append("")
    lines.append("| Requirement | Spaces |")
    lines.append("|-------------|--------|")
    lines.append(f"| **Required Minimum** | **{calc_spaces}** |")
    if max_spaces:
        lines.append(f"| Maximum Allowed | {max_spaces} |")
    lines.append(f"| ADA Accessible | {ada} |")
    lines.append(f"| Bicycle | {bike} |")
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


# ──────────────────────────────────────────────────────────────────────
# Refresh functions
# ──────────────────────────────────────────────────────────────────────

def refresh_requirements() -> None:
    if "requirements_md" in ui_refs:
        ui_refs["requirements_md"].set_content(build_requirements_markdown())


def refresh_parking() -> None:
    if "parking_md" in ui_refs:
        ui_refs["parking_md"].set_content(build_parking_markdown())


def refresh_all() -> None:
    refresh_requirements()
    refresh_parking()


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

                zoning_options = {code: f"{code} — {d['name']}" for code, d in ZONING_DISTRICTS.items()}
                flu_options = {code: f"{code} — {d['name']}" for code, d in FLUM_CATEGORIES.items()}

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

                use_options = {k: k for k in PARKING_REQUIREMENTS.keys()}
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

ui.run(
    title="Dev Code Lookup",
    port=8080,
    reload=True,
    show=True,
)
