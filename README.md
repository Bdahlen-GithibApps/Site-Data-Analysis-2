# Pinellas County Development Code Lookup

Single-file NiceGUI app for parcel-driven development requirements lookup — unincorporated Pinellas County, FL.

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

## Files

```
app.py              # The entire app (everything in one file)
requirements.txt    # nicegui, requests, beautifulsoup4
Dockerfile          # Single container
.gitignore
README.md
```
