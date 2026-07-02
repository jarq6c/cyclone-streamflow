"""Project-wide configuration data models."""
import logging
from pathlib import Path
from typing import TypeAlias, Annotated, Any, Literal
from enum import StrEnum
from collections.abc import Hashable

from pydantic import BaseModel, HttpUrl, BeforeValidator
from pandas._typing import DtypeArg

LOGGER: logging.Logger = logging.getLogger(__name__)
"""Module-level logger."""

class DataType(StrEnum):
    """Required data sources."""
    IBTRACS = "IBTrACS"
    GAGES_II = "GAGES_II"
    NWPS = "NWPS"
    GAGES_III = "GAGES_III"
    NWM_BASINS = "NWM_BASINS"

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

class NWMBasinColumn(StrEnum):
    """NWM Basin geometry column labels."""
    PROVIDER_ID = "provider_id"

GLOBAL_CRS: Literal["ESRI:102010"] = "ESRI:102010"
"""Distance preserving CRS string. North America Equidistant Conic."""

class NWPSColumn(StrEnum):
    """NWPS CSV fields."""
    LATITUDE = "latitude"
    LONGITUDE = "longitude"

NWPS_COLUMN_DATATYPES: dict[Hashable, DtypeArg] = {
    "location name": "string",
    "proximity": "string",
    "river/water-body name": "string",
    "nws shef id": "string",
    "location type": "string",
    "usgs id": "string",
    NWPSColumn.LATITUDE: "float32",
    NWPSColumn.LONGITUDE: "float32",
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

GAGES_III_COLUMN_TYPES: dict[Hashable, DtypeArg] = {
    "ID": "string",
    "NWIS_Area": "float32",
    "NHD_Area": "float32",
    "Adj_NWIS_Area": "float32",
    "End_Year": "Int32",
    "Station_Name": "string",
    "Lat_Dec": "float32",
    "Long_Dec": "float32",
    "Source": "string",
    "COMID_Man_QA": "Int64",
    "Gages2_Status": "string",
    "Gages3_Status": "string",
    "Gages3_Screen_Comments": "string",
    "Other_Info_Sources": "string",
    "HDI.Pct.Ag": "float32",
    "HDI.Art.Path": "float32",
    "HDI.Canals": "float32",
    "HDI.NPDES": "float32",
    "HDI.FW.With": "float32",
    "HDI.MDam.Dens": "float32",
    "HDI.Delta.Stg": "float32",
    "HDI.Pct.Urban": "float32",
    "NA_Eco3": "string",
    "Size.Class": "string",
    "Ag.Rank": "string",
    "Art.Path.Rank": "string",
    "Canals.Rank": "string",
    "NPDES.Rank": "string",
    "FW.With.Rank": "string",
    "MDam.Den.Rank": "string",
    "Delta.Stg.Rank": "string",
    "Urban.Rank": "string",
    "Gages2_Screen_Comments": "string"
}
"""Mapping from GAGES-3 column names to pandas data types."""

class GAGESIIIColumn(StrEnum):
    """GAGES-3 CSV fields."""
    LATITUDE = "Lat_Dec"
    LONGITUDE = "Long_Dec"
    BEGIN_DATE = "Begin_Date"
    END_DATE = "End_Date"

def create_directory_path(
        directory_path: str | Path
) -> Path:
    """Custom validation function that returns directory_path as a pathlib.Path
    and creates the directory if it does not already exist.

    Parameters
    ----------
    directory_path : str | pathlib.Path
        Path to directory.
    
    Returns
    -------
    pathlib.Path
        Path to created directory.
    """
    path_object = Path(directory_path)
    if path_object.exists():
        LOGGER.info("Found %s", path_object.resolve())
    else:
        LOGGER.info("Creating %s", path_object)
        path_object.mkdir(exist_ok=True, parents=True)
    return path_object

CustomDirectoryPath: TypeAlias = Annotated[
    Any,
    BeforeValidator(create_directory_path)
]
"""Custom annotated type used to create a directory, if it does not exist."""

class DataSource(BaseModel):
    """
    Pydantic model that defines a data source.
    
    Attributes
    ----------
    data_type : DataType
        Type of data source.
    url : HttpUrl
        Source url.
    citations : list[str]
        List of preferred citations.
    filename : str
        Desired local file name after download.
    metadata : str
        Desired local file name for Markdown metadata.

    """
    data_type: DataType
    url: HttpUrl
    citations: list[str]
    filename: str
    metadata: str

class ProcessedData(BaseModel):
    """
    Pydantic model for different stages of processed data.

    Attributes
    ----------
    path : str
        Filename to save processed data to under data_directory.
    description : str
        Description of data.
    """
    path: str
    description: str

class ProcessedDataStore(BaseModel):
    """
    Tracks different types of processed data.

    Attributes
    ----------
    basin_storms : ProcessedData
        Pydantic model describing joined table of cyclones and streamflow basins.
    nwm_basin_storms : ProcessedData
        Pydantic model describing joined table of cyclones and NWM assimilation gauge basins.
    streamflow : ProcessedData
        Pydantic model indicating streamflow coincident with individual storm events.
    """
    basin_storms: ProcessedData
    nwm_basin_storms: ProcessedData
    streamflow: ProcessedData

class Configuration(BaseModel):
    """
    Project configuration Pydantic model.
    
    Attributes
    ----------
    data_directory : pathlib.Path
        Path to data/download directory.
    api_key_file : pathlib.Path
        Path to USGS API key file.
    data_sources : list[DataSource]
        List of DataSource objects.
    processed_data : ProcessedDataStore
        Pydantic model that track intermediate processed data.

    """
    data_directory: CustomDirectoryPath
    api_key_file: CustomDirectoryPath
    data_sources: list[DataSource]
    processed_data: ProcessedDataStore

def load_configuration(
        configuration_filepath: Path = Path("configuration.json")
) -> Configuration:
    """
    Reads and loads configuration file.
    
    Parameters
    ----------
    configuration_filepath : pathlib.Path
        Path to configuration JSON file.

    Returns
    -------
    Configuration
        Validated Configuration object.
    """
    # Load configuration
    LOGGER.info("Loading %s", configuration_filepath.resolve())
    with configuration_filepath.open("r", encoding="utf-8") as fi:
        return Configuration.model_validate_json(fi.read())
