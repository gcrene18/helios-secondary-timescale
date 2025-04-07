"""
Event repository for database operations.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from ...core.db import db
from ...core.logging import get_logger
from ...domain.event import Event

logger = get_logger(__name__)

class EventRepository:
    """
    Repository for event data operations.
    
    This class handles database operations for event entities,
    including CRUD operations and specific queries.
    """
    
    TABLE_NAME = "events"
    
    @staticmethod
    def ensure_table_exists():
        """Ensure the events table exists in the database."""
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {EventRepository.TABLE_NAME} (
            event_id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            venue TEXT NOT NULL,
            city TEXT NOT NULL,
            country TEXT NOT NULL,
            event_date TIMESTAMP NOT NULL,
            viagogo_id TEXT NOT NULL UNIQUE,
            is_tracked BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_listings_fetch TIMESTAMP
        );
        """
        
        # Add is_tracked column if it doesn't exist
        alter_table_sql = f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = '{EventRepository.TABLE_NAME}' AND column_name = 'is_tracked'
            ) THEN
                ALTER TABLE {EventRepository.TABLE_NAME} ADD COLUMN is_tracked BOOLEAN NOT NULL DEFAULT TRUE;
            END IF;
        END $$;
        """
        
        # Add last_listings_fetch column if it doesn't exist
        alter_table_sql_last_listings_fetch = f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = '{EventRepository.TABLE_NAME}' AND column_name = 'last_listings_fetch'
            ) THEN
                ALTER TABLE {EventRepository.TABLE_NAME} ADD COLUMN last_listings_fetch TIMESTAMP;
            END IF;
        END $$;
        """
        
        try:
            db.execute(create_table_sql)
            db.execute(alter_table_sql)
            db.execute(alter_table_sql_last_listings_fetch)
            logger.info(f"Ensured table {EventRepository.TABLE_NAME} exists with is_tracked and last_listings_fetch columns")
            return True
        except Exception as e:
            logger.error(f"Failed to create/update table {EventRepository.TABLE_NAME}", error=str(e))
            return False
    
    @staticmethod
    def get_all() -> List[Event]:
        """Get all events from the database."""
        query = f"SELECT * FROM {EventRepository.TABLE_NAME} ORDER BY event_date;"
        
        try:
            results = db.execute(query, commit=False)
            
            if not results:
                return []
                
            events = [Event.from_dict(dict(row)) for row in results]
            logger.info(f"Retrieved {len(events)} events from database")
            return events
        except Exception as e:
            logger.error("Error retrieving events", error=str(e))
            return []
    
    @staticmethod
    def get_by_id(event_id: int) -> Optional[Event]:
        """Get an event by its ID."""
        query = f"SELECT * FROM {EventRepository.TABLE_NAME} WHERE event_id = %s;"
        
        try:
            results = db.execute(query, (event_id,), commit=False)
            
            if not results:
                logger.warning(f"Event with ID {event_id} not found")
                return None
                
            return Event.from_dict(dict(results[0]))
        except Exception as e:
            logger.error(f"Error retrieving event with ID {event_id}", error=str(e))
            return None
    
    @staticmethod
    def get_by_viagogo_id(viagogo_id: str) -> Optional[Event]:
        """Get an event by its viagogo ID."""
        query = f"SELECT * FROM {EventRepository.TABLE_NAME} WHERE viagogo_id = %s;"
        
        try:
            results = db.execute(query, (viagogo_id,), commit=False)
            
            if not results:
                logger.debug(f"Event with viagogo ID {viagogo_id} not found")
                return None
                
            return Event.from_dict(dict(results[0]))
        except Exception as e:
            logger.error(f"Error retrieving event with viagogo ID {viagogo_id}", error=str(e))
            return None
    
    @staticmethod
    def insert(event: Event) -> Optional[int]:
        """
        Insert a new event into the database.
        
        Returns:
            The ID of the new event, or None if insertion failed
        """
        insert_sql = f"""
        INSERT INTO {EventRepository.TABLE_NAME} 
        (name, venue, city, country, event_date, viagogo_id, is_tracked, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING event_id;
        """
        
        try:
            now = datetime.now()
            params = (
                event.name,
                event.venue,
                event.city,
                event.country,
                event.event_date,
                event.viagogo_id,
                event.is_tracked,
                now,
                now
            )
            
            result = db.execute(insert_sql, params)
            
            if result and len(result) > 0:
                event_id = result[0]['event_id']
                logger.info(f"Inserted event with ID {event_id}: {event.name}")
                return event_id
            else:
                logger.warning(f"Failed to insert event: {event.name}")
                return None
        except Exception as e:
            logger.error(f"Error inserting event {event.name}", error=str(e))
            return None
    
    @staticmethod
    def update(event: Event) -> bool:
        """Update an existing event in the database."""
        if not event.event_id:
            logger.error("Cannot update event without event_id")
            return False
            
        update_sql = f"""
        UPDATE {EventRepository.TABLE_NAME}
        SET name = %s, venue = %s, city = %s, country = %s, event_date = %s,
            viagogo_id = %s, is_tracked = %s, updated_at = %s
        WHERE event_id = %s;
        """
        
        try:
            params = (
                event.name,
                event.venue,
                event.city,
                event.country,
                event.event_date,
                event.viagogo_id,
                event.is_tracked,
                datetime.now(),
                event.event_id
            )
            
            db.execute(update_sql, params)
            logger.info(f"Updated event with ID {event.event_id}: {event.name}")
            return True
        except Exception as e:
            logger.error(f"Error updating event with ID {event.event_id}", error=str(e))
            return False
    
    @staticmethod
    def delete(event_id: int) -> bool:
        """Delete an event from the database."""
        delete_sql = f"DELETE FROM {EventRepository.TABLE_NAME} WHERE event_id = %s;"
        
        try:
            db.execute(delete_sql, (event_id,))
            logger.info(f"Deleted event with ID {event_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting event with ID {event_id}", error=str(e))
            return False
    
    @staticmethod
    def update_last_listings_fetch(event_id: int) -> bool:
        """Update the timestamp of when listings were last fetched for an event."""
        update_sql = f"""
        UPDATE {EventRepository.TABLE_NAME}
        SET last_listings_fetch = %s
        WHERE event_id = %s;
        """
        
        try:
            db.execute(update_sql, (datetime.now(), event_id))
            logger.debug(f"Updated last_listings_fetch for event ID {event_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating last_listings_fetch for event ID {event_id}", error=str(e))
            return False
    
    @staticmethod
    def get_events_needing_update(hours: int = 12) -> List[Event]:
        """
        Get events that haven't had their listings updated in the specified number of hours.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of Event objects that need updating
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        query = f"""
        SELECT * FROM {EventRepository.TABLE_NAME}
        WHERE is_tracked = TRUE AND (last_listings_fetch IS NULL OR last_listings_fetch < %s)
        ORDER BY last_listings_fetch ASC NULLS FIRST;
        """
        
        with db.cursor() as cursor:
            cursor.execute(query, (cutoff_time,))
            rows = cursor.fetchall()
            
        return [Event(**row) for row in rows]
        
    @staticmethod
    def get_tracked() -> List[Event]:
        """
        Get all events that are marked as tracked.
        
        Returns:
            List of Event objects that are tracked.
        """
        from ...core.logging import get_logger
        logger = get_logger(__name__)
        
        logger.info("Fetching tracked events from database")
        
        query = f"""
        SELECT * FROM {EventRepository.TABLE_NAME}
        WHERE is_tracked = TRUE
        ORDER BY event_date ASC;
        """
        
        try:
            with db.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()
                
            events = [Event(**row) for row in rows]
            logger.info(f"Retrieved {len(events)} tracked events from database")
            return events
        except Exception as e:
            logger.error(f"Error fetching tracked events: {str(e)}")
            return []
    
    @staticmethod
    def sync_from_google_sheets(events: List[Event]) -> Dict[str, int]:
        """
        Synchronize events from Google Sheets to the database.
        
        This method will insert new events and update existing ones.
        Events with is_tracked=False will be skipped for insertion
        but existing events will be updated with the tracking status.
        
        Args:
            events: List of Event objects from Google Sheets
            
        Returns:
            Dictionary with counts of inserted, updated, skipped and failed events
        """
        stats = {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,  # For events with is_tracked=False
            "failed": 0
        }
        
        for event in events:
            # Check if event already exists
            existing = EventRepository.get_by_viagogo_id(event.viagogo_id)
            
            if existing:
                # Update event with new data from sheets but keep the ID
                event.event_id = existing.event_id
                event.created_at = existing.created_at
                
                if EventRepository.update(event):
                    stats["updated"] += 1
                else:
                    stats["failed"] += 1
            else:
                # Skip events that are not to be tracked
                if not event.is_tracked:
                    logger.info(f"Skipping untracked event: {event.name} ({event.viagogo_id})")
                    stats["skipped"] += 1
                    continue
                
                # Insert new event if it's tracked
                if EventRepository.insert(event) is not None:
                    stats["inserted"] += 1
                else:
                    stats["failed"] += 1
        
        logger.info(
            f"Event sync completed: {stats['inserted']} inserted, "
            f"{stats['updated']} updated, {stats['skipped']} skipped, "
            f"{stats['failed']} failed"
        )
        return stats
