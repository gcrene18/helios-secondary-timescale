"""
Threading and async utilities for concurrent operations.
"""
import asyncio
import threading
from typing import List, Callable, Any, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
import functools

from ..core.logging import get_logger

logger = get_logger(__name__)

def run_in_thread(func):
    """
    Decorator to run a function in a separate thread.
    
    Args:
        func: Function to run in a thread
        
    Returns:
        Decorated function that runs in a thread
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
        return thread
    
    return wrapper


def run_in_background(func, *args, **kwargs):
    """
    Run a function in a background thread.
    
    Args:
        func: Function to run
        *args: Arguments for the function
        **kwargs: Keyword arguments for the function
        
    Returns:
        The created thread object
    """
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()
    return thread


async def gather_with_concurrency(n: int, *tasks):
    """
    Run coroutines with a limit on concurrency.
    
    Args:
        n: Maximum number of concurrent tasks
        *tasks: Coroutines to execute
        
    Returns:
        List of results from the tasks
    """
    semaphore = asyncio.Semaphore(n)
    
    async def sem_task(task):
        async with semaphore:
            return await task
    
    return await asyncio.gather(*(sem_task(task) for task in tasks))


async def gather_with_progress(coros, description="Processing tasks"):
    """
    Run coroutines and track progress.
    
    Args:
        coros: List of coroutines to execute
        description: Description for the progress bar
        
    Returns:
        List of results from the coroutines
    """
    from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn
    from ..core.logging import console
    
    results = []
    
    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task(description, total=len(coros))
        
        for coro in coros:
            result = await coro
            results.append(result)
            progress.update(task, advance=1)
    
    return results


def map_threaded(func: Callable, items: List[Any], max_workers: int = None) -> List[Any]:
    """
    Apply a function to each item in a list using a thread pool.
    
    Args:
        func: Function to apply to each item
        items: List of items to process
        max_workers: Maximum number of worker threads
        
    Returns:
        List of results from applying the function to each item
    """
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(func, items))
    
    return results


async def execute_with_timeout(coro, timeout_seconds: float) -> Optional[Any]:
    """
    Execute a coroutine with a timeout.
    
    Args:
        coro: Coroutine to execute
        timeout_seconds: Timeout in seconds
        
    Returns:
        Result of the coroutine, or None if it timed out
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(f"Operation timed out after {timeout_seconds} seconds")
        return None


class AsyncBatchProcessor:
    """
    Process items in batches asynchronously.
    
    This class helps process a large number of items in smaller batches
    to avoid overloading resources.
    """
    
    def __init__(
        self, 
        batch_size: int = 10, 
        max_concurrency: int = 5,
        timeout_seconds: float = 60.0
    ):
        """
        Initialize the batch processor.
        
        Args:
            batch_size: Number of items to process in each batch
            max_concurrency: Maximum number of concurrent tasks
            timeout_seconds: Maximum time to wait for each task
        """
        self.batch_size = batch_size
        self.max_concurrency = max_concurrency
        self.timeout_seconds = timeout_seconds
        self.semaphore = asyncio.Semaphore(max_concurrency)
    
    def _chunks(self, items: List[Any]) -> List[List[Any]]:
        """Split items into chunks of batch_size."""
        return [items[i:i + self.batch_size] for i in range(0, len(items), self.batch_size)]
    
    async def _process_item_with_semaphore(self, process_func, item):
        """Process a single item with concurrency control."""
        async with self.semaphore:
            try:
                return await execute_with_timeout(
                    process_func(item),
                    self.timeout_seconds
                )
            except Exception as e:
                logger.error(f"Error processing item {item}", error=str(e))
                return None
    
    async def process_items(
        self, 
        items: List[Any], 
        process_func: Callable[[Any], Any]
    ) -> List[Any]:
        """
        Process items in batches with controlled concurrency.
        
        Args:
            items: List of items to process
            process_func: Async function to apply to each item
            
        Returns:
            List of results
        """
        results = []
        batches = self._chunks(items)
        
        for i, batch in enumerate(batches):
            logger.info(f"Processing batch {i+1}/{len(batches)} with {len(batch)} items")
            
            # Create tasks for this batch
            tasks = [
                self._process_item_with_semaphore(process_func, item)
                for item in batch
            ]
            
            # Process the batch
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
        
        return results
