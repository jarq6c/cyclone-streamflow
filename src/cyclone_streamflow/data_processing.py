"""Methods for transforming and cleaning source data."""
from pathlib import Path
from typing import Literal
from enum import StrEnum
import logging

import xarray as xr
import geopandas as gpd

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
