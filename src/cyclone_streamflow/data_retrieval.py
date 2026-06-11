"""Methods for retrieving required data and documenting citations."""
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import TypeAlias, Annotated, Any

import requests
from pydantic import BaseModel, HttpUrl, BeforeValidator

LOGGER: logging.Logger = logging.getLogger(__name__)
"""Module-level logger."""

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
    pathlib.Path object.
    """
    path_object = Path(directory_path)
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
    name : str
        Machine-friendly name.
    url : HttpUrl
        Source url.
    citations : list[str]
        List of preferred citations.
    filename : str
        Desired local file name after download.
    metadata : str
        Desired local file name for Markdown metadata.

    """
    name: str
    url: HttpUrl
    citations: list[str]
    filename: str
    metadata: str

class Configuration(BaseModel):
    """
    Project configuration Pydantic model.
    
    Attributes
    ----------
    data_directory: pathlib.Path
        Path to data/download directory.
    data_sources : list[DataSource]
        List of DataSource objects.

    """
    data_directory: CustomDirectoryPath
    data_sources: list[DataSource]

def download_data_source(source: DataSource, directory: Path = Path(".")) -> None:
    """Downloads a data associated with a DataSource object.
    
    Parameters
    ----------
    source : DataSource
        DataSource object
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

    LOGGER.info("%s exists, skipping download", filepath)

def download_all_data(
        configuration_filepath: Path = Path("configuration.json")
) -> None:
    """
    Reads configuration file and downloads all required data.
    
    Parameters
    ----------
    configuration_filepath : pathlib.Path
        Path to configuration JSON file.

    """
    # Load configuration
    with configuration_filepath.open("r", encoding="utf-8") as fi:
        configuration = Configuration.model_validate_json(fi.read())

    # Download files
    for ds in configuration.data_sources:
        download_data_source(ds, configuration.data_directory)
