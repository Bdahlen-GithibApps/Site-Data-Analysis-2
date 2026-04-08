import requests, json

s = requests.Session()
lat, lon = 27.883, -82.803
geom = json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}})

# 1. Pinellas Districts layers
print("=== Pinellas Districts ===")
r = s.get("https://egis.pinellas.gov/gis/rest/services/PublicWebGIS/Districts/MapServer", params={"f": "json"}, timeout=10)
d = r.json()
for lyr in d.get("layers", []):
    print(lyr.get("id"), lyr.get("name"))

# 2. Proximity to CCCL (Coastal Construction Control Line) - within 1000ft?
print("\n=== CCCL Proximity (within 1000ft) ===")
r2 = s.get(
    "https://egis.pinellas.gov/gis/rest/services/PublicWebGIS/SurveyCoastal/MapServer/1/query",
    params={"geometry": geom, "geometryType": "esriGeometryPoint", "inSR": "4326",
            "distance": 1000, "units": "esriSRUnit_Foot",
            "outFields": "*", "returnGeometry": "false", "f": "json"},
    timeout=15,
)
d2 = r2.json()
features = d2.get("features", [])
print("Features within 1000ft of CCCL:", len(features))
if features:
    print(features[0]["attributes"])

# 3. NWI at a coastal/wetland-heavy location (south St Pete near bay)
lat2, lon2 = 27.730, -82.643
geom2 = json.dumps({"x": lon2, "y": lat2, "spatialReference": {"wkid": 4326}})
print("\n=== NWI Wetlands (coastal St Pete) ===")
r3 = s.get(
    "https://fwsprimary.wim.usgs.gov/server/rest/services/Wetlands/MapServer/0/query",
    params={"geometry": geom2, "geometryType": "esriGeometryPoint", "inSR": "4326",
            "distance": 1000, "units": "esriSRUnit_Foot",
            "outFields": "WETLAND_TYPE,ATTRIBUTE,ACRES", "returnGeometry": "false", "f": "json"},
    timeout=20,
)
d3 = r3.json()
print("HTTP:", r3.status_code, "features:", len(d3.get("features", [])))
for f in d3.get("features", [])[:5]:
    print(f["attributes"])

# 4. Try FL DEP alternate sinkhole URL
print("\n=== FL DEP Sinkhole (alternate URL) ===")
for url in [
    "https://geodata.dep.state.fl.us/arcgis/rest/services/OpenData/FGS_Sinkholes/MapServer/0/query",
    "https://ca.dep.state.fl.us/arcgis/rest/services/OpenData/FGS_Sinkholes/FeatureServer/0/query",
]:
    try:
        r4 = s.get(url, params={"geometry": geom, "geometryType": "esriGeometryPoint",
                                 "inSR": "4326", "distance": 2000, "units": "esriSRUnit_Foot",
                                 "outFields": "*", "returnGeometry": "false", "f": "json"}, timeout=12)
        print(url.split("/")[-4], "->", r4.status_code, r4.text[:200])
    except Exception as e:
        print(url, "->", e)

# 5. Check FEMA for AE zone (flood) at coastal St Pete location
print("\n=== FEMA flood at coastal location ===")
r5 = s.get(
    "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query",
    params={"geometry": geom2, "geometryType": "esriGeometryPoint", "inSR": "4326",
            "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE,DEPTH", "returnGeometry": "false", "f": "json"},
    timeout=20,
)
for f in r5.json().get("features", []):
    print(f["attributes"])
