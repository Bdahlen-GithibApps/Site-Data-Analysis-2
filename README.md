# Pinellas County Development Code Lookup

NiceGUI app for parcel-driven development requirements lookup — unincorporated Pinellas County, FL.

Refactored into a modular architecture: the NiceGUI frontend (`app.py`) imports from domain agents
and shared tools; all data lives in JSON files under `data/`.

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

## Architecture

```
app.py                      # NiceGUI frontend only (imports from agents/ and tools/)
agents/
    __init__.py
    orchestrator.py         # Routes queries to sub-agents; convenience entry point
    property_agent.py       # Parcel lookup — strategy pattern per county
    zoning_agent.py         # Zoning + FLUM data queries
    parking_agent.py        # Parking space calculations (motor vehicle, ADA, bicycle)
    landscape_agent.py      # Landscape buffer/tree/irrigation requirements
data/
    pinellas/
        zoning.json         # ZONING_DISTRICTS — dimensional standards per district
        flum.json           # FLUM_CATEGORIES — density/intensity limits
        parking.json        # Parking requirements, ADA table, stall dimensions, bicycle rule
        maps.json           # City name map + zoning map URLs
        landscape.json      # Landscape code data (Ch. 138, Art. IV)
tools/
    __init__.py
    helpers.py              # Numeric helpers, UI component factories, map URL builder
    scraper.py              # HTTP session + PCPAO scraper + city/land-use name helpers
    arcgis_client.py        # ArcGIS REST API client for spatial zoning/FLU queries
requirements.txt            # nicegui, requests, beautifulsoup4
Dockerfile
README.md
```

## Adding a New County

1. Create `data/<county_lowercase>/` and add `zoning.json`, `flum.json`, `parking.json`, `maps.json`, `landscape.json`.
2. Add a scraper function in `tools/scraper.py` (or a new file).
3. Register the county in `agents/property_agent.py` under `_COUNTY_STRATEGIES`.
4. Optionally add ArcGIS endpoints to `tools/arcgis_client.py`.
5. Pass the county name to `ZoningAgent`, `ParkingAgent`, `LandscapeAgent` when constructing `OrchestratorAgent`.
