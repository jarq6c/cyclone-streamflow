"""Methods for retrieving required data and documenting citations."""
import logging
from datetime import datetime, UTC
from pathlib import Path

import requests

from .configuration import DataSource

LOGGER: logging.Logger = logging.getLogger(__name__)
"""Module-level logger."""

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
