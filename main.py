"""Main entry to data pipeline."""
from pathlib import Path
import logging
from src.cyclone_streamflow.data_retrieval import download_all_data, DataType
from src.cyclone_streamflow.data_processing import process_nwps

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

def main(
        configuration_filepath: Path = Path("configuration.json")
) -> None:
    """
    Execute pipeline.
    
    Parameters
    ----------
    configuration_filepath : pathlib.Path
        Path to configuration JSON file.

    """
    # Download data
    sources = download_all_data(configuration_filepath)

    # Process data
    gdf = process_nwps(sources[DataType.NWPS])
    print(gdf.info())

if __name__ == "__main__":
    main()
