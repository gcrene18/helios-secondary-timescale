"""
Service for fetching StubHub event listings using browser automation
"""
from loguru import logger
import asyncio
import json
import random
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from playwright.async_api import Page

from app.config import settings
from app.services.browser_pool import BrowserPool, BrowserSession
from app.utils.stealth import perform_human_like_actions, add_random_delay


async def get_event_listings(event_id: str, browser_pool: BrowserPool) -> Dict[str, Any]:
    """
    Fetch ticket listings for a specific StubHub event
    
    Args:
        event_id: StubHub event ID
        browser_pool: Browser pool instance
        
    Returns:
        Dictionary containing event and listing data
    """
    session = None
    try:
        # Get a browser session from the pool
        session = await browser_pool.get_session()
        
        # Get event data
        logger.info(f"Fetching listings for event {event_id} using session {session.id}")
        
        # Create a new page
        page = await session.context.new_page()
        
        # Fetch the data
        event_data = await _fetch_event_data(page, event_id)
        listings_data = await _fetch_listing_data(page, event_id)
        
        # Close the page
        await page.close()
        
        # Process and combine the data
        result = _process_event_and_listings(event_id, event_data, listings_data)
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching listings for event {event_id}: {str(e)}")
        raise
        
    finally:
        # Release the session back to the pool
        if session:
            await browser_pool.release_session(session.id)


async def _fetch_event_data(page: Page, event_id: str) -> Dict[str, Any]:
    """Fetch event details from StubHub"""
    try:
        # Navigate to the event page
        event_url = f"{settings.STUBHUB_BASE_URL}/event/{event_id}"
        logger.debug(f"Navigating to event page: {event_url}")
        
        await page.goto(event_url, timeout=settings.BROWSER_TIMEOUT_SECONDS * 1000)
        
        # Add random delay to mimic human behavior
        await add_random_delay(settings.MIN_PAGE_DELAY_MS, settings.MAX_PAGE_DELAY_MS)
        
        # Perform some random human-like actions on the page
        if settings.ADD_RANDOM_ACTIONS:
            await perform_human_like_actions(page)
        
        # Wait for the event data to be loaded
        # This could be extracted by monitoring network requests or from the DOM
        
        # For now, extract basic event info from the page
        title = await page.title()
        
        # Let's extract basic event information from the page
        event_data = {
            "event_id": event_id,
            "event_name": await _extract_event_name(page),
            "event_datetime": await _extract_event_datetime(page),
            "venue": await _extract_venue_info(page),
        }
        
        logger.debug(f"Extracted event data: {json.dumps(event_data)}")
        return event_data
        
    except Exception as e:
        logger.error(f"Error fetching event data for {event_id}: {str(e)}")
        raise


async def _fetch_listing_data(page: Page, event_id: str) -> List[Dict[str, Any]]:
    """Fetch ticket listing data from StubHub"""
    try:
        # StubHub loads listing data via API calls when you browse the event page
        # We'll need to intercept these network requests to get the listing data
        
        # For demonstration, we'll monitor for API calls and extract data
        listings = []
        
        # Set up request interception for the listings API
        async def handle_listings_response(response):
            if "inventory/listings" in response.url and response.status == 200:
                try:
                    json_data = await response.json()
                    if "listing" in json_data:
                        nonlocal listings
                        listings = json_data["listing"]
                        logger.debug(f"Intercepted listings data with {len(listings)} listings")
                except Exception as e:
                    logger.error(f"Error parsing listings response: {str(e)}")
        
        # Listen for response events
        page.on("response", handle_listings_response)
        
        # Scroll down to trigger the listings API call
        for i in range(5):
            await page.evaluate("window.scrollBy(0, 300)")
            await add_random_delay(300, 800)
        
        # If we didn't get listings data from the interception, we can try other methods
        # For example, we could parse the DOM directly
        
        if not listings:
            # Fallback: Try to extract listings from DOM (implementation would depend on site structure)
            logger.warning("No listings data intercepted, attempting fallback extraction")
            listings = await _extract_listings_from_dom(page)
        
        return listings
        
    except Exception as e:
        logger.error(f"Error fetching listing data for {event_id}: {str(e)}")
        raise


def _process_event_and_listings(event_id: str, event_data: Dict[str, Any], listings_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process and combine event and listing data"""
    try:
        # Calculate price statistics
        prices = [float(listing.get("currentPrice", {}).get("amount", 0)) for listing in listings_data if listing.get("currentPrice")]
        
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        median_price = sorted(prices)[len(prices)//2] if prices else 0
        
        # Combine the data
        result = {
            **event_data,
            "listings": listings_data,
            "total_listings": len(listings_data),
            "min_price": min_price,
            "max_price": max_price,
            "median_price": median_price,
            "fetched_at": datetime.now().isoformat()
        }
        
        logger.info(f"Processed listings for event {event_id}: {len(listings_data)} listings found")
        return result
        
    except Exception as e:
        logger.error(f"Error processing event and listing data: {str(e)}")
        raise


# Helper functions for data extraction

async def _extract_event_name(page: Page) -> str:
    """Extract event name from the page"""
    try:
        # This would need to be adapted to StubHub's actual DOM structure
        event_name = await page.evaluate('''
            () => {
                const titleEl = document.querySelector('h1');
                return titleEl ? titleEl.innerText.trim() : 'Unknown Event';
            }
        ''')
        return event_name
    except Exception:
        return "Unknown Event"


async def _extract_event_datetime(page: Page) -> str:
    """Extract event datetime from the page"""
    try:
        # This would need to be adapted to StubHub's actual DOM structure
        event_datetime = await page.evaluate('''
            () => {
                const dateEl = document.querySelector('[data-testid="event-date"]');
                return dateEl ? dateEl.innerText.trim() : '';
            }
        ''')
        return event_datetime or datetime.now().isoformat()
    except Exception:
        return datetime.now().isoformat()


async def _extract_venue_info(page: Page) -> Dict[str, str]:
    """Extract venue information from the page"""
    try:
        # This would need to be adapted to StubHub's actual DOM structure
        venue_info = await page.evaluate('''
            () => {
                const venueEl = document.querySelector('[data-testid="event-venue"]');
                const locationEl = document.querySelector('[data-testid="event-location"]');
                
                return {
                    name: venueEl ? venueEl.innerText.trim() : 'Unknown Venue',
                    location: locationEl ? locationEl.innerText.trim() : 'Unknown Location'
                };
            }
        ''')
        return venue_info
    except Exception:
        return {"name": "Unknown Venue", "location": "Unknown Location"}


async def _extract_listings_from_dom(page: Page) -> List[Dict[str, Any]]:
    """Fallback method to extract listings from the DOM"""
    try:
        # This would need to be adapted to StubHub's actual DOM structure
        listings = await page.evaluate('''
            () => {
                const listingElements = document.querySelectorAll('[data-testid="listing-item"]');
                const listings = [];
                
                listingElements.forEach(el => {
                    const priceEl = el.querySelector('[data-testid="listing-price"]');
                    const sectionEl = el.querySelector('[data-testid="listing-section"]');
                    const rowEl = el.querySelector('[data-testid="listing-row"]');
                    const quantityEl = el.querySelector('[data-testid="listing-quantity"]');
                    
                    listings.push({
                        id: el.id || `listing-${listings.length}`,
                        currentPrice: {
                            amount: priceEl ? parseFloat(priceEl.innerText.replace(/[^0-9.]/g, '')) : 0,
                            currency: 'USD'
                        },
                        section: sectionEl ? sectionEl.innerText.trim() : 'Unknown',
                        row: rowEl ? rowEl.innerText.trim() : 'Unknown',
                        quantity: quantityEl ? parseInt(quantityEl.innerText) : 1
                    });
                });
                
                return listings;
            }
        ''')
        return listings
    except Exception as e:
        logger.error(f"Error extracting listings from DOM: {str(e)}")
        return []
