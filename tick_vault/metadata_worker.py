"""Metadata worker module for tracking download results."""

import asyncio

from .metadata import MetadataDB
from .chunk import TickChunk


async def metadata_worker(
    result_queue: asyncio.Queue[tuple[TickChunk, bool] | None],
    db_path: str | None = None,
) -> None:
    """
    Worker coroutine that processes download results and updates metadata.

    This worker consumes results from result_queue and updates the metadata
    database with download status. It runs until it receives None as a
    sentinel value. The worker maintains a single database connection for
    efficient batch processing.

    Args:
        result_queue: Queue of (chunk, has_data) tuples or None for shutdown
        db_path: Optional path to the metadata database. If None, uses
            CONFIG.metadata_db_path

    Raises:
        ValueError: If database path validation fails
        sqlite3.Error: If database operations fail

    Workflow:
        1. Initialize database connection
        2. Fetch result from result_queue
        3. If result is None, break and exit
        4. Insert metadata row with (chunk, has_data) status
        5. Repeat until shutdown signal received
        6. Close database connection on exit
    """
    with MetadataDB(db_path) as db:
        while True:
            result = await result_queue.get()

            # None is the sentinel value to stop the worker
            if result is None:
                break

            # Insert or update metadata for this chunk
            db.insert_row(*result)