"""Reader module for loading and decoding tick data into pandas DataFrames."""

from datetime import datetime

import pandas as pd
from tqdm import tqdm

from .decoder import decode_chunk
from .logger import logger
from .metadata import MetadataDB


def read_tick_data(
    symbol: str,
    start: datetime,
    end: datetime,
    pipet_scale: float | None = None,
) -> pd.DataFrame:
    """
    Read and decode tick data for a symbol within a time range.

    This function:
    1. Verifies data continuity by checking for gaps in the metadata database
    2. Retrieves all available chunks within the specified time range
    3. Decodes each chunk from compressed binary format
    4. Combines all decoded ticks into a single pandas DataFrame

    The returned DataFrame is sorted by time and contains one row per tick with
    ask/bid prices and volumes.

    Args:
        symbol: The trading pair symbol (e.g., 'XAUUSD', 'EURUSD', 'BTCUSD')
        start: Start datetime of the range (inclusive, rounded down to hour)
        end: End datetime of the range (exclusive, rounded down to hour)
        pipet_scale: Optional price scaling factor. If None, uses the value from
            PIPET_SIZE_REGISTRY for the symbol. This scales the raw integer prices
            to actual floating-point prices.

    Returns:
        pd.DataFrame: DataFrame with columns:
            - time (datetime): Tick timestamp
            - ask (float): Ask price
            - bid (float): Bid price
            - ask_volume (int): Ask volume
            - bid_volume (int): Bid volume
            Sorted by time in ascending order. Returns empty DataFrame if no data
            is available in the range.

    Raises:
        ValueError: If no data exists for the symbol in the database
        RuntimeError: If gaps are detected in the data (missing hours between
            first and last downloaded chunks)
        FileNotFoundError: If a chunk file is missing from disk despite being
            marked as available in the metadata database

    Example:
        >>> from datetime import datetime
        >>> df = read_tick_data(
        ...     symbol='XAUUSD',
        ...     start=datetime(2024, 3, 1, 0),
        ...     end=datetime(2024, 3, 2, 0)
        ... )
        >>> df.head()
                            time      ask      bid  ask_volume  bid_volume
        0 2024-03-01 00:00:01.234  2045.50  2045.45     1500000     2000000
        1 2024-03-01 00:00:01.567  2045.51  2045.46     1200000     1800000
        ...

        >>> # Custom pipet scale for non-standard symbols
        >>> df = read_tick_data(
        ...     symbol='CUSTOM',
        ...     start=datetime(2024, 3, 1),
        ...     end=datetime(2024, 3, 2),
        ...     pipet_scale=0.01
        ... )
    """
    logger.info(f"Reading tick data for {symbol} from {start.date()} to {end.date()}")

    # Initialize database and verify data integrity
    with MetadataDB() as db:
        # Check for gaps in the data - raises RuntimeError if gaps exist
        logger.debug(f"Checking for data gaps in {symbol}")
        db.check_for_gaps(symbol)

        # Get all available chunks in the time range
        logger.debug(f"Retrieving available chunks for {symbol}")
        chunks = db.get_available_chunks(symbol, start, end)

    # Handle empty result
    if not chunks:
        logger.warning(
            f"No data available for {symbol} in range {start.date()} to {end.date()}"
        )
        return pd.DataFrame(
            columns=["time", "ask", "bid", "ask_volume", "bid_volume"]
        )

    logger.info(f"Decoding {len(chunks)} chunks for {symbol}")

    # Decode all chunks and collect rows with progress bar
    all_rows = []
    
    with tqdm(
        total=len(chunks),
        desc=f"Reading {symbol}",
        unit="chunk",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        colour="green",
    ) as pbar:
        for chunk in chunks:
            try:
                rows = decode_chunk(chunk, pipet_scale=pipet_scale)
                all_rows.extend(rows)
                pbar.update(1)
            except FileNotFoundError:
                pbar.close()
                logger.error(
                    f"Chunk file missing for {chunk.symbol} at {chunk.time.isoformat()}"
                )
                raise
            except Exception as e:
                pbar.close()
                logger.error(
                    f"Failed to decode chunk {chunk.symbol} at {chunk.time.isoformat()}: {e}"
                )
                raise

    # Convert to DataFrame
    df = pd.DataFrame(
        all_rows,
        columns=["time", "ask", "bid", "ask_volume", "bid_volume"]
    )

    # Ensure time column is datetime type
    df["time"] = pd.to_datetime(df["time"])
    df["ask"] = df["ask"].astype("float64")
    df["bid"] = df["bid"].astype("float64")
    df["ask_volume"] = df["ask_volume"].astype("int64")
    df["bid_volume"] = df["bid_volume"].astype("int64")

    logger.info(
        f"Successfully loaded {len(df)} ticks for {symbol} "
        f"from {df['time'].min()} to {df['time'].max()}"
    )

    return df