"""Methods for retrieving required data and documenting citations."""
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import TypedDict, Optional

import requests
import pandas as pd

from hydrotools.waterdata_client.async_web_client import get_all
from hydrotools.waterdata_client.url_builder import build_request_batch_from_queries
from hydrotools.waterdata_client.transformers import to_optimized_dataframe, NoDataError

from .configuration import DataSource

LOGGER: logging.Logger = logging.getLogger(__name__)
"""Module-level logger."""

class RequestParameters(TypedDict):
    """Request arguments for calls to continuous API."""
    monitoring_location_id: str
    datetime: str
    limit: str
    api_key: Optional[str]

def download_data_source(
        source: DataSource,
        directory: Path = Path(".")
) -> Path:
    """Downloads a data associated with a DataSource object.
    
    Parameters
    ----------
    source : DataSource
        DataSource object
    directory : pathlib.Path
        Download directory.
    
    Returns
    -------
    pathlib.Path
        Path to downloaded file.
    """
    # Construct filepaths
    filepath = directory / source.filename
    metadata = directory / source.metadata

    # Download
    if not filepath.exists():
        # Download file
        LOGGER.info("Retrieving %s", source.filename)
        current_time = datetime.now(UTC)
        with filepath.open("wb") as fo:
            fo.write(requests.get(source.url, timeout=900).content)

        # Write metadata
        LOGGER.info("Writing %s", metadata)
        date_string = current_time.strftime("%Y-%m-%d")
        output = "# Citations\n"
        output += "\n".join(
            [" - " + s for s in source.citations]
        ).replace("ACCESS_DATE", date_string)
        with metadata.open("w", encoding="utf-8") as fo:
            fo.write(output)
    else:
        LOGGER.info("%s exists, skipping download", filepath)
    return filepath

def download_storm_streamflow(
        storms: pd.DataFrame,
        api_key: Optional[str] = None
    ) -> pd.DataFrame:
    """Given a dataframe of storm details, retrieve corresponding USGS streamflow.
    
    Parameters
    ----------
    storms: pandas.DataFrame
        Dataframe of storm information. Must contain rows with columns for ['provider_id',
        'start', 'end'].
    
    Returns
    -------
    pandas.DataFrame
        Retrieved streamflow.
    """
    # Extract subset of columns from storms
    subset = storms[["provider_id", "start", "end"]]

    # Build queries
    queries: list[RequestParameters] = []
    for _, provider_id, start, end in subset.itertuples():
        # Build individual query
        start_dt = start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_dt = end.strftime("%Y-%m-%dT%H:%M:%SZ")
        queries.append(RequestParameters(
            monitoring_location_id=f"USGS-{provider_id}",
            datetime=f"{start_dt}/{end_dt}",
            limit="50000",
            api_key=api_key
        ))

    print(queries)
    return pd.DataFrame()
