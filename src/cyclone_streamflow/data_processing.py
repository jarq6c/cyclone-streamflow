"""Methods for transforming and cleaning source data."""
from pathlib import Path
from typing import Literal
from enum import StrEnum
import logging
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from collections.abc import Hashable

import xarray as xr
import geopandas as gpd
import pandas as pd
from pandas._typing import DtypeArg

class IBTrACSColumn(StrEnum):
    """IBTrACS NetCDF fields."""
    DIST2LAND = "dist2land"
    STORM_NAME = "name"
    STORM_TYPE = "nature"
    STORM_CATEGORY = "usa_sshs"
    LONGITUDE = "lon"
    LATITUDE = "lat"
    STORM_ID = "storm"
    LIFETIME_MAXIMUM = "lifetime_max_intensity"
    TIME = "time"

GLOBAL_CRS: Literal["ESRI:102010"] = "ESRI:102010"
"""Distance preserving CRS string. North America Equidistant Conic."""

LOGGER: logging.Logger = logging.getLogger(__name__)
"""Module-level logger."""

NWPS_COLUMN_DATATYPES: dict[Hashable, DtypeArg] = {
    "location name": "string",
    "proximity": "string",
    "river/water-body name": "string",
    "nws shef id": "string",
    "location type": "string",
    "usgs id": "string",
    "latitude": "float32",
    "longitude": "float32",
    "wfo": "string",
    "rfc": "string",
    "state": "string",
    "county": "string",
    "wrr": "string",
    "timezone": "string",
    "inundation": "bool",
    "elevation": "float32",
    "action stage": "float32",
    "flood stage": "float32",
    "moderate flood stage": "float32",
    "major flood stage": "float32",
    "flood stage unit": "string",
    "coeid": "string",
    "hydrograph page": "string",
    "pedts": "string",
    "in service": "bool",
    "hemisphere": "string",
    "low water threshold value / units": "string",
    "forecast status": "string",
    "display low water impacts": "bool",
    "low flow display": "bool",
    "give data attribution": "bool",
    "attribution wording": "string",
    "fema wms": "string",
    "probabilistic site": "bool",
    "weekly chance probabilistic enabled": "bool",
    "short-term probabilistic enabled": "bool",
    "chance of exceeding probabilistic enabled": "bool",
    "nrldb vertical datum name": "string",
    "nrldb vertical datum": "string",
    "navd88 vertical datum": "string",
    "ngvd29 vertical datum": "string",
    "msl vertical datum": "string",
    "other vertical datum": "string",
    "reach id": "string"
}
"""Mapping from NWPS All Gauges Report column names to pandas data types."""

def process_ibtracs(
        source: Path,
        maximum_distance: float = 400.0,
        source_crs: str = "EPSG:4326",
        output_crs: str = GLOBAL_CRS,
        geometry_column: str = "geometry"
) -> gpd.GeoDataFrame:
    """Read IBTrACS source NetCDF data, extract relevant columns, limit to cyclones
    potentially generating rainfall overland, and return a GeoDataFrame.
    
    Parameters
    ----------
    source : pathlib.Path
        Path to source NetCDF.
    maximum_distance : float, default 400.0
        Maximum distance to land in km of cyclone centers to include in resulting
            GeoDataFrame.
    source_crs : str, default 'EPSG:4326'
        CRS of NetCDF cyclone tracks.
    output_crs : str, default 'ESRI:102010'
        CRS of returned GeoDataFrame. Defaults to North America Equidistant Conic.
    geometry_column : str, default 'geometry'
        Name of geopandas geometry column.
    
    Returns
    -------
    geopandas.GeoDataFrame
        Georeferenced cyclone tracks within maximum_distance of land.
    """
    LOGGER.info("Processing %s", source)

    # Open dataset
    with xr.open_dataset(source) as ds:
        # Extract distance to land, nature, and categories; convert to DataFrame
        df = ds[[
            IBTrACSColumn.DIST2LAND,
            IBTrACSColumn.STORM_CATEGORY,
            IBTrACSColumn.STORM_NAME,
            IBTrACSColumn.STORM_TYPE
        ]].to_dataframe()

    # Drop NaN
    df = df[~df[IBTrACSColumn.DIST2LAND].isna()]

    # Retain near land cyclones
    df = df[df[IBTrACSColumn.DIST2LAND] <= maximum_distance]

    # Determine life-time maximum intensities
    lmi = df[[IBTrACSColumn.STORM_CATEGORY]].dropna().reset_index().groupby(
        IBTrACSColumn.STORM_ID
    ).max()
    lmi[IBTrACSColumn.STORM_CATEGORY] = lmi[IBTrACSColumn.STORM_CATEGORY].apply("{:.0f}".format)

    # String conversions
    df[IBTrACSColumn.STORM_NAME] = df[IBTrACSColumn.STORM_NAME].str.decode("utf-8")
    df[IBTrACSColumn.STORM_TYPE] = df[IBTrACSColumn.STORM_TYPE].str.decode("utf-8")
    df[IBTrACSColumn.STORM_CATEGORY] = df[IBTrACSColumn.STORM_CATEGORY].map("{:.0f}".format)

    # Add geometry
    df[geometry_column] = gpd.points_from_xy(
        x=df[IBTrACSColumn.LONGITUDE],
        y=df[IBTrACSColumn.LATITUDE],
        crs=source_crs
    )

    # Map lifetime max intensity
    df = df.reset_index()[[
        IBTrACSColumn.STORM_ID,
        IBTrACSColumn.TIME,
        IBTrACSColumn.DIST2LAND,
        IBTrACSColumn.STORM_CATEGORY,
        IBTrACSColumn.STORM_NAME,
        IBTrACSColumn.STORM_TYPE,
        geometry_column
    ]]
    df[IBTrACSColumn.LIFETIME_MAXIMUM] = df[IBTrACSColumn.STORM_ID].map(lmi[IBTrACSColumn.STORM_CATEGORY])

    # Project to distance preserving CRS
    return gpd.GeoDataFrame(df).to_crs(output_crs)

def process_gages_ii(
        source: Path,
        output_crs: str = GLOBAL_CRS,
        boundary_source: str = "boundaries-shapefiles-by-aggeco/bas_ref_all.shp"
) -> gpd.GeoDataFrame:
    """Read GAGES-II boundaries zipfile, extract relevant data, and return a GeoDataFrame.
    
    Parameters
    ----------
    source : pathlib.Path
        Path to source zipfile.
    output_crs : str, default 'ESRI:102010'
        CRS of returned GeoDataFrame. Defaults to North America Equidistant Conic.
    boundary_source: str, default 'boundaries-shapefiles-by-aggeco/bas_ref_all.shp'
        Path to basin boundaries inside source zipfile.
    
    Returns
    -------
    geopandas.GeoDataFrame
        Georeferenced GAGES-II basin geometry.
    """
    # Extract and load shapefile
    with TemporaryDirectory() as td:
        with ZipFile(source) as zf:
            # Extract
            LOGGER.info("Extracting %s", source)
            zf.extractall(path=td)

            # Load
            LOGGER.info("Reading %s", boundary_source)
            return gpd.read_file(
                Path(td) / boundary_source,
                engine="pyogrio",
                use_arrow=True
            ).to_crs(output_crs)

def process_nwps(
        source: Path,
        source_crs: str = "EPSG:4326",
        output_crs: str = GLOBAL_CRS,
        geometry_column: str = "geometry"
) -> gpd.GeoDataFrame:
    """Read NWPS All Gauges report and return a GeoDataFrame.
    
    Parameters
    ----------
    source : pathlib.Path
        Path to source CSV.
    source_crs : str, default 'EPSG:4326'
        CRS of CSV cyclone tracks.
    output_crs : str, default 'ESRI:102010'
        CRS of returned GeoDataFrame. Defaults to North America Equidistant Conic.
    geometry_column : str, default 'geometry'
        Name of geopandas geometry column.
    
    Returns
    -------
    geopandas.GeoDataFrame
        Georeferenced gauge metadata.
    """
    # Read CSV
    df = pd.read_csv(source, dtype=NWPS_COLUMN_DATATYPES)

    # Add geometry
    df[geometry_column] = gpd.points_from_xy(
        x=df["longitude"],
        y=df["latitude"],
        crs=source_crs
    )

    # Fix erroneous reach id
    df.loc[df["reach id"] == "LKLO1 ", "reach id"] = "15396810"

    # Convert reach id to integer
    df["reach id"] = pd.to_numeric(df["reach id"])

    # Convert to GeoDataFrame
    return gpd.GeoDataFrame(df).to_crs(output_crs)
