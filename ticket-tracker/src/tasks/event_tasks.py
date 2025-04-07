"""
Celery tasks for event data operations.
"""
from celery import Task
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from ..core.logging import get_logger
from .celery_app import app
from ..data.google_sheets import GoogleSheetsClient
from ..infrastructure.services.google_api import GoogleSheetsService
from ..infrastructure.database.event_repo import EventRepository

console = Console()
logger = get_logger(__name__)

class LoggedTask(Task):
    """Base task with rich logging."""
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            f"Task {self.name} failed",
            task_id=task_id,
            exception=str(exc),
            args=args,
            kwargs=kwargs
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)
        
    def on_success(self, retval, task_id, args, kwargs):
        logger.info(
            f"Task {self.name} succeeded",
            task_id=task_id,
            result=retval,
            args=args,
            kwargs=kwargs
        )
        super().on_success(retval, task_id, args, kwargs)

@app.task(base=LoggedTask, bind=True)
def fetch_events(self):
    """Fetch events from Google Sheets and store in database."""
    logger.info("Starting event fetch from Google Sheets")
    
    try:
        # Create Google Sheets service
        sheets_service = GoogleSheetsService()
        
        # Fetch events
        events = sheets_service.fetch_events()
        
        if not events:
            logger.warning("No events found in Google Sheet")
            return {"status": "completed", "count": 0}
        
        # Log events found
        logger.info(f"Found {len(events)} events in Google Sheet")
        
        # Sync events to database
        stats = EventRepository.sync_from_google_sheets(events)
        
        return {
            "status": "completed",
            "inserted": stats['inserted'],
            "updated": stats['updated'],
            "failed": stats['failed'],
            "count": len(events)
        }
        
    except Exception as e:
        logger.error(f"Error fetching events: {str(e)}")
        raise