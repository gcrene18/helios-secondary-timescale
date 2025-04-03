"""
StubHub API service for fetching ticket listings.
"""
from typing import List, Dict, Any, Optional
import asyncio
from datetime import datetime

from ...core.logging import get_logger, console
from ...data.stubhub import StubHubClient
from ...domain.listing import Listing
from ...domain.event import Event
from ...infrastructure.database.event_repo import EventRepository
from ...infrastructure.database.listing_repo import ListingRepository
from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn

logger = get_logger(__name__)

class StubHubService:
    """
    Service for interacting with StubHub API.
    
    This service coordinates the fetching of ticket listings
    and storing them in the database.
    """
    
    def __init__(self):
        """Initialize the StubHub service."""
        self.client = StubHubClient()
        logger.info("StubHub service initialized")
    
    async def fetch_and_store_listings(self, event: Event) -> int:
        """
        Fetch ticket listings for an event and store them in the database.
        
        Args:
            event: The Event to fetch listings for
            
        Returns:
            Number of listings stored
        """
        if not event.event_id:
            # Try to get the event ID from the database
            db_event = EventRepository.get_by_viagogo_id(event.viagogo_id)
            if db_event:
                event.event_id = db_event.event_id
            else:
                logger.error(f"Cannot fetch listings for event without event_id: {event.name}")
                return 0
        
        try:
            # Fetch listings from StubHub API
            listings = await self.client.get_listings_with_retry(event.viagogo_id)
            
            if not listings:
                logger.warning(f"No listings found for event {event.name} (ID: {event.event_id})")
                return 0
            
            # Store listings in database
            count = ListingRepository.batch_insert(event.event_id, listings)
            
            logger.info(
                f"Stored {count} listings for event {event.name} "
                f"(ID: {event.event_id}, viagogo: {event.viagogo_id})"
            )
            return count
        except Exception as e:
            logger.error(
                f"Error fetching and storing listings for event {event.name}",
                error=str(e)
            )
            return 0
    
    async def fetch_all_events_listings(self, events: List[Event]) -> Dict[str, int]:
        """
        Fetch and store listings for multiple events.
        
        Args:
            events: List of Event objects to fetch listings for
            
        Returns:
            Dictionary with event viagogo IDs and listing counts
        """
        results = {}
        
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task(f"Processing {len(events)} events...", total=len(events))
            
            for event in events:
                count = await self.fetch_and_store_listings(event)
                results[event.viagogo_id] = count
                progress.update(task, advance=1)
        
        # Log summary
        total_listings = sum(results.values())
        events_with_listings = sum(1 for count in results.values() if count > 0)
        
        logger.info(
            f"Processed {len(events)} events, found listings for {events_with_listings} events, "
            f"stored {total_listings} total listings"
        )
        
        return results
