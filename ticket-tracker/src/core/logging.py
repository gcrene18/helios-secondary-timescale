"""
Logging configuration with Rich and structlog integration.
"""
import os
import sys
import logging
import structlog
from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install as install_rich_traceback
from datetime import datetime

from ..config.settings import settings

# Install rich traceback handler for beautiful exception formatting
install_rich_traceback(show_locals=True)

# Create console for rich output
console = Console()

def configure_logging():
    """Configure structured logging with Rich for console and file output."""
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Configure rich handler for console output
    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=True, 
        tracebacks_show_locals=True,
        markup=True,
        show_time=False,  # structlog will add this
    )
    
    # Configure file handler for persistent logs
    timestamp = datetime.now().strftime("%Y%m%d")
    file_handler = logging.FileHandler(f"logs/ticket_tracker_{timestamp}.log")
    
    # Basic logging configuration
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[rich_handler, file_handler]
    )
    
    # Define processors for structlog
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.contextvars.merge_contextvars,
        structlog.processors.dict_tracebacks,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]
    
    # Configure structlog to work with standard library logging
    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Create formatter for file handler
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(sort_keys=True)
        ],
    )
    file_handler.setFormatter(formatter)
    
    # Return a configured logger
    return structlog.get_logger()

def get_logger(name: str = None):
    """Get a configured logger instance."""
    return structlog.get_logger(name)
