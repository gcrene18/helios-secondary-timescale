"""
Debugging utilities for the application
"""

import os
import json
from datetime import datetime
from loguru import logger
from pathlib import Path
from app.config import settings

# Create a dedicated directory for debug files
DEBUG_DIR = Path("debug_files")
SCREENSHOTS_DIR = DEBUG_DIR / "screenshots"
API_RESPONSES_DIR = DEBUG_DIR / "api_responses"

def ensure_debug_dirs():
    """Ensure all debug directories exist"""
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(API_RESPONSES_DIR, exist_ok=True)

# Initialize directories
ensure_debug_dirs()

async def save_screenshot(page, filename: str, category: str = "general") -> str:
    """
    Save a screenshot in an organized directory structure
    
    Args:
        page: Playwright page object
        filename: Base filename for the screenshot
        category: Category for organizing screenshots (e.g., "error", "debug", "api")
        
    Returns:
        Path to the saved screenshot
    """
    # Only save screenshots in development mode
    if not settings.DEBUG:
        return None
        
    # Create category subdirectory
    category_dir = SCREENSHOTS_DIR / category
    os.makedirs(category_dir, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_filename = filename.replace(" ", "_").replace("/", "_")
    path = category_dir / f"{clean_filename}_{timestamp}.png"
    
    try:
        # Save the screenshot
        await page.screenshot(path=str(path))
        logger.debug(f"Screenshot saved: {path}")
        return str(path)
    except Exception as e:
        logger.warning(f"Failed to save screenshot {filename}: {str(e)}")
        return None

def save_api_response(data, filename: str, event_id: str = None) -> str:
    """
    Save API response data to a file
    
    Args:
        data: Response data to save
        filename: Base filename 
        event_id: Optional event ID for organization
        
    Returns:
        Path to the saved file
    """
    # Only save API responses in development mode
    if not settings.DEBUG:
        return None
        
    # Create subdirectory for event if provided
    if event_id:
        response_dir = API_RESPONSES_DIR / f"event_{event_id}"
    else:
        response_dir = API_RESPONSES_DIR
        
    os.makedirs(response_dir, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_filename = filename.replace(" ", "_").replace("/", "_")
    path = response_dir / f"{clean_filename}_{timestamp}.json"
    
    try:
        # Save the data
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        logger.debug(f"API response saved: {path}")
        return str(path)
    except Exception as e:
        logger.warning(f"Failed to save API response {filename}: {str(e)}")
        return None
