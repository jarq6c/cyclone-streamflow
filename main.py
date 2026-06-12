"""Main entry to data pipeline."""
from pathlib import Path
import logging
from src.cyclone_streamflow.configuration import load_configuration, DataType
from src.cyclone_streamflow.pipelines import download_all_data, process_all_data

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
    configuration = load_configuration(configuration_filepath)
    sources = download_all_data(configuration)
    data = process_all_data(sources, directory=configuration.data_directory)
    for k, v in data.items():
        print(k, v.head(1))

if __name__ == "__main__":
    main()
