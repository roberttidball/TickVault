"""Download worker module for fetching tick data chunks."""

import asyncio

from httpx import AsyncClient

from .chunk import TickChunk
from .config import CONFIG
from .fetcher import fetch_with_retry


async def download_worker(
    proxy: str | None,
    input_queue: asyncio.Queue[TickChunk | None],
    output_queue: asyncio.Queue[TickChunk],
) -> None:
    """
    Worker coroutine that downloads tick data chunks from a queue.

    This worker processes chunks from input_queue, fetches their data,
    saves successful downloads to disk, and reports results to output_queue
    for metadata tracking. The worker runs until it receives None as a
    sentinel value or times out waiting for work.

    Any errors from fetch_with_retry (ForbiddenError, RuntimeError) are
    raised immediately to stop all workers and alert the parent process.

    Args:
        proxy: Optional proxy URL for the HTTP client (e.g., 'http://proxy:8080')
        input_queue: Queue of TickChunk objects to download. None signals shutdown.
        output_queue: Queue for reporting results

    Raises:
        ForbiddenError: If access is blocked/forbidden (propagated from fetch_with_retry)
        RuntimeError: If max retries exceeded or unexpected errors occur
            (propagated from fetch_with_retry)
        FileExistsError: If attempting to save a chunk that already exists on disk

    Workflow:
        1. Fetch chunk from input_queue (with timeout)
        2. If timeout occurs, exit gracefully (assumes parent crashed)
        3. If chunk is None, break and exit
        4. Fetch data using fetch_with_retry (which handles retries internally)
        5. If data exists (not None), save to disk using chunk.save()
        6. Put chunk to output_queue
        7. Any errors are raised immediately to stop the download process
    """
    async with AsyncClient(proxy=proxy) as client:
        while True:
            try:
                # Wait for chunk with timeout
                chunk = await asyncio.wait_for(
                    input_queue.get(), timeout=CONFIG.worker_queue_timeout
                )
            except asyncio.TimeoutError:
                # Timeout - assume parent process crashed or no more work
                break

            # None is the sentinel value to stop the worker
            if chunk is None:
                break

            # Fetch data with automatic retry logic
            # Any ForbiddenError or RuntimeError will be raised immediately
            content = await fetch_with_retry(client, chunk.url)

            if content is not None:
                # Data exists - save to disk
                chunk.save(content)

            await output_queue.put(chunk)
