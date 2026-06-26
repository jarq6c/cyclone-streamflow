"""Methods for transforming and cleaning source data."""
from pathlib import Path
from typing import Protocol, Any
import logging
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import xarray as xr
import geopandas as gpd
import pandas as pd

from .configuration import (
    GLOBAL_CRS,
    IBTrACSColumn,
    NWPS_COLUMN_DATATYPES,
    NWPSColumn,
    GAGES_III_COLUMN_TYPES,
    GAGESIIIColumn
)

LOGGER: logging.Logger = logging.getLogger(__name__)
"""Module-level logger."""

class DataProcessor(Protocol):
    """Protocol class that defines the interface for data processing methods."""
    def __call__(self, source: Path, *args: Any, **kwds: Any) -> gpd.GeoDataFrame:
        ...

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
    LOGGER.info("Processing %s", source)

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
        CRS of gauge locations.
    output_crs : str, default 'ESRI:102010'
        CRS of returned GeoDataFrame. Defaults to North America Equidistant Conic.
    geometry_column : str, default 'geometry'
        Name of geopandas geometry column.
    
    Returns
    -------
    geopandas.GeoDataFrame
        Georeferenced gauge metadata.
    """
    LOGGER.info("Processing %s", source)

    # Read CSV
    df = pd.read_csv(source, dtype=NWPS_COLUMN_DATATYPES)

    # Add geometry
    df[geometry_column] = gpd.points_from_xy(
        x=df[NWPSColumn.LONGITUDE],
        y=df[NWPSColumn.LATITUDE],
        crs=source_crs
    )

    # Convert to GeoDataFrame
    return gpd.GeoDataFrame(df).to_crs(output_crs)

def process_gages_iii(
        source: Path,
        source_crs: str = "EPSG:4326",
        output_crs: str = GLOBAL_CRS,
        geometry_column: str = "geometry"
) -> gpd.GeoDataFrame:
    """Read GAGES-3 CSV data and return a GeoDataFrame.
    
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
    LOGGER.info("Processing %s", source)

    # Read CSV
    df = pd.read_csv(source, dtype=GAGES_III_COLUMN_TYPES, parse_dates=[
        GAGESIIIColumn.BEGIN_DATE, GAGESIIIColumn.END_DATE
    ])

    # Add geometry
    df[geometry_column] = gpd.points_from_xy(
        x=df[GAGESIIIColumn.LONGITUDE],
        y=df[GAGESIIIColumn.LATITUDE],
        crs=source_crs
    )

    # Convert to GeoDataFrame
    return gpd.GeoDataFrame(df).to_crs(output_crs)
