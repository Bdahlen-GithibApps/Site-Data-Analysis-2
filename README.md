# Site Data Analysis — Multi-Agent Development Code Lookup

**GitHub repository:** <https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2>

A local web app for parcel-driven development requirements lookup.
You run it **on your own computer** — it starts a small web server and
opens in your regular browser at **http://localhost:8080**.

Supports Pinellas County, FL with a modular multi-agent architecture
designed to scale to additional counties.

---

## ⬇️ Get the Code — Download or Clone

There are two ways to get all of these files onto your computer.

---

### Option A — Download as a ZIP (no Git required — easiest)

1. Go to the repository on GitHub:
   **<https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2>**

2. Click the green **`<> Code`** button near the top-right of the file list.

3. Click **"Download ZIP"** from the dropdown.

4. Open the downloaded `.zip` file and **extract** it to a folder on your computer
   (e.g. `C:\Users\You\Documents\Site-Data-Analysis-2` on Windows).

5. Open a terminal / Command Prompt **inside that extracted folder**, then follow
   the [Quick Start](#quick-start) steps below to install dependencies and run the app.

> **Note:** To get the full modular version (with `agents/`, `tools/`, `data/` folders)
> you need to download from the **`copilot/refactor-app-into-modular-architecture`** branch:
>
> 1. Click **`<> Code`** → **"Download ZIP"**
>    — OR use this direct link: [Download ZIP of this branch](https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2/archive/refs/heads/copilot/refactor-app-into-modular-architecture.zip)
> 2. Extract and open a terminal in the extracted folder.
> 3. Follow [Quick Start](#quick-start) below.

---

### ❓ I already have a cloned copy — do I delete the old files?

**No — do not delete the old files or the `.git` folder.**
Instead, copy the new files from inside the extracted ZIP *over* the existing ones.

Here is exactly what to do (Windows example, works the same on Mac/Linux):

**Situation:** Your `Site-Data-Analysis-2` folder looks like this:

```
Site-Data-Analysis-2\            ← your existing repo folder
  .git\                           ← KEEP THIS — never delete it
  .gitignore
  app.py
  Dockerfile
  README.md
  requirements.txt
  Site-Data-Analysis-2-copilot-refactor-ap...\   ← the extracted ZIP subfolder
  Site-Data-Analysis-2-copilot-refactor-ap....zip ← the downloaded ZIP file
```

**Steps:**

1. **Open** the extracted folder (`Site-Data-Analysis-2-copilot-refactor-ap...`).

2. **Select all files and folders inside it** (press `Ctrl+A` on Windows).

3. **Copy** them (`Ctrl+C`).

4. **Go up one level** back into the `Site-Data-Analysis-2` folder.

5. **Paste** (`Ctrl+V`).
   When Windows asks *"Replace the files in the destination?"* click **Replace the files in the destination** (or "Yes to all").
   This will update `app.py`, `README.md`, etc. and add the new `agents/`, `tools/`, and `data/` folders.

6. **Delete** the now-empty extracted subfolder and the `.zip` file — they are no longer needed.

Your `Site-Data-Analysis-2` folder should now look like this:

```
Site-Data-Analysis-2\
  .git\
  .gitignore
  agents\
  app.py
  data\
  Dockerfile
  README.md
  requirements.txt
  run.bat
  run.sh
  tools\
```

7. **Open a terminal / Command Prompt inside `Site-Data-Analysis-2`** and follow [Quick Start](#quick-start) below.

---

### Option B — Clone with Git (recommended)

Git lets you pull updates with a single command in the future.

**Step 1 — Install Git** (skip if you already have it)

| OS | Installer |
|---|---|
| Windows | <https://git-scm.com/download/win> — run the installer, accept all defaults |
| macOS | Open Terminal and type `git --version` — macOS will offer to install it automatically |
| Linux | `sudo apt install git` (Debian/Ubuntu) or `sudo dnf install git` (Fedora) |

**Step 2 — Clone the repository**

Open a terminal (Git Bash on Windows) and run:

```bash
git clone https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2.git
cd Site-Data-Analysis-2
```

This downloads all files into a folder called `Site-Data-Analysis-2`.

**Step 3 — Switch to the modular branch** (to get agents, tools, data folders)

```bash
git checkout copilot/refactor-app-into-modular-architecture
```

**Step 4 — Follow [Quick Start](#quick-start)** to install dependencies and run the app.

---

## 📁 Where are the agents and folders?

> **Note:** If you're viewing this README on the `main` branch and only see `app.py`
> with no subfolders, this PR has not been merged yet.
> Switch to the **`copilot/refactor-app-into-modular-architecture`** branch on GitHub
> (use the branch dropdown) or **merge this PR** to bring the full structure into `main`.

You can browse every file right now on GitHub using these links:

| Folder / File | Description | Browse on GitHub |
|---|---|---|
| `agents/` | All agent modules | [📂 agents/](https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2/tree/copilot/refactor-app-into-modular-architecture/agents) |
| `agents/orchestrator.py` | Routes queries to all sub-agents | [🔗 view](https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2/blob/copilot/refactor-app-into-modular-architecture/agents/orchestrator.py) |
| `agents/property_agent.py` | Parcel lookup (PCPAO scraper) | [🔗 view](https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2/blob/copilot/refactor-app-into-modular-architecture/agents/property_agent.py) |
| `agents/zoning_agent.py` | Zoning + FLUM + ArcGIS queries | [🔗 view](https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2/blob/copilot/refactor-app-into-modular-architecture/agents/zoning_agent.py) |
| `agents/parking_agent.py` | Parking calculation (MV + ADA + bicycle) | [🔗 view](https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2/blob/copilot/refactor-app-into-modular-architecture/agents/parking_agent.py) |
| `agents/landscape_agent.py` | Buffer / tree / irrigation requirements | [🔗 view](https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2/blob/copilot/refactor-app-into-modular-architecture/agents/landscape_agent.py) |
| `tools/` | Shared utilities | [📂 tools/](https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2/tree/copilot/refactor-app-into-modular-architecture/tools) |
| `tools/scraper.py` | PCPAO web scraper | [🔗 view](https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2/blob/copilot/refactor-app-into-modular-architecture/tools/scraper.py) |
| `tools/arcgis_client.py` | ArcGIS REST API client | [🔗 view](https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2/blob/copilot/refactor-app-into-modular-architecture/tools/arcgis_client.py) |
| `tools/helpers.py` | Formatting / validation helpers | [🔗 view](https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2/blob/copilot/refactor-app-into-modular-architecture/tools/helpers.py) |
| `data/pinellas/` | Pinellas County JSON data | [📂 data/pinellas/](https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2/tree/copilot/refactor-app-into-modular-architecture/data/pinellas) |
| `data/pinellas/zoning.json` | Zoning district dimensional standards | [🔗 view](https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2/blob/copilot/refactor-app-into-modular-architecture/data/pinellas/zoning.json) |
| `data/pinellas/flum.json` | FLUM density / intensity limits | [🔗 view](https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2/blob/copilot/refactor-app-into-modular-architecture/data/pinellas/flum.json) |
| `data/pinellas/parking.json` | Parking requirements + ADA table | [🔗 view](https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2/blob/copilot/refactor-app-into-modular-architecture/data/pinellas/parking.json) |
| `data/pinellas/landscape.json` | Ch. 138, Art. IV landscape code data | [🔗 view](https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2/blob/copilot/refactor-app-into-modular-architecture/data/pinellas/landscape.json) |
| `data/pinellas/maps.json` | City map + zoning map URLs | [🔗 view](https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2/blob/copilot/refactor-app-into-modular-architecture/data/pinellas/maps.json) |
| `app.py` | NiceGUI frontend (uses all agents) | [🔗 view](https://github.com/Bdahlen-GithibApps/Site-Data-Analysis-2/blob/copilot/refactor-app-into-modular-architecture/app.py) |

---

## Where do I run this?

**On your own machine** — download or clone the repo (see [Get the Code](#️-get-the-code--download-or-clone) above),
open a terminal in the project folder, and follow one of the Quick Start options below.
No hosting, no account, no internet connection required once installed.

## Quick Start

**Requirements:** Python 3.10 or newer — [download from python.org](https://www.python.org/downloads/)

---

### 🪟 Windows — one-liner

1. Install Python from <https://www.python.org/downloads/>
   *(check **"Add Python to PATH"** during installation)*
2. Download / clone this repository
3. In **File Explorer**, double-click **`run.bat`**
   — OR open **Command Prompt** or **PowerShell**, `cd` into the project folder, and type:

```bat
run.bat
```

The script installs dependencies, starts the server, and opens your browser at **http://localhost:8080** automatically.

---

### 🐧 Linux / 🍎 macOS / WSL — one-liner

Open a terminal, `cd` into the project folder, then run:

```bash
bash run.sh
```

The script installs dependencies and starts the server.
Then open **http://localhost:8080** in your browser (the script prints this URL).

---

### Manual steps (any OS)

Open a terminal / Command Prompt in the project folder, then run:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the app
python app.py
```

Then open **http://localhost:8080** in your browser.

> **Windows tip:** if `python` is not recognised, try `py -3` instead.
> **Virtual env (recommended):**
> - Windows: `python -m venv .venv && .venv\Scripts\activate`
> - Linux/macOS: `python -m venv .venv && source .venv/bin/activate`
> then run `pip install -r requirements.txt` inside the activated env.

---

### Docker (any OS with Docker Desktop)

```bash
docker build -t devcode .
docker run -p 8080:8080 devcode
```

Then open **http://localhost:8080** in your browser.

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
├── run.bat               # Windows quick-start (double-click or run from CMD/PowerShell)
├── run.sh                # Linux / macOS / WSL quick-start
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
run.bat             # Windows quick-start script
run.sh              # Linux / macOS / WSL quick-start script
README.md
```

