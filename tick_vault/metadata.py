"""Metadata database module for managing tick data download status."""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .chunk import TickChunk
from .config import CONFIG
from .logger import logger
from .utils import generate_hourly_datetimes


class MetadataDB:
    """
    SQLite-based metadata storage for tracking tick data download status.

    Each symbol gets its own table with hourly entries as rows. The timestamp
    serves as the primary key, allowing efficient queries and automatic sorting.
    This design supports non-sequential inserts and gap detection.

    The database is designed for single-threaded access only. For concurrent
    downloads, use a queue-based architecture with a dedicated metadata worker.

    Attributes:
        db_path: Path to the SQLite database file
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """
        Initialize the metadata database.

        Args:
            db_path: Path to the SQLite database file. If None, uses
                CONFIG.metadata_db_path. Parent directories are created
                if they don't exist.

        Raises:
            ValueError: If db_path points to an existing directory instead of a file
        """
        self.db_path = Path(db_path) if db_path else CONFIG.metadata_db_path
        if self.db_path.is_dir():
            raise ValueError(
                f"Expected a database path but got a directory: {self.db_path}"
            )

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        logger.debug(f"Initialized metadata database at {self.db_path}")

    def _get_table_name(self, symbol: str) -> str:
        """
        Generate a valid SQL table name from a symbol.

        Args:
            symbol: The trading pair symbol

        Returns:
            str: A valid SQL table name (prefixed with 'symbol_')
        """
        # Prefix with 'symbol_' to ensure valid table name
        # Replace any non-alphanumeric characters with underscores
        clean_symbol = "".join(c if c.isalnum() else "_" for c in symbol)
        return f"symbol_{clean_symbol}"

    def _ensure_table_exists(self, symbol: str) -> None:
        """
        Create a table for the symbol if it doesn't exist.

        Args:
            symbol: The trading pair symbol
        """
        logger.debug(f"Ensuring table exists for symbol: {symbol}")
        table_name = self._get_table_name(symbol)
        self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                timestamp INTEGER PRIMARY KEY,
                has_data INTEGER NOT NULL CHECK(has_data IN (0, 1))
            )
            """
        )
        self.conn.commit()

    def insert_rows(self, chunks: list[TickChunk]) -> None:
        """
        Insert or update multiple metadata rows in a single transaction.

        Chunks are grouped by symbol, and each symbol's data is inserted in one
        transaction. If an entry already exists for a timestamp, it will be replaced.

        Args:
            chunks: List of TickChunk objects to insert

        Example:
            >>> db = MetadataDB()
            >>> chunks = [
            ...     TickChunk(symbol='XAUUSD', time=datetime(2024, 1, 1, i, 0, 0))
            ...     for i in range(24)
            ... ]
            >>> db.insert_rows_batch(chunks)
        """
        if not chunks:
            return

        # Group chunks by symbol
        chunks_by_symbol: dict[str, list[TickChunk]] = {}
        for chunk in chunks:
            if chunk.symbol not in chunks_by_symbol:
                chunks_by_symbol[chunk.symbol] = []
            chunks_by_symbol[chunk.symbol].append(chunk)

        logger.debug(
            f"Inserting {len(chunks)} rows across {len(chunks_by_symbol)} symbols"
        )

        # Insert all chunks for each symbol in a single transaction
        for symbol, symbol_chunks in chunks_by_symbol.items():
            self._ensure_table_exists(symbol)
            table_name = self._get_table_name(symbol)

            # Prepare data tuples (timestamp, has_data)
            data = [
                (int(chunk.time.timestamp()), int(chunk.path().exists()))
                for chunk in symbol_chunks
            ]

            # Bulk insert with single commit
            self.conn.executemany(
                f"INSERT OR REPLACE INTO {table_name} (timestamp, has_data) VALUES (?, ?)",
                data,
            )
            self.conn.commit()

    def find_not_attempted_chunks(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[TickChunk]:
        """
        Find all hourly chunks that have not been attempted for download.

        Generates all hourly datetimes in the range and filters out those
        that already exist in the database. Useful for resuming interrupted
        downloads or updating to include recent data.

        Args:
            symbol: The trading pair symbol
            start: Start datetime of the range (inclusive, rounded down to hour)
            end: End datetime of the range (exclusive, rounded down to hour)

        Returns:
            list[TickChunk]: Chunks for hours that have not been attempted

        Example:
            >>> db = MetadataDB()
            >>> start = datetime(2024, 3, 1, 0)
            >>> end = datetime(2024, 3, 2, 0)
            >>> chunks = db.find_not_attempted_chunks('XAUUSD', start, end)
        """
        self._ensure_table_exists(symbol)
        table_name = self._get_table_name(symbol)

        # Generate all hourly datetimes in range
        all_hours = generate_hourly_datetimes(start, end)

        # Get existing timestamps from database
        timestamps = [int(dt.timestamp()) for dt in all_hours]
        placeholders = ",".join("?" * len(timestamps))

        cursor = self.conn.execute(
            f"""
            SELECT timestamp FROM {table_name}
            WHERE timestamp IN ({placeholders})
            """,
            timestamps,
        )

        existing_timestamps = {row[0] for row in cursor.fetchall()}

        # Create chunks for hours not in database
        not_attempted = [
            TickChunk(symbol=symbol, time=dt)
            for dt in all_hours
            if int(dt.timestamp()) not in existing_timestamps
        ]

        logger.debug(
            f"Found {len(not_attempted)} not-attempted chunks for {symbol} from {start.date()} to {end.date()}"
        )

        return not_attempted

    def check_for_gaps(self, symbol: str) -> None:
        """
        Verify data continuity by checking for gaps in downloaded data.

        Finds the first and last entries for the symbol and ensures all hours
        between them exist in the database. Raises an error if any gaps are found.

        This should be called before reading data to ensure consistency.

        Args:
            symbol: The trading pair symbol

        Raises:
            RuntimeError: If gaps are found in the data
            ValueError: If no data exists for the symbol

        Example:
            >>> db = MetadataDB()
            >>> db.check_for_gaps('XAUUSD')  # Raises if gaps exist
        """
        self._ensure_table_exists(symbol)
        table_name = self._get_table_name(symbol)

        # Get first and last timestamps
        cursor = self.conn.execute(
            f"""
            SELECT MIN(timestamp), MAX(timestamp), COUNT(*)
            FROM {table_name}
            """
        )

        result = cursor.fetchone()
        if result[0] is None:
            logger.warning(f"No data found for symbol: {symbol}")
            raise ValueError(f"No data found for symbol: {symbol}")

        min_timestamp, max_timestamp, count = result

        # Calculate expected number of hours
        first_dt = datetime.fromtimestamp(min_timestamp, tz=timezone.utc)
        last_dt = datetime.fromtimestamp(max_timestamp, tz=timezone.utc)

        # Generate all expected hours
        expected_hours = generate_hourly_datetimes(
            first_dt, last_dt + timedelta(hours=1)
        )
        expected_count = len(expected_hours)

        if count != expected_count:
            # Find the actual gaps
            expected_timestamps = {int(dt.timestamp()) for dt in expected_hours}

            cursor = self.conn.execute(
                f"""
                SELECT timestamp FROM {table_name}
                WHERE timestamp >= ? AND timestamp <= ?
                """,
                (min_timestamp, max_timestamp),
            )

            existing_timestamps = {row[0] for row in cursor.fetchall()}
            missing_timestamps = expected_timestamps - existing_timestamps

            missing_dates = [
                datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
                for ts in sorted(missing_timestamps)
            ]
            logger.error(
                f"Data gaps detected for {symbol}: {len(missing_timestamps)} missing hours"
            )

            raise RuntimeError(
                f"Data gaps found for symbol {symbol}. "
                f"Expected {expected_count} entries but found {count}. "
                f"Missing timestamps: {missing_dates[:10]}"
                + (" ..." if len(missing_dates) > 10 else "")
            )

    def get_available_chunks(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[TickChunk]:
        """
        Get all chunks with available data within a time range.

        Returns only chunks where has_data=True. Typically called after
        check_for_gaps() to ensure data continuity.

        Args:
            symbol: The trading pair symbol
            start: Start datetime of the range (inclusive, rounded down to hour)
            end: End datetime of the range (exclusive, rounded down to hour)

        Returns:
            list[TickChunk]: Chunks with available data, sorted by time

        Example:
            >>> db = MetadataDB()
            >>> db.check_for_gaps('XAUUSD')  # Verify no gaps first
            >>> start = datetime(2024, 3, 1, 0)
            >>> end = datetime(2024, 3, 2, 0)
            >>> chunks = db.get_available_chunks('XAUUSD', start, end)
        """
        self._ensure_table_exists(symbol)
        table_name = self._get_table_name(symbol)

        # Round to hours
        start_hour = start.replace(minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        end_hour = end.replace(minute=0, second=0, microsecond=0, tzinfo=timezone.utc)

        start_timestamp = int(start_hour.timestamp())
        end_timestamp = int(end_hour.timestamp())

        cursor = self.conn.execute(
            f"""
            SELECT timestamp FROM {table_name}
            WHERE timestamp >= ? AND timestamp < ? AND has_data = 1
            ORDER BY timestamp ASC
            """,
            (start_timestamp, end_timestamp),
        )

        available_chunks = [
            TickChunk(symbol=symbol, time=datetime.fromtimestamp(row[0], tz=timezone.utc))
            for row in cursor.fetchall()
        ]

        logger.debug(f"Retrieved {len(available_chunks)} available chunks for {symbol}")

        return available_chunks

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
        logger.debug("Closed metadata database connection")

    def __enter__(self) -> "MetadataDB":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - closes connection."""
        self.close()
