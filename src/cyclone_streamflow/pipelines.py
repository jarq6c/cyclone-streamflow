"""Methods that run sequences of methods."""
from pathlib import Path
from typing import Optional

import geopandas as gpd

from .configuration import DataType, Configuration
from .data_retrieval import download_data_source
from .data_processing import (
    DataProcessor,
    process_gages_ii,
    process_ibtracs,
    process_nwps
)

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

def process_all_data(
        sources: dict[DataType, Path],
        data_processors: Optional[dict[DataType, DataProcessor]] = None
) -> dict[DataType, gpd.GeoDataFrame]:
    """
    Applies appropriate data processors to downloaded data sources.
    
    Parameters
    ----------
    sources : dict[DataType, Path]
        Dictionary mapping DataType objects to downloaded file paths.
    data_processors : dict[DataType, DataProcessor]
        Mapping from DataType enums to DataProcessor callables.

    Returns
    -------
    dict[DataType, geopandas.GeoDataFrame]
        Dictionary mapping DataType objects to processed GeoDataFrame objects.
    """
    # Handle processors
    if data_processors is None:
        data_processors = DATA_PROCESSING_FUNCTIONS

    # Process files
    return {t: p(sources[t]) for t, p in data_processors.items()}
