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
    event_name: str
    event_datetime: str
    venue: Dict[str, Any]
    listings: List[Dict[str, Any]]
    total_listings: int
    min_price: float
    max_price: float
    median_price: float
    fetched_at: str
    cached: bool

@router.get("/{event_id}", response_model=ListingResponse)
async def get_listings(
    event_id: str,
    force_refresh: bool = Query(True, description="Force fresh data fetch instead of using cache")
):
    """
    Get ticket listings for a specific StubHub event
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
        browser_pool = get_browser_pool()
        
        # Get listings using browser automation
        listings_data = await get_event_listings(event_id, browser_pool)
        
        # Cache the results
        if listings_data and not force_refresh:
            await cache_listings(event_id, listings_data)
        
        # Mark as not cached
        listings_data["cached"] = False
        
        return listings_data
    
    except Exception as e:
        logger.error(f"Failed to fetch listings for event {event_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch listings: {str(e)}"
        )
