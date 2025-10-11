"""Decoder module for reading and decoding tick data chunks."""

import lzma
import struct
from datetime import datetime, timedelta
from typing import TypeAlias

from .chunk import TickChunk
from .constants import LZMA_FORMAT_STRING, PIPET_SIZE_REGISTRY, RAW_DATA_TOKEN_SIZE
from .logger import logger

# Type alias for a single tick row
RowType: TypeAlias = tuple[datetime, float, float, int, int]


def decode_chunk(chunk: TickChunk, pipet_scale: float | None = None) -> list[RowType]:
    """
    Decode a single tick data chunk from compressed binary format.

    Decompresses the LZMA-compressed data and unpacks each tick into a tuple
    containing timestamp, ask/bid prices, and volumes. The timestamp is calculated
    by adding the delta milliseconds to the chunk's base hour.

    Args:
        chunk: The TickChunk to decode
        pipet_scale: Optional price scaling factor. If None, uses the value from
            PIPET_SIZE_REGISTRY for the chunk's symbol.

    Returns:
        list[RowType]: List of tuples, each containing:
            - datetime: Tick timestamp (chunk.time + delta milliseconds)
            - float: Ask price (scaled)
            - float: Bid price (scaled)
            - int: Ask volume (scaled and rounded)
            - int: Bid volume (scaled and rounded)

    Raises:
        FileNotFoundError: If the chunk file doesn't exist on disk
        ValueError: If pipet_scale is None and symbol not in PIPET_SIZE_REGISTRY
        lzma.LZMAError: If decompression fails
        struct.error: If binary data format is invalid

    Example:
        >>> chunk = TickChunk(symbol='XAUUSD', time=datetime(2024, 3, 2, 12))
        >>> ticks = decode_chunk(chunk)
        >>> len(ticks) > 0
        True
        >>> isinstance(ticks[0][0], datetime)
        True
    """
    # Load and decompress the chunk data
    compressed_bytes = chunk.load()
    try:
        decompressed_bytes = lzma.decompress(compressed_bytes)
    except lzma.LZMAError as e:
        logger.error(f"Failed to decompress chunk {chunk.symbol} at {chunk.time}: {e}")
        raise

    # Calculate number of ticks in the chunk
    num_ticks = len(decompressed_bytes) // RAW_DATA_TOKEN_SIZE

    if len(decompressed_bytes) % RAW_DATA_TOKEN_SIZE != 0:
        logger.warning(
            f"Chunk {chunk.symbol} at {chunk.time} has incomplete data: "
            f"{len(decompressed_bytes)} bytes not divisible by {RAW_DATA_TOKEN_SIZE}"
        )

    # Get pipet scale for price conversion
    if pipet_scale is None:
        if chunk.symbol not in PIPET_SIZE_REGISTRY:
            raise ValueError(
                f"Pipet scale is not registered for {chunk.symbol} symbol. "
                "Manually pass it or add it to PIPET_SIZE_REGISTRY registry."
            )
        pipet_scale = PIPET_SIZE_REGISTRY[chunk.symbol]

    logger.debug(
        f"Decoding {num_ticks} ticks from chunk {chunk.symbol} at {chunk.time}"
    )

    # Decode each tick
    data: list[RowType] = []
    for i in range(num_ticks):
        # Extract raw bytes for this tick
        row_bytes = decompressed_bytes[
            i * RAW_DATA_TOKEN_SIZE : (i + 1) * RAW_DATA_TOKEN_SIZE
        ]

        # Unpack binary data
        try:
            delta_ms, ask, bid, ask_volume, bid_volume = struct.unpack(
                LZMA_FORMAT_STRING, row_bytes
            )
        except struct.error as e:
            logger.error(
                f"Failed to unpack tick {i} from chunk {chunk.symbol} at {chunk.time}: {e}"
            )
            raise

        # Convert to final format
        tick_time = chunk.time + timedelta(milliseconds=delta_ms)
        scaled_ask = ask * pipet_scale
        scaled_bid = bid * pipet_scale
        scaled_ask_volume = int(round(ask_volume * 1e6))
        scaled_bid_volume = int(round(bid_volume * 1e6))

        data.append(
            (tick_time, scaled_ask, scaled_bid, scaled_ask_volume, scaled_bid_volume)
        )

    return data
