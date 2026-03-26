import requests, json, re

s = requests.Session()
lat, lon = 27.883, -82.803
geom = json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}})

# 1. FEMA Flood Zone
print("=== FEMA Flood Zone ===")
r = s.get(
    "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query",
    params={"geometry": geom, "geometryType": "esriGeometryPoint", "inSR": "4326",
            "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE,DEPTH",
            "returnGeometry": "false", "f": "json"},
    timeout=20,
)
print("HTTP:", r.status_code)
d = r.json()
for f in d.get("features", []):
    print(f["attributes"])

# 2. Pinellas SurveyCoastal layers (CHHA?)
print("\n=== Pinellas SurveyCoastal layers ===")
r2 = s.get("https://egis.pinellas.gov/gis/rest/services/PublicWebGIS/SurveyCoastal/MapServer", params={"f": "json"}, timeout=10)
d2 = r2.json()
for lyr in d2.get("layers", []):
    print(lyr.get("id"), lyr.get("name"))

# 3. Pinellas Landuse_Zoning layers
print("\n=== Pinellas Landuse_Zoning layers ===")
r3 = s.get("https://egis.pinellas.gov/gis/rest/services/PublicWebGIS/Landuse_Zoning/MapServer", params={"f": "json"}, timeout=10)
d3 = r3.json()
for lyr in d3.get("layers", []):
    print(lyr.get("id"), lyr.get("name"))

# 4. Pinellas General layers
print("\n=== Pinellas General layers ===")
r4 = s.get("https://egis.pinellas.gov/gis/rest/services/PublicWebGIS/General/MapServer", params={"f": "json"}, timeout=10)
d4 = r4.json()
for lyr in d4.get("layers", []):
    print(lyr.get("id"), lyr.get("name"))

# 5. Florida DEP sinkhole data
print("\n=== FL DEP / FGS Sinkhole ===")
try:
    r5 = s.get("https://ca.dep.state.fl.us/arcgis/rest/services/OpenData/FGS_Sinkholes/MapServer/0/query",
        params={"geometry": geom, "geometryType": "esriGeometryPoint", "inSR": "4326",
                "distance": 2000, "units": "esriSRUnit_Foot",
                "outFields": "VERIFIED,SINK_TYPE,SINK_DATE", "returnGeometry": "false", "f": "json"},
        timeout=15)
    print("HTTP:", r5.status_code, r5.text[:300])
except Exception as e:
    print("Error:", e)

# 6. Try Pinellas Jurisdictions for CHHA
print("\n=== Pinellas Jurisdictions layers ===")
r6 = s.get("https://egis.pinellas.gov/gis/rest/services/PublicWebGIS/Jurisdictions/MapServer", params={"f": "json"}, timeout=10)
d6 = r6.json()
for lyr in d6.get("layers", []):
    print(lyr.get("id"), lyr.get("name"))


# 2. NWI Wetlands
print("\n=== NWI Wetlands ===")
r2 = s.get(
    "https://fwsprimary.wim.usgs.gov/server/rest/services/Wetlands/MapServer/0/query",
    params={"geometry": geom, "geometryType": "esriGeometryPoint", "inSR": "4326",
            "distance": 500, "units": "esriSRUnit_Foot",
            "outFields": "WETLAND_TYPE,ATTRIBUTE,ACRES",
            "returnGeometry": "false", "f": "json"},
    timeout=20,
)
print("HTTP:", r2.status_code)
d2 = r2.json()
for f in d2.get("features", [])[:5]:
    print(f["attributes"])

# 3. Pinellas PublicWebGIS service list
print("\n=== Pinellas overlay services ===")
r3 = s.get("https://egis.pinellas.gov/gis/rest/services/PublicWebGIS", params={"f": "json"}, timeout=10)
names = re.findall(r'"name":"([^"]+)"', r3.text)
flood = [n for n in names if any(x in n.upper() for x in ["CHHA", "FLOOD", "COASTAL", "HAZARD", "WETLAND", "ENVIRON", "OVERLAY"])]
print(flood)
print("All services:", names)

# 4. FEMA FIRM panel for BFE / panel number
print("\n=== FEMA FIRM Panels (layer 3) ===")
r4 = s.get(
    "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/3/query",
    params={"geometry": geom, "geometryType": "esriGeometryPoint", "inSR": "4326",
            "outFields": "DFIRM_ID,PANEL,EFF_DATE,ST_FIPS,CO_FIPS",
            "returnGeometry": "false", "f": "json"},
    timeout=20,
)
d4 = r4.json()
for f in d4.get("features", []):
    print(f["attributes"])
