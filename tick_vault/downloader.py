import asyncio
from datetime import datetime

from tqdm.asyncio import tqdm

from .download_worker import download_worker
from .metadata import MetadataDB
from .metadata_worker import metadata_worker
from .models import TickChunk


async def download_range(
    symbol: str,
    start: datetime,
    end: datetime,
    proxies: list[str] | None = None,
    worker_per_proxy: int = 10,
) -> None:
    """
    Download tick data for a symbol within a date range using concurrent workers.

    This orchestrator manages the entire download pipeline: finding chunks to
    download, distributing work across multiple workers (optionally with different
    proxies), tracking progress, and handling errors gracefully.

    Args:
        symbol: The trading pair symbol (e.g., 'XAUUSD', 'EURUSD')
        start: Start datetime of the range (inclusive, rounded down to hour)
        end: End datetime of the range (exclusive, rounded down to hour)
        proxies: Optional list of proxy URLs. If None or empty, workers run
            without proxies. Workers are distributed evenly across proxies.
        worker_per_proxy: Number of concurrent workers per proxy (default: 10)

    Raises:
        ForbiddenError: If access is blocked/forbidden during download
        RuntimeError: If max retries exceeded or unexpected errors occur
        ValueError: If database operations fail

    Example:
        >>> await download_range(
        ...     symbol='XAUUSD',
        ...     start=datetime(2024, 1, 1),
        ...     end=datetime(2024, 2, 1),
        ...     proxies=['http://proxy1:8080', 'http://proxy2:8080'],
        ...     worker_per_proxy=5
        ... )
    """
    # Handle empty proxies list
    if proxies is None or len(proxies) == 0:
        worker_proxies = [None]
    else:
        worker_proxies = proxies

    # Initialize database and find chunks to download
    with MetadataDB() as db:
        chunks_to_download = db.find_not_attempted_chunks(symbol, start, end)

    # If nothing to download, exit early
    if not chunks_to_download:
        print(f"✓ All data for {symbol} from {start.date()} to {end.date()} already downloaded")
        return

    total_chunks = len(chunks_to_download)
    print(f"Found {total_chunks} chunks to download for {symbol}")

    # Create queues
    chunk_queue: asyncio.Queue[TickChunk | None] = asyncio.Queue()
    downloader_result_queue: asyncio.Queue[tuple[TickChunk, bool]] = asyncio.Queue()
    metadata_queue: asyncio.Queue[tuple[TickChunk, bool] | None] = asyncio.Queue()

    # Calculate total number of workers (capped by available chunks)
    max_workers = len(worker_proxies) * worker_per_proxy
    actual_workers = min(max_workers, total_chunks)

    # Start metadata worker
    metadata_task = asyncio.create_task(metadata_worker(metadata_queue))

    # Start download workers (distributed across proxies)
    download_tasks = []
    worker_index = 0
    
    for proxy in worker_proxies:
        for _ in range(worker_per_proxy):
            if worker_index >= actual_workers:
                break
            
            # Create worker task
            task = asyncio.create_task(
                download_worker(proxy, chunk_queue, downloader_result_queue)
            )
            download_tasks.append(task)
            worker_index += 1
        
        if worker_index >= actual_workers:
            break

    # Populate initial chunks (one per worker to start)
    chunks_remaining = list(chunks_to_download)  # Make a copy
    for _ in range(actual_workers):
        if chunks_remaining:
            await chunk_queue.put(chunks_remaining.pop(0))

    # Create progress bar
    pbar = tqdm(
        total=total_chunks,
        desc=f"Downloading {symbol}",
        unit="chunk",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        colour="green",
    )

    completed = 0
    error_occurred = False

    try:
        # Process results as they come in
        while completed < total_chunks:
            # Get result from download workers
            chunk, has_data = await downloader_result_queue.get()
            
            # Forward to metadata worker
            await metadata_queue.put((chunk, has_data))
            
            # Update progress
            completed += 1
            pbar.update(1)
            
            # Feed next chunk to workers if available
            if chunks_remaining:
                await chunk_queue.put(chunks_remaining.pop(0))
            else:
                await chunk_queue.put(None)

        pbar.close()
        print(f"✓ Successfully downloaded {total_chunks} chunks for {symbol}")

    except Exception as e:
        error_occurred = True
        pbar.close()
        print(f"\n✗ Error during download: {e}")
        raise

    finally:
        # Send stop signals to all workers
        for _ in range(actual_workers):
            await chunk_queue.put(None)
        
        # Stop metadata worker
        await metadata_queue.put(None)

        # Wait for all workers to finish
        try:
            if error_occurred:
                # Cancel tasks if error occurred
                for task in download_tasks:
                    task.cancel()
                metadata_task.cancel()
                
                await asyncio.gather(*download_tasks, metadata_task, return_exceptions=True)
            else:
                # Normal shutdown
                await asyncio.gather(*download_tasks, metadata_task)
        except asyncio.CancelledError:
            pass