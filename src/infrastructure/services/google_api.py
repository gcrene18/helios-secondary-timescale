"""
Google API service for interacting with Google Sheets.
"""
from typing import List, Dict, Any, Optional

from ...core.logging import get_logger
from ...data.google_sheets import GoogleSheetsClient
from ...domain.event import Event

logger = get_logger(__name__)

class GoogleSheetsService:
    """
    Service for interacting with Google Sheets API.
    
    This service wraps the GoogleSheetsClient to provide higher-level
    operations for the application.
    """
    
    def __init__(self):
        """Initialize the Google Sheets service."""
        self.client = GoogleSheetsClient()
        logger.info("Google Sheets service initialized")
    
    def fetch_events(self) -> List[Event]:
        """
        Fetch all events from the configured Google Sheet.
        
        Returns:
            List of Event objects
        """
        try:
            events = self.client.get_all_events()
            logger.info(f"Successfully fetched {len(events)} events from Google Sheets")
            return events
        except Exception as e:
            logger.error("Failed to fetch events from Google Sheets", error=str(e))
            return []
    
    def update_event_status(self, viagogo_id: str, status: str) -> bool:
        """
        Update the status of an event in the Google Sheet.
        
        Args:
            viagogo_id: The ID of the event to update
            status: The new status to set
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = self.client.update_event_status(viagogo_id, status)
            if result:
                logger.info(f"Updated status for event {viagogo_id} to '{status}'")
            else:
                logger.warning(f"Failed to update status for event {viagogo_id}")
            return result
        except Exception as e:
            logger.error(f"Error updating event status for {viagogo_id}", error=str(e))
            return False
