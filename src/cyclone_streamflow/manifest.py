"""Methods to track storm-associated streamflow downloads."""
import logging
from enum import StrEnum
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np

LOGGER: logging.Logger = logging.getLogger(__name__)
"""Module-level logger."""

class DownloadStatus(StrEnum):
    """Valid download statuses."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    NODATA = "NODATA"

class SQLiteManifestManager:
    """Orchestrates SQL database operations for pipeline checkpoints.
    
    Attributes
    ----------
    db_path : pathlib.Path
        Filesystem path to SQLite database file.
    """
    _partition_manifest_table: str = "partition_manifest"
    _default_status: DownloadStatus = DownloadStatus.PENDING
    _prefix_field: str = "prefix"
    _year_field: str = "year"
    _status_field: str = "status"

    def __init__(self, db_path: Path) -> None:
        LOGGER.info("Using database at %s", db_path)
        self.db_path = db_path
        self._create_schema()

    def _create_schema(self) -> None:
        """Executes the DDL statements to set up the tracking manifest table."""
        create_table_sql = f"""
CREATE TABLE IF NOT EXISTS {self._partition_manifest_table} (
    {self._prefix_field} TEXT NOT NULL,
    {self._year_field} INTEGER NOT NULL,
    {self._status_field} TEXT NOT NULL DEFAULT '{self._default_status}',
    PRIMARY KEY ({self._prefix_field}, {self._year_field})
);
"""
        LOGGER.info("Initializing table %s", self._partition_manifest_table)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(create_table_sql)
            conn.commit()

    def initialize_partitions(self, records: np.recarray[Any, np.dtype[np.record]]) -> None:
        """Populate the manifest table with distinct partitions set to the default
        status (e.g. 'PENDING').
        
        Parameters
        ----------
        records : numpy.recarray
            Record array of individual partition indices as a tuples of (str, int). For
            example, [('01', 2001), ('02', 1999)].
        """
        insert_sql = f"""
INSERT OR IGNORE INTO {self._partition_manifest_table} ({self._prefix_field}, {self._year_field}, {self._status_field})
VALUES (?, ?, '{self._default_status}');
"""
        LOGGER.info("Populating %s", self._partition_manifest_table)
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(insert_sql, records.tolist())
            conn.commit()

    def get_partitions(self, status: DownloadStatus) -> list[tuple[str, int]]:
        """Retrieves all partitions with the indicated status.
        
        Parameters
        ----------
        status : DownloadStatus
            A valid status enum.
            
        Returns
        -------
        A list of tuples matching (prefix, year) for targeted status.
        """
        select_sql = f"""
SELECT {self._prefix_field}, {self._year_field}
FROM {self._partition_manifest_table}
WHERE {self._status_field} = '{status}';
"""
        LOGGER.info("Gathering %s partitions", status)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(select_sql)
            rows = cursor.fetchall()
        return [(str(row[0]), int(row[1])) for row in rows]

    def update_status(self, prefix: str, year: int, status: DownloadStatus) -> None:
        """Updates the tracking status of a distinct partition.
        
        Parameters
        ----------
        prefix : str
            The partition prefix identifier string.
        year : int
            The partition calendar year integer.
        status : DownloadStatus
            The valid status state to write.
        """
        update_sql = f"""
UPDATE {self._partition_manifest_table}
SET {self._status_field} = ?
WHERE {self._prefix_field} = ? AND {self._year_field} = ?;
"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(update_sql, (status, prefix, year))
            conn.commit()
            LOGGER.info("Partition %s, %d updated to %s", prefix, year, status)
