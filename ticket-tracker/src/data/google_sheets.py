"""
Google Sheets integration for fetching event data.
"""
from typing import List, Dict, Any, Optional
import gspread
from gspread.exceptions import APIError, SpreadsheetNotFound
from oauth2client.service_account import ServiceAccountCredentials
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..core.logging import get_logger
from ..config.settings import settings
from ..domain.event import Event

logger = get_logger(__name__)

class GoogleSheetsClient:
    """
    Client for interacting with Google Sheets API to fetch event data.
    
    This class handles authentication and data retrieval from the configured
    Google Sheets document containing event information.
    """
    
    SCOPES = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    
    def __init__(self, credentials_file: str = None, sheet_id: str = None):
        """
        Initialize the Google Sheets client with credentials.
        
        Args:
            credentials_file: Path to the credentials JSON file
            sheet_id: ID of the Google Sheet to access
        """
        self.credentials_file = credentials_file or settings.google_credentials_file
        self.sheet_id = sheet_id or settings.google_sheet_id
        self.client = None
        self.worksheet_name = settings.events_worksheet_name
        
    def authenticate(self) -> None:
        """Authenticate with Google Sheets API."""
        try:
            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                self.credentials_file, 
                self.SCOPES
            )
            
            self.client = gspread.authorize(credentials)
            logger.info("Authenticated with Google Sheets API")
        except Exception as e:
            logger.error("Google Sheets authentication failed", error=str(e))
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((APIError, ConnectionError))
    )
    def get_sheet(self):
        """Get the Google Sheet by ID with retry logic."""
        if not self.client:
            self.authenticate()
            
        try:
            return self.client.open_by_key(self.sheet_id)
        except SpreadsheetNotFound:
            logger.error(f"Spreadsheet not found with ID: {self.sheet_id}")
            raise
        except Exception as e:
            logger.error("Error accessing Google Sheet", error=str(e))
            raise
    
    def get_events_worksheet(self):
        """Get the events worksheet from the Google Sheet."""
        sheet = self.get_sheet()
        
        try:
            return sheet.worksheet(self.worksheet_name)
        except Exception as e:
            logger.error(f"Worksheet '{self.worksheet_name}' not found", error=str(e))
            raise
    
    def get_all_events(self) -> List[Event]:
        """
        Fetch all events from the Google Sheet.
        
        Returns:
            List of Event objects parsed from the sheet data
        """
        worksheet = self.get_events_worksheet()
        all_rows = worksheet.get_all_values()
        
        if not all_rows or len(all_rows) < 2:  # Check for header + at least one row
            logger.warning("No event data found in Google Sheet")
            return []
            
        # Skip header row
        data_rows = all_rows[1:]
        events = []
        
        for i, row in enumerate(data_rows, start=2):  # Start from row 2 (1-indexed with header)
            try:
                event = Event.from_google_sheets_row(row)
                events.append(event)
            except Exception as e:
                logger.warning(f"Error parsing event at row {i}", error=str(e), row=row)
        
        logger.info(f"Successfully fetched {len(events)} events from Google Sheet")
        return events
    
    def update_event_status(self, viagogo_id: str, status: str, status_column: int = 6) -> bool:
        """
        Update the status of an event in the Google Sheet.
        
        Args:
            viagogo_id: The viagogo ID of the event to update
            status: The new status to set
            status_column: The column index for the status (0-indexed)
            
        Returns:
            True if update was successful, False otherwise
        """
        worksheet = self.get_events_worksheet()
        all_rows = worksheet.get_all_values()
        
        if not all_rows or len(all_rows) < 2:
            logger.warning("No event data found in Google Sheet for status update")
            return False
            
        # Skip header row
        data_rows = all_rows[1:]
        
        # Find the row with matching viagogo_id (typically in column 5, 0-indexed)
        row_idx = None
        for i, row in enumerate(data_rows, start=2):  # Start from row 2 (1-indexed with header)
            if len(row) > 5 and row[5] == viagogo_id:
                row_idx = i
                break
        
        if row_idx is None:
            logger.warning(f"Event with viagogo_id {viagogo_id} not found in sheet")
            return False
            
        try:
            # Update the status column
            worksheet.update_cell(row_idx, status_column + 1, status)  # Adjust for 1-indexed API
            logger.info(f"Updated status for event {viagogo_id} to '{status}'")
            return True
        except Exception as e:
            logger.error(f"Failed to update status for event {viagogo_id}", error=str(e))
            return False
