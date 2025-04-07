"""
Celery tasks for listing data operations.
"""
import asyncio
from celery import Task, shared_task, current_task
from rich.console import Console
from datetime import datetime, timedelta

from ..core.logging import get_logger
from .celery_app import app
from ..infrastructure.database.event_repo import EventRepository
from ..infrastructure.services.stubhub_api import StubHubService

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

# Async helper for Celery task
async def _fetch_and_store_listings(event):
    """Fetch and store listings for a single event."""
    stubhub_service = StubHubService()
    return await stubhub_service.fetch_and_store_listings(event)

@app.task(base=LoggedTask, bind=True)
def fetch_listings_for_event(self, viagogo_id):
    """Fetch ticket listings for a specific event."""
    logger.info(f"Starting listing fetch for event with viagogo ID: {viagogo_id}")
    
    try:
        # Check if event exists in database
        event = EventRepository.get_by_viagogo_id(viagogo_id)
        
        if not event:
            logger.warning(f"Event with viagogo ID {viagogo_id} not found in database")
            return {"status": "failed", "error": "Event not found"}
        
        # Run the async function in the Celery task
        count = asyncio.run(_fetch_and_store_listings(event))
        
        return {
            "status": "completed", 
            "event_id": event.id,
            "event_name": event.name,
            "viagogo_id": viagogo_id,
            "listings_count": count
        }
        
    except Exception as e:
        logger.error(f"Error fetching listings: {str(e)}")
        raise

@app.task(base=LoggedTask, bind=True)
def fetch_all_listings(self):
    """Fetch listings for all tracked events."""
    logger.info("Starting listing fetch for all tracked events")
    
    try:
        # Import here to ensure it's available in the Celery worker context
        from ..infrastructure.database.event_repo import EventRepository
        
        logger.info("Getting tracked events from database")
        
        # Get all tracked events from database
        try:
            events = EventRepository.get_tracked()
            if events is None:
                logger.error("get_tracked() returned None instead of a list")
                return {"status": "failed", "error": "Database query returned None"}
                
            event_count = len(events) if events else 0
            logger.info(f"Retrieved {event_count} tracked events")
            
            # Debug: Print first few events to verify data
            if events and len(events) > 0:
                for i, event in enumerate(events[:3]):
                    logger.debug(f"Event {i+1}: {event.name} (ID: {event.event_id}, viagogo_id: {event.viagogo_id})")
            
        except Exception as db_error:
            logger.error(f"Database error when fetching tracked events: {str(db_error)}", exc_info=True)
            return {"status": "failed", "error": f"Database error: {str(db_error)}"}
        
        if not events:
            logger.warning("No tracked events found in database")
            return {"status": "completed", "count": 0}
        
        # Create tasks for each event with throttling
        task_ids = []
        batch_size = 5  # Process events in batches of 5
        delay_between_batches = 30  # 30 seconds between batches
        
        # Group events into batches
        batches = [events[i:i + batch_size] for i in range(0, len(events), batch_size)]
        logger.info(f"Split {len(events)} events into {len(batches)} batches of {batch_size}")
        
        # Schedule first batch immediately
        for i, batch in enumerate(batches):
            batch_task_ids = []
            
            # Log which batch we're processing
            logger.info(f"Processing batch {i+1}/{len(batches)} with {len(batch)} events")
            
            for event in batch:
                try:
                    if not hasattr(event, 'viagogo_id') or not event.viagogo_id:
                        logger.warning(f"Skipping event with missing viagogo_id: {event.name if hasattr(event, 'name') else 'Unknown'}")
                        continue
                    
                    # For first batch, schedule immediately
                    if i == 0:
                        result = fetch_listings_for_event.delay(event.viagogo_id)
                    else:
                        # For subsequent batches, use apply_async with ETA
                        eta = datetime.now() + timedelta(seconds=i * delay_between_batches)
                        result = fetch_listings_for_event.apply_async(
                            args=[event.viagogo_id],
                            eta=eta
                        )
                    
                    batch_task_ids.append(result.id)
                    logger.info(f"Scheduled task for event {event.name} (ID: {event.viagogo_id}), batch {i+1}, ETA: {eta if i > 0 else 'immediate'}")
                except Exception as task_error:
                    logger.error(f"Error scheduling task for event {event.viagogo_id if hasattr(event, 'viagogo_id') else 'Unknown'}: {str(task_error)}")
            
            task_ids.extend(batch_task_ids)
        
        return {
            "status": "scheduled",
            "events_count": len(events),
            "tasks_scheduled": len(task_ids),
            "batches": len(batches)
        }
        
    except Exception as e:
        logger.error(f"Error in fetch_all_listings task: {str(e)}", exc_info=True)
        # Return error instead of raising to prevent task retry
        return {"status": "failed", "error": str(e)}

@app.task(base=LoggedTask, bind=True)
def fetch_outdated_listings(self, hours=12):
    """Fetch listings for events not updated recently."""
    logger.info(f"Starting fetch for events not updated in {hours} hours")
    
    try:
        # Get events not updated recently
        events = EventRepository.get_not_updated_since(hours=hours)
        
        if not events:
            logger.warning(f"No events found that were not updated in the last {hours} hours")
            return {"status": "completed", "count": 0}
        
        # Create tasks for each event
        for event in events:
            # Queue a task for each event
            fetch_listings_for_event.delay(event.viagogo_id)
        
        return {
            "status": "scheduled",
            "events_count": len(events)
        }
        
    except Exception as e:
        logger.error(f"Error scheduling outdated listing fetches: {str(e)}")
        raise

@app.task(base=LoggedTask, bind=True)
def debug_database_connection(self):
    """Debug task to test database connectivity and event retrieval."""
    from ..core.logging import get_logger
    logger = get_logger(__name__)
    
    logger.info("Starting database connection debug task")
    
    result = {
        "status": "started",
        "database_connection": False,
        "event_retrieval": False,
        "tracked_event_retrieval": False,
        "errors": []
    }
    
    try:
        # Test database connection
        from ..core.db import db
        db_status = db.test_connection()
        result["database_connection"] = db_status
        logger.info(f"Database connection test: {'Success' if db_status else 'Failed'}")
        
        # Test event retrieval
        try:
            from ..infrastructure.database.event_repo import EventRepository
            all_events = EventRepository.get_all()
            result["event_retrieval"] = True
            result["all_events_count"] = len(all_events) if all_events else 0
            logger.info(f"Retrieved {result['all_events_count']} total events")
            
            # Test tracked event retrieval
            try:
                tracked_events = EventRepository.get_tracked()
                result["tracked_event_retrieval"] = True
                result["tracked_events_count"] = len(tracked_events) if tracked_events else 0
                logger.info(f"Retrieved {result['tracked_events_count']} tracked events")
            except Exception as e:
                error_msg = f"Error retrieving tracked events: {str(e)}"
                logger.error(error_msg)
                result["errors"].append(error_msg)
                
        except Exception as e:
            error_msg = f"Error retrieving all events: {str(e)}"
            logger.error(error_msg)
            result["errors"].append(error_msg)
            
    except Exception as e:
        error_msg = f"Error connecting to database: {str(e)}"
        logger.error(error_msg)
        result["errors"].append(error_msg)
    
    result["status"] = "completed"
    return result

@app.task(base=LoggedTask, bind=True)
def debug_simple(self):
    """A simple debug task that doesn't rely on imports or database connections."""
    import os
    import sys
    import platform
    
    # Get basic system information
    result = {
        "status": "completed",
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "cwd": os.getcwd(),
        "env_vars": {k: v for k, v in os.environ.items() if k.startswith(('CELERY_', 'REDIS_', 'DB_', 'POSTGRES'))},
        "sys_path": sys.path,
    }
    
    return result