# Site Data Analysis — Multi-Agent Development Code Lookup

NiceGUI app for parcel-driven development requirements lookup.
Supports Pinellas County, FL with a modular multi-agent architecture
designed to scale to additional counties.

## Run

```bash
pip install -r requirements.txt
python app.py
```

Opens at http://localhost:8080

## Docker

```bash
docker build -t devcode .
docker run -p 8080:8080 devcode
```

## What It Does

1. **Property Lookup** — Enter County + Parcel ID → scrapes PCPAO → auto-fills address, owner, land use, site area
2. **Requirements** — Select Zoning + FLU from the map → shows setbacks, height, lot size, density, FAR, IS ratio
3. **Parking** — Select use type + building SF → calculates required spaces, ADA, bicycle
4. **Landscape** — Shows perimeter buffer, parking lot landscaping, tree canopy, irrigation, sight triangle, and plant material requirements

## Project Structure

```
Site-Data-Analysis-2/
├── app.py                    # NiceGUI frontend (imports from agents/ and tools/)
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py       # Routes queries to all sub-agents
│   ├── property_agent.py     # Parcel lookup (PCPAO, Hillsborough stub, Pasco stub)
│   ├── zoning_agent.py       # Zoning + FLUM + building code lookups + ArcGIS queries
│   ├── parking_agent.py      # Parking calculations (motor vehicle, ADA, bicycle)
│   └── landscape_agent.py    # Landscape buffer/tree/irrigation requirements
├── data/
│   ├── __init__.py
│   └── pinellas/
│       ├── zoning.json       # ZONING_DISTRICTS dimensional standards
│       ├── flum.json         # FLUM_CATEGORIES density/intensity limits
│       ├── parking.json      # PARKING_REQUIREMENTS + ADA table + dimensions + bicycle
│       ├── maps.json         # PINELLAS_CITY_MAP + ZONING_MAP_URLS
│       └── landscape.json    # Ch. 138, Art. IV landscape code data
├── tools/
│   ├── __init__.py
│   ├── scraper.py            # Web scraping utilities (PCPAO, city name expansion)
│   ├── arcgis_client.py      # ArcGIS REST API client for spatial zoning/FLU queries
│   └── helpers.py            # safe_float, safe_int, fmt_num, labeled_input, etc.
├── requirements.txt
├── Dockerfile
└── README.md
```

## How Agents Work

### OrchestratorAgent (`agents/orchestrator.py`)
Accepts a query dict and coordinates all sub-agents:
```python
from agents.orchestrator import OrchestratorAgent

orchestrator = OrchestratorAgent()
results = orchestrator.process({
    "parcel_id": "19-31-17-73166-001-0010",
    "county": "Pinellas",
    "use_type": "Retail (General)",
    "building_sf": 15000,
})
# results["property"] — parcel data
# results["zoning"]   — zoning + FLUM standards
# results["parking"]  — parking calculation
# results["landscape"] — landscape requirements
```

### PropertyAgent (`agents/property_agent.py`)
Strategy pattern for multiple counties. Pinellas uses PCPAO scraper;
other counties return "not yet implemented" placeholders.

### ZoningAgent (`agents/zoning_agent.py`)
Loads zoning and FLUM data from `data/<county>/zoning.json` and
`data/<county>/flum.json`. Optionally queries ArcGIS REST services
to auto-detect zoning/FLU from lat/lon coordinates.

### ParkingAgent (`agents/parking_agent.py`)
Loads parking data from `data/<county>/parking.json`.
Calculates motor vehicle, ADA, and bicycle spaces.

### LandscapeAgent (`agents/landscape_agent.py`)
Loads landscape data from `data/<county>/landscape.json`.
Returns perimeter buffer, parking lot, tree canopy, and irrigation requirements.

## How to Add a New County

1. **Create data files** — add `data/<county>/zoning.json`, `flum.json`,
   `parking.json`, and `landscape.json` following the Pinellas JSON schema.

2. **Register ArcGIS endpoints** — add the county to `ARCGIS_SERVICES` in
   `tools/arcgis_client.py` with the correct zoning and FLU service URLs
   and attribute field names.

3. **Implement property lookup** — add a `_lookup_<county>` method to
   `agents/property_agent.py` and register the county in `SUPPORTED_COUNTIES`.

4. **Add city map** — add a `maps.json` file to `data/<county>/` with
   `city_map` and `zoning_map_urls` for the new county's municipalities.

## Files

```
app.py              # NiceGUI frontend (~760 lines, down from 1,668)
agents/             # Agent modules
tools/              # Shared utilities
data/pinellas/      # Pinellas County data as JSON
requirements.txt    # nicegui, requests, beautifulsoup4, aiohttp
Dockerfile          # Single container
README.md
```

