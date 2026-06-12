"""Main entry to data pipeline."""
from pathlib import Path
import logging
from itertools import count

import pandas as pd

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

    # Match basins to storm tracks
    number_of_gages = len(data[DataType.GAGES_II]["GAGE_ID"])
    counter = count(1)
    dfs = []
    for index, gage_id, boundary in data[DataType.GAGES_II][["GAGE_ID", "geometry"]].itertuples():
        # Report
        logging.info("%s - %d / %d", gage_id, next(counter), number_of_gages)

        # Clip storm tracks to basin boundary
        subset = data[DataType.IBTRACS].clip(boundary.buffer(400.0))

        # Check for storms
        if subset.empty:
            logging.info("No storms found")
            continue

        # Save storms
        subset["GAGE_ID"] = gage_id
        dfs.append(subset)

    # Merge
    result = pd.concat(dfs, ignore_index=True).sort_values(["GAGE_ID", "time"])
    result.to_csv("test_result.csv")

if __name__ == "__main__":
    main()
