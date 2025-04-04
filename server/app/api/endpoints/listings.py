"""
Endpoints for fetching StubHub event listings
"""
from fastapi import APIRouter, HTTPException, status, Query, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from loguru import logger
from app.services.browser_pool import get_browser_pool
from app.services.listing_service import get_event_listings
from app.db.cache import get_cached_listings, cache_listings

router = APIRouter()

class ListingResponse(BaseModel):
    """Response model for listing data"""
    event_id: str
    event_name: Optional[str] = None
    event_datetime: Optional[str] = None
    venue: Optional[Dict[str, Any]] = {}
    listings: List[Dict[str, Any]]
    stats: Dict[str, Any]
    metadata: Dict[str, Any]
    cached: bool = False

@router.get("/{event_id}", response_model=ListingResponse)
async def get_listings(
    event_id: str,
    force_refresh: bool = Query(False, description="Force fresh data fetch instead of using cache"),
    fetch_venue_map: bool = Query(False, description="Fetch venue map data along with listings")
):
    """
    Get ticket listings for a specific StubHub event
    
    Args:
        event_id: StubHub event ID
        force_refresh: Force fresh data fetch instead of using cache
        fetch_venue_map: Fetch venue map data along with listings (default: False)
        
    Returns:
        Listing data including stats and metadata
    """
    try:
        # Check cache first if not forcing refresh
        if not force_refresh:
            cached_data = await get_cached_listings(event_id)
            if cached_data:
                logger.info(f"Returning cached listings for event {event_id}")
                cached_data["cached"] = True
                return cached_data
        
        # No cache or force refresh, fetch fresh data
        logger.info(f"Fetching fresh listings for event {event_id}")
        
        # Get browser pool - make sure to await the async function
        browser_pool = await get_browser_pool()
        
        # Get listings using browser automation
        listings_data = await get_event_listings(event_id, browser_pool, fetch_venue_map=fetch_venue_map)
        
        # Add basic validation to ensure data meets the model requirements
        if not listings_data:
            logger.error(f"No listings data returned for event {event_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No listings found for event {event_id}"
            )
            
        # Ensure required fields exist
        if "listings" not in listings_data or "stats" not in listings_data:
            logger.error(f"Missing required fields in response data for event {event_id}: {listings_data.keys()}")
            # Try to recover - create empty fields if missing
            listings_data["listings"] = listings_data.get("listings", [])
            listings_data["stats"] = listings_data.get("stats", {})
            listings_data["metadata"] = listings_data.get("metadata", {})
        
        # Cache the results if we have valid data
        if listings_data and not force_refresh:
            await cache_listings(event_id, listings_data)
        
        # Mark as not cached
        listings_data["cached"] = False
        
        # Log what we're returning
        logger.info(f"Returning {len(listings_data.get('listings', []))} listings for event {event_id}")
        
        return listings_data
    
    except Exception as e:
        logger.error(f"Failed to fetch listings for event {event_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch listings: {str(e)}"
        )
