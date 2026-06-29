"""Main entry to data pipeline."""
from pathlib import Path
import logging

import pandas as pd

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
    basin_tracks = merge_storm_basins(
        basins=data[DataType.NWM_BASINS],
        storms=data[DataType.IBTRACS],
        filepath=configuration.data_directory / configuration.processed_data.nwm_basin_storms.path,
        location_column="provider_id"
    )

    # Accumulate storm-basin periods
    # TODO Fix erroneous distance. Projection is in meters. Change 400 to 400_000.
    basin_storms = basin_tracks.groupby(["provider_id", "storm"]).agg(
        Name=pd.NamedAgg(column="name", aggfunc="first"),
        Start=pd.NamedAgg(column="time", aggfunc="min"),
        End=pd.NamedAgg(column="time", aggfunc="max")
    )
    print(basin_storms)

if __name__ == "__main__":
    main()
