"""Download worker module for fetching tick data chunks."""

import asyncio

from httpx import AsyncClient

from .fetcher import fetch_with_retry
from .models import TickChunk


async def download_worker(
    proxy: str | None,
    chunk_queue: asyncio.Queue[TickChunk | None],
    result_queue: asyncio.Queue[tuple[TickChunk, bool]],
) -> None:
    """
    Worker coroutine that downloads tick data chunks from a queue.

    This worker processes chunks from chunk_queue, fetches their data,
    saves successful downloads to disk, and reports results to result_queue
    for metadata tracking. The worker runs until it receives None as a
    sentinel value.

    Any errors from fetch_with_retry (ForbiddenError, RuntimeError) are
    raised immediately to stop all workers and alert the parent process.

    Args:
        proxy: Optional proxy URL for the HTTP client (e.g., 'http://proxy:8080')
        chunk_queue: Queue of TickChunk objects to download. None signals shutdown.
        result_queue: Queue for reporting results as (chunk, has_data) tuples

    Raises:
        ForbiddenError: If access is blocked/forbidden (propagated from fetch_with_retry)
        RuntimeError: If max retries exceeded or unexpected errors occur
            (propagated from fetch_with_retry)
        FileExistsError: If attempting to save a chunk that already exists on disk

    Workflow:
        1. Fetch chunk from chunk_queue
        2. If chunk is None, break and exit
        3. Fetch data using fetch_with_retry (which handles retries internally)
        4. If data exists (not None):
           - Save to disk using chunk.save()
           - Put (chunk, True) to result_queue
        5. If data doesn't exist (None/404):
           - Put (chunk, False) to result_queue
        6. Any errors are raised immediately to stop the download process
    """
    async with AsyncClient(proxy=proxy) as client:
        while True:
            chunk = await chunk_queue.get()

            # None is the sentinel value to stop the worker
            if chunk is None:
                break

            # Fetch data with automatic retry logic
            # Any ForbiddenError or RuntimeError will be raised immediately
            content = await fetch_with_retry(client, chunk.url)

            if content is not None:
                # Data exists - save to disk
                chunk.save(content)
                await result_queue.put((chunk, True))
            else:
                # No data exists (404 response)
                await result_queue.put((chunk, False))