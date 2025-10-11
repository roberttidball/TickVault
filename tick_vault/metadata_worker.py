"""Metadata worker module for tracking download results."""

import asyncio

from .chunk import TickChunk
from .config import CONFIG
from .metadata import MetadataDB


async def metadata_worker(
    result_queue: asyncio.Queue[TickChunk | None], db_path: str | None = None
) -> None:
    """
    Worker coroutine that processes download results and updates metadata.

    This worker consumes results from result_queue and updates the metadata
    database with download status. It runs until it receives None as a
    sentinel value or times out waiting for results. The worker maintains
    a single database connection for efficient batch processing.

    Args:
        result_queue: Queue of chunk or None for shutdown
        db_path: Optional path to the metadata database. If None, uses
            CONFIG.metadata_db_path

    Raises:
        ValueError: If database path validation fails
        sqlite3.Error: If database operations fail

    Workflow:
        1. Initialize database connection
        2. Wait for result from result_queue (with timeout)
        3. If timeout occurs, exit gracefully (assumes parent crashed)
        4. If result is None, break and exit
        5. Insert metadata row with chunk
        6. Repeat until shutdown signal received
        7. Close database connection on exit
    """
    with MetadataDB(db_path) as db:
        while True:
            try:
                # Wait for chunk with timeout
                chunk = await asyncio.wait_for(
                    result_queue.get(), timeout=CONFIG.worker_queue_timeout
                )
            except asyncio.TimeoutError:
                # Timeout - assume parent process crashed or no more work
                break

            # None is the sentinel value to stop the worker
            if chunk is None:
                break

            # Insert or update metadata for this chunk
            db.insert_row(chunk)
