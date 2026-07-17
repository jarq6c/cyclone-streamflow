"""Methods for retrieving required data and documenting citations."""
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import TypedDict, Optional
from time import sleep

import requests
import pandas as pd
import numpy as np

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
        api_key: Optional[str] = None,
        batch_size: int = 50,
        sleep_time: float = 19.0
    ) -> pd.DataFrame:
    """Given a dataframe of storm details, retrieve corresponding USGS streamflow.
    
    Parameters
    ----------
    storms: pandas.DataFrame
        Dataframe of storm information. Must contain rows with columns for ['provider_id',
        'start', 'end'].
    api_key : str
        USGS API key.
    batch_size : int
        Number of URLs to retrieve before sleeping.
    sleep_time : float
        Amount of time to sleep between batches.
    
    Returns
    -------
    pandas.DataFrame
        Retrieved streamflow.
    """
    # Extract subset of columns from storms
    LOGGER.info("Subsetting storm dataframe")
    subset = storms[["provider_id", "start", "end"]]

    # Build queries
    LOGGER.info("Building queries")
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

    # Build URLs
    LOGGER.info("Building URLs")
    urls = build_request_batch_from_queries(queries=queries)

    # Batch URLs
    LOGGER.info("Batching URLs")
    number_of_batches = (len(urls) // batch_size) + 1
    batches = np.array_split(urls, number_of_batches)

    # Retrieve batches
    LOGGER.info("Retrieving batches")
    dfs: list[pd.DataFrame] = []
    for batch in batches:
        LOGGER.info("Retrieving batch")
        # Get deserialized JSON
        data = get_all(
            urls=batch,
            max_retries=1
        )

        # Convert to dataframes
        LOGGER.info("Processing batch")
        try:
            dfs.append(to_optimized_dataframe(data))
        except NoDataError:
            LOGGER.warning("Empty batch")

        # Sleep
        LOGGER.info("Sleeping for %f s", sleep_time)
        sleep(sleep_time)

    # Check for data
    if len(dfs) == 0:
        raise NoDataError("No batches returned data.")

    LOGGER.info("Merging batches")
    return pd.concat(dfs, ignore_index=True)
