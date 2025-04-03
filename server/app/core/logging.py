"""
Logging configuration for the StubHub Proxy API Server
"""
import sys
import os
from loguru import logger
from datetime import datetime

def setup_logging():
    """Configure application logging"""
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # Generate log filename with timestamp
    log_filename = os.path.join(logs_dir, f"stubhub_proxy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    # Configure loguru
    config = {
        "handlers": [
            {
                "sink": sys.stdout,
                "format": "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
                "level": "INFO",
            },
            {
                "sink": log_filename,
                "format": "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
                "level": "DEBUG",
                "rotation": "10 MB",
                "retention": "1 week",
            },
        ],
    }
    
    # Remove default logger and apply configuration
    logger.remove()
    for handler in config["handlers"]:
        logger.add(**handler)
    
    logger.info("Logging initialized")
    return logger
