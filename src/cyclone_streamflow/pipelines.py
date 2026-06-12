"""Methods that run sequences of methods."""
from pathlib import Path
from typing import Optional
import logging

import geopandas as gpd

from .configuration import DataType, Configuration
from .data_retrieval import download_data_source
from .data_processing import (
    DataProcessor,
    process_gages_ii,
    process_ibtracs,
    process_nwps
)

LOGGER: logging.Logger = logging.getLogger(__name__)
"""Module-level logger."""

DATA_PROCESSING_FUNCTIONS: dict[DataType, DataProcessor] = {
    DataType.IBTRACS: process_ibtracs,
    DataType.GAGES_II: process_gages_ii,
    DataType.NWPS: process_nwps
}
"""Mapping from DataType enums to DataProcessor callables."""

def download_all_data(
        configuration: Configuration
) -> dict[DataType, Path]:
    """
    Reads configuration file and downloads all required data.
    
    Parameters
    ----------
    configuration : Configuration
        Validated Configuration object.

    Returns
    -------
    dict[DataType, Path]
        Dictionary mapping DataType objects to downloaded file paths.
    """
    # Download files
    return {ds.data_type: download_data_source(ds, configuration.data_directory) for ds in configuration.data_sources}

def run_data_processor(
        source: Path,
        data_processor: DataProcessor,
        geoparquet_filepath: Path
) -> gpd.GeoDataFrame:
    """
    If geoparquet_filepath exists, read and return GeoDataFrame. Otherwise, call
    data_processor on source, save and return result.
    
    Parameters
    ----------
    sources : pathlib.Path
        Path to downloaded data.
    data_processor : DataProcessor
        DataProcessor callables.
    geoparquet_filepath : pathlib.Path
        File path to save resulting GeoDataFrame for later retrieval.

    Returns
    -------
    geopandas.GeoDataFrame
        Processed GeoDataFrame object.
    """
    # Check for output filepath
    if geoparquet_filepath.exists():
        LOGGER.info("Found %s", geoparquet_filepath)
        return gpd.read_parquet(geoparquet_filepath)

    # Process and save
    gdf = data_processor(source)
    LOGGER.info("Building %s", geoparquet_filepath)
    gdf.to_parquet(geoparquet_filepath)
    return gdf

def process_all_data(
        sources: dict[DataType, Path],
        data_processors: Optional[dict[DataType, DataProcessor]] = None,
        directory: Path = Path(".")
) -> dict[DataType, gpd.GeoDataFrame]:
    """
    Applies appropriate data processors to downloaded data sources.
    
    Parameters
    ----------
    sources : dict[DataType, Path]
        Dictionary mapping DataType objects to downloaded file paths.
    data_processors : dict[DataType, DataProcessor]
        Mapping from DataType enums to DataProcessor callables. Defaults to module
            defined processors.
    directory : pathlib.Path, default "."
        Directory to save processed GeoDataFrame geoparquet files.

    Returns
    -------
    dict[DataType, geopandas.GeoDataFrame]
        Dictionary mapping DataType objects to processed GeoDataFrame objects.
    """
    # Handle processors
    if data_processors is None:
        data_processors = DATA_PROCESSING_FUNCTIONS

    # Process files
    return {t: run_data_processor(sources[t], p, directory / f"{t}.parquet") for t, p in data_processors.items()}
