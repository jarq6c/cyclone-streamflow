# Cyclone Streamflow Analysis Pipeline

An end-to-end Python data integration pipeline designed to quantify cyclone-driven hydrologic impacts across the United States. The package downloads historical tropical cyclone tracks (IBTrACS) and river basin boundary geometries, performs spatial buffer intersects, queries continuous USGS streamflow observations via asynchronous web clients, and aggregates peak streamflow discharge ($cfs$) coincident with individual storm events.

---

## Architecture & Workflow

```
┌─────────────────┐      ┌─────────────────┐
│ IBTrACS Tracks  │      │   NWM Basins    │
└────────┬────────┘      └────────┬────────┘
         │                        │
         └───────────┬────────────┘
                     ▼
           [ Spatial Buffer Join ]
                     │
                     ▼
        [ Storm-Basin Event Windows ]
                     │
                     ▼
         [ SQLite Download Manifest ]
                     │
                     ▼
         [ USGS Streamflow Client ]
                     │
                     ▼
       [ Hive Parquet Store (01/1978) ]
                     │
                     ▼
        [ Polars Lazy Partition Join ]
                     │
                     ▼
       `cyclone_peak_streamflow.parquet`

```

The pipeline operates in four main stages:

1. **Data Ingestion & Standardized Reprojection**: Automates fetching remote NetCDF, GeoPackage, Shapefile, and CSV data sources defined in `configuration.json`. Geometries are clean-projected to North America Equidistant Conic (`ESRI:102010`).
2. **Spatial Distance Intersection**: Buffers National Water Model (NWM) assimilation basin boundaries to extract tropical cyclone tracks within $400\text{ km}$ of each river basin, generating site-specific storm temporal windows (`start` to `end`).
3. **Partitioned Streamflow Ingestion**: Tracks progress via a localized SQLite checkpoint manifest (`streamflow_manifest.sqlite3`). Batched asynchronous requests retrieve continuous USGS unit-value streamflow observations during storm windows, saving records to a Hive-partitioned Parquet dataset (`prefix=XX/year=YYYY/`).
4. **Lazy Peak Discharge Aggregation**: Uses Polars lazy frames to execute exact multi-column joins (`usgs_site_code`, `prefix`, `year`) against the Hive partition tree, extracting maximum volumetric flow rate (`peak_streamflow_cfs`) per storm event.

---

## Data Sources

The framework automatically ingests and attributes the following datasets:

| Dataset | Format | Source | Description |
| :--- | :--- | :--- | :--- |
| **IBTrACS** | NetCDF (`.nc`) | NOAA NCEI | Global tropical cyclone best track archive (1980–Present). |
| **GAGES-II** | Shapefile (`.zip`) | USGS | Geospatial attributes and reference basin boundaries. |
| **NWPS** | CSV (`.csv`) | NOAA OWP | National Water Prediction Service gauge metadata and flood stages. |
| **GAGES-III** | CSV (`.csv`) | USGS | Environmental setting and screening metadata for USGS stream gages. |
| **NWM Basins** | GeoPackage (`.gpkg`)| HydroShare | Basin boundary geometries for NWM assimilation streamgages. |

---

## Installation

### Prerequisites
* **Python**: `3.11` or higher
* **GDAL / GEOS**: Required for spatial dependencies (`geopandas`, `pyogrio`)

### Setup
1. Clone the repository:
```bash
git clone https://github.com/jarq6c/cyclone-streamflow
cd cyclone-streamflow
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. (Optional) Configure USGS API Key:
Save your USGS Water Data API key inside `./api.key` to bypass standard public rate limits.

---

## Usage

### Configuration

Data sources, file locations, and intermediate artifact definitions are declared in `configuration.json`.

```json
{
    "data_directory": "./data",
    "api_key_file": "./api.key",
    "data_sources": [...],
    "processed_data": {
        "basin_storms": {"path": "usgs_basin_storms.parquet", "description": "Storm tracks mapped to streamflow basins."},
        "nwm_basin_storms": {"path": "nwm_basin_storms.parquet", "description": "Storm tracks mapped to NWM assimilation gauge basins."},
        "streamflow": {"path": "streamflow", "description": "Streamflow coincident with individual storm events."},
        "streamflow_manifest": {"path": "streamflow_manifest.sqlite3", "description": "Tracks progress of streamflow downloads."}
    }
}

```

### Running the Pipeline

Execute the full download, spatial join, and streamflow extraction workflow:

```bash
python main.py
```

### Script Execution Flow

When executed, `main.py` performs the following steps:

1. Validates `configuration.json` schema via Pydantic.

2. Downloads missing raw dataset files and generates Markdown citation files.

3. Processes NetCDF tracks and spatial basin shapefiles into unified GeoDataFrames.

4. Computes spatial overlaps and initializes the SQLite partition manifest.

5. Fetches streamflow data in batches, updating SQLite partition status (`PENDING` -> `PROCESSING` -> `DONE`).

6. Aggregates maximum discharge and exports `data/cyclone_peak_streamflow.parquet`.

---

## Directory Structure

```text
├── configuration.json        # Main configuration file containing URLs, paths, and metadata
├── main.py                   # Primary pipeline execution entry point
├── requirements.txt          # Package dependencies
└── src/
    └── cyclone_streamflow/
        ├── __init__.py
        ├── configuration.py  # Pydantic schema models and column mappings
        ├── data_processing.py# Geospatial transformation and cleanup routines
        ├── data_retrieval.py # HTTP ingestion and USGS water data API clients
        ├── manifest.py       # SQLite database manager for download checkpointing
        └── pipelines.py      # Spatial buffer joins and sequence orchestrators

```

---

## Output Schema

The final output file (`cyclone_peak_streamflow.parquet`) contains the calculated peak streamflow values for each site-storm event pair:

| Field | Type | Description |
| --- | --- | --- |
| `usgs_site_code` | String | USGS station identifier (e.g., `"USGS-01013500"`).|
| `storm` | String | Unique IBTrACS storm identifier string.|
| `name` | String | Official tropical cyclone name.|
| `start` | Datetime (UTC) | Beginning timestamp of the storm event window.|
| `end` | Datetime (UTC) | Ending timestamp of the storm event window.|
| `peak_streamflow_cfs` | Float64 | Maximum recorded volumetric streamflow discharge in cubic feet per second ($cfs$).|

---

## Attribution

This software is developed for scientific hydrological research. Data retrieved through this package requires proper attribution to NOAA NCEI, NOAA OWP, and the U.S. Geological Survey (USGS). Citations for all downloaded datasets are generated dynamically during execution and stored in markdown format within your configured `data_directory`.
