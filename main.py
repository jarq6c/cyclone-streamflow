"""Main entry to data pipeline."""
from pathlib import Path
import logging

import pandas as pd
import polars as pl

from hydrotools.waterdata_client.transformers import NoDataError

from src.cyclone_streamflow.configuration import load_configuration, DataType, IBTrACSColumn, NWMBasinColumn
from src.cyclone_streamflow.pipelines import download_all_data, process_all_data, merge_storm_basins
from src.cyclone_streamflow.data_retrieval import download_storm_streamflow
from src.cyclone_streamflow.manifest import SQLiteManifestManager, DownloadStatus

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

    # Load API key
    if configuration.api_key_file.exists():
        api_key = configuration.api_key_file.read_text()
    else:
        api_key = None

    # Match basins to storm tracks
    basin_tracks = merge_storm_basins(
        basins=data[DataType.NWM_BASINS],
        storms=data[DataType.IBTRACS],
        filepath=configuration.data_directory / configuration.processed_data.nwm_basin_storms.path,
        location_column=NWMBasinColumn.PROVIDER_ID
    )

    # Accumulate storm-basin periods
    basin_storms = basin_tracks.groupby([NWMBasinColumn.PROVIDER_ID, IBTrACSColumn.STORM_ID]).agg(
        name=pd.NamedAgg(column=IBTrACSColumn.STORM_NAME, aggfunc="first"),
        start=pd.NamedAgg(column=IBTrACSColumn.TIME, aggfunc="min"),
        end=pd.NamedAgg(column=IBTrACSColumn.TIME, aggfunc="max")
    ).reset_index()

    # Add prefix and year for partitioning
    basin_storms["prefix"] = basin_storms["provider_id"].str[:2]
    basin_storms["year"] = basin_storms["start"].dt.year

    # Setup manifest
    manifest_file: Path = configuration.data_directory / configuration.processed_data.streamflow_manifest.path
    manager = SQLiteManifestManager(manifest_file)
    manager.initialize_partitions(
        records=basin_storms[["prefix", "year"]].drop_duplicates().to_records(index=False)
    )
    streamflow_directory: Path = (
        configuration.data_directory /
        configuration.processed_data.streamflow.path
    )

    # Download
    partitions = (
        manager.get_partitions(DownloadStatus.PENDING) +
        manager.get_partitions(DownloadStatus.PROCESSING)
    )
    for prefix, year in partitions:
        # Check for partition
        data_check = pl.scan_parquet(
            streamflow_directory
        ).filter(
            pl.col("prefix") == prefix,
            pl.col("year") == year
        ).select("value").head().collect().count().item()

        if data_check == 5:
            logging.warning("Skipping existing partition %s/%d", prefix, year)
            manager.update_status(prefix, year, DownloadStatus.DONE)
            continue

        # Extract storm events
        storms = basin_storms[(basin_storms["prefix"] == prefix) & (basin_storms["year"] == year)]

        # Download
        try:
            manager.update_status(prefix, year, DownloadStatus.PROCESSING)
            df = download_storm_streamflow(
                storms=storms,
                api_key=api_key
            )
        except NoDataError:
            logging.warning("No data available for partition, skipping")
            manager.update_status(prefix, year, DownloadStatus.NODATA)
            continue

        # Add partition columns
        df["prefix"] = prefix
        df["year"] = year

        # Save
        logging.info("Saving %s", streamflow_directory)
        pl_df = pl.from_pandas(df[[
            "usgs_site_code",
            "value_time",
            "value",
            "prefix",
            "year"
        ]]).with_columns(
            pl.col("year").cast(pl.Int32)
        )
        pl_df.write_parquet(streamflow_directory, partition_by=["prefix", "year"])
        manager.update_status(prefix, year, DownloadStatus.DONE)

    # Save storms frame to parquet
    ofile: Path = (
        configuration.data_directory /
        configuration.processed_data.basin_storms.path
    )
    logging.info("Checking %s", ofile)
    if not ofile.exists():
        basin_storms["usgs_site_code"] = "USGS-" + basin_storms["provider_id"]
        pl.from_pandas(basin_storms).write_parquet(ofile)

    # Map peak streamflow to cyclones
    logging.info("Mapping streamflow to cyclones")
    storms = pl.scan_parquet(ofile).select(
        ["storm", "name", "start", "end", "usgs_site_code", "prefix", "year"]
    )
    streamflow = pl.scan_parquet(
        streamflow_directory,
        hive_partitioning=True
    ).select(
        ["usgs_site_code", "value_time", "value", "prefix", "year"]
    )
    peaks = storms.join(
        streamflow,
        on=["usgs_site_code", "prefix", "year"],
        how="inner"
    ).filter(
        (pl.col("value_time") >= pl.col("start"))
        & (pl.col("value_time") <= pl.col("end"))
    ).group_by(
        ["usgs_site_code", "storm"]
    ).agg(
        peak_streamflow_cfs=pl.col("value").max()
    )

    # Let-join back to preserve metadata
    logging.info("Saving final dataset")
    final_dataset = storms.select(
        ["usgs_site_code", "storm", "name", "start", "end"]
    ).unique().join(
        peaks,
        on=["usgs_site_code", "storm"],
        how="left"
    )

    # Save final dataset
    final_output_path: Path = (
        configuration.data_directory / "cyclone_peak_streamflow.parquet"
    )
    final_dataset.sink_parquet(final_output_path)
    logging.info("Saved dataset to: %s", final_output_path)

if __name__ == "__main__":
    main()
