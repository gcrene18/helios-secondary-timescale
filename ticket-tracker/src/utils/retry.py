"""
Retry decorators for handling transient failures.
"""
import functools
import time
from typing import Callable, Type, List, Optional, Any, Union
import random
import asyncio
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from ..core.logging import get_logger

logger = get_logger(__name__)

def with_retry(
    retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], List[Type[Exception]]] = Exception
):
    """
    Decorator for retrying functions on failure with exponential backoff.
    
    Args:
        retries: Maximum number of retries
        delay: Initial delay in seconds
        backoff: Backoff multiplier for each retry
        exceptions: Exception types to catch and retry
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            # If exceptions is a single exception type, convert to list
            exception_types = exceptions if isinstance(exceptions, list) else [exceptions]
            
            for attempt in range(retries + 1):
                try:
                    if attempt > 0:
                        # Calculate delay with exponential backoff and jitter
                        current_delay = delay * (backoff ** (attempt - 1))
                        jitter = random.uniform(0.8, 1.2)
                        sleep_time = current_delay * jitter
                        
                        logger.debug(
                            f"Retry attempt {attempt}/{retries} for {func.__name__}",
                            delay=sleep_time
                        )
                        time.sleep(sleep_time)
                    
                    return func(*args, **kwargs)
                except tuple(exception_types) as e:
                    last_exception = e
                    logger.warning(
                        f"Attempt {attempt + 1}/{retries + 1} failed for {func.__name__}",
                        error=str(e)
                    )
                    
                    # If this was the last attempt, re-raise
                    if attempt == retries:
                        logger.error(
                            f"All {retries + 1} attempts failed for {func.__name__}",
                            error=str(e)
                        )
                        raise
            
            # This should not be reached, but just in case
            if last_exception:
                raise last_exception
            return None
        
        return wrapper
    
    return decorator


async def with_async_retry(
    func: Callable,
    retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], List[Type[Exception]]] = Exception,
    *args,
    **kwargs
):
    """
    Async helper function to retry an async function with exponential backoff.
    
    Args:
        func: Async function to retry
        retries: Maximum number of retries
        delay: Initial delay in seconds
        backoff: Backoff multiplier for each retry
        exceptions: Exception types to catch and retry
        *args: Arguments for the function
        **kwargs: Keyword arguments for the function
        
    Returns:
        Result of the function
    """
    last_exception = None
    
    # If exceptions is a single exception type, convert to list
    exception_types = exceptions if isinstance(exceptions, list) else [exceptions]
    
    for attempt in range(retries + 1):
        try:
            if attempt > 0:
                # Calculate delay with exponential backoff and jitter
                current_delay = delay * (backoff ** (attempt - 1))
                jitter = random.uniform(0.8, 1.2)
                sleep_time = current_delay * jitter
                
                logger.debug(
                    f"Async retry attempt {attempt}/{retries} for {func.__name__}",
                    delay=sleep_time
                )
                await asyncio.sleep(sleep_time)
            
            return await func(*args, **kwargs)
        except tuple(exception_types) as e:
            last_exception = e
            logger.warning(
                f"Async attempt {attempt + 1}/{retries + 1} failed for {func.__name__}",
                error=str(e)
            )
            
            # If this was the last attempt, re-raise
            if attempt == retries:
                logger.error(
                    f"All {retries + 1} async attempts failed for {func.__name__}",
                    error=str(e)
                )
                raise
    
    # This should not be reached, but just in case
    if last_exception:
        raise last_exception
    return None


def async_retry(
    retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], List[Type[Exception]]] = Exception
):
    """
    Decorator for retrying async functions on failure with exponential backoff.
    
    Args:
        retries: Maximum number of retries
        delay: Initial delay in seconds
        backoff: Backoff multiplier for each retry
        exceptions: Exception types to catch and retry
        
    Returns:
        Decorated async function
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await with_async_retry(
                func,
                retries=retries,
                delay=delay,
                backoff=backoff,
                exceptions=exceptions,
                *args,
                **kwargs
            )
        
        return wrapper
    
    return decorator


# Convenience wrappers using tenacity library
def with_tenacity_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
    exceptions: Union[Type[Exception], List[Type[Exception]]] = Exception
):
    """
    Use tenacity library for more advanced retry logic.
    
    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time between retries
        max_wait: Maximum wait time between retries
        exceptions: Exception types to retry on
        
    Returns:
        Decorated function with retry logic
    """
    exception_types = exceptions if isinstance(exceptions, list) else [exceptions]
    
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(tuple(exception_types)),
        before_sleep=lambda retry_state: logger.info(
            "Retry attempt",
            attempt=retry_state.attempt_number,
            wait=retry_state.next_action.sleep
        )
    )
