"""Main entry to data pipeline."""
from pathlib import Path
import logging

from src.cyclone_streamflow.configuration import load_configuration, DataType
from src.cyclone_streamflow.pipelines import download_all_data, process_all_data, merge_storm_basins

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

    # Match basins to storm tracks
    result = merge_storm_basins(
        basins=data[DataType.GAGES_II],
        storms=data[DataType.IBTRACS],
        filepath=configuration.data_directory / configuration.processed_data.basin_storms.path
    )
    print(result)

if __name__ == "__main__":
    main()
