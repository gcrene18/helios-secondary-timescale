"""
Service for fetching and processing StubHub event listings
"""

import asyncio
import json
import random
import time
import traceback
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from playwright.async_api import Page
from loguru import logger

from app.config import settings
from app.services.browser_pool import BrowserPool, BrowserSession
from app.utils.stealth import perform_human_like_actions, add_random_delay
from app.utils.debug import save_screenshot, save_api_response
import math
from decimal import Decimal
from dateutil.parser import parse


def _ensure_serializable(data):
    """
    Recursively ensure all data is JSON serializable
    - Convert non-serializable types to strings or compatible formats
    - Handle datetime objects, special numeric types, etc.
    """
    if isinstance(data, dict):
        return {k: _ensure_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_ensure_serializable(item) for item in data]
    elif isinstance(data, (datetime, date)):
        return data.isoformat()
    elif isinstance(data, (Decimal, float)) and (math.isnan(data) or math.isinf(data)):
        return str(data)  # Convert NaN or Inf to string
    elif data is None or isinstance(data, (str, int, float, bool)):
        return data
    else:
        # Convert any other types to string representation
        return str(data)


async def get_event_listings(event_id: str, browser_pool: BrowserPool, event_data: Optional[Dict[str, Any]] = None, fetch_venue_map: bool = False) -> Dict[str, Any]:
    """
    Fetch ticket listings for a specific StubHub event via StubHub Pro
    
    Args:
        event_id: StubHub event ID
        browser_pool: Browser pool instance
        event_data: Optional event data to include in the response
        fetch_venue_map: Whether to fetch venue map data (default: False)
        
    Returns:
        Dictionary containing event and listing data
    """
    session = None
    try:
        # Get a browser session from the pool
        session = await browser_pool.get_session()
        
        # Log the request
        logger.info(f"Fetching listings for event {event_id} using session {session.id}")
        
        # Create a new page
        page = await session.context.new_page()
        
        # Navigate to the event page
        event_data = await _fetch_event_data(page, event_id)
        
        # Use the interceptor to get listings
        logger.info(f"Fetching listings data for event {event_id}")
        listings_data = await _fetch_listing_data(page, event_id, fetch_venue_map)
        
        # Close the page
        await page.close()
        
        # Process and combine the data
        result = _process_event_and_listings(event_id, event_data, listings_data)
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching listings for event {event_id}: {str(e)}")
        # Take screenshot for debugging if possible
        if session:
            try:
                pages = await session.context.pages()
                if pages:
                    await save_screenshot(pages[0], f"error_{event_id}.png")
            except:
                pass
        raise
        
    finally:
        # Always release the session back to the pool
        if session:
            await browser_pool.release_session(session.id)


async def _fetch_event_data(page: Page, event_id: str) -> Dict[str, Any]:
    """
    Navigate to the event page on StubHub Pro and prepare for listing data fetching.
    This function only navigates to the page and ensures it's ready for the subsequent
    API call to fetch listings.
    """
    try:
        # Navigate to the event page on StubHub Pro
        pro_event_url = f"https://pro.stubhub.com/inventory/event?eventId={event_id}"
        logger.info(f"Navigating to StubHub Pro event page: {pro_event_url}")
        
        await page.goto(pro_event_url, timeout=settings.BROWSER_TIMEOUT_SECONDS * 1000)
        
        # Add random delay to mimic human behavior
        await add_random_delay(settings.MIN_PAGE_DELAY_MS, settings.MAX_PAGE_DELAY_MS)
        
        # Check if we need to log in
        if await page.locator("text=Sign In").count() > 0 or page.url.startswith("https://account.stubhub.com/login"):
            logger.warning("Login required but should have been handled by session management")
            # The browser_pool's ensure_login should have already handled this
            await save_screenshot(page, f"login_needed_{event_id}.png")
            raise Exception("Login required but session should already be authenticated")
        
        # Save a screenshot for debugging/verification
        await save_screenshot(page, f"event_page_{event_id}.png")
        
        # Return minimal event data - we'll get details from the API response
        event_data = {
            "event_id": event_id,
            "source": "stubhub_pro",
            "fetched_at": datetime.now().isoformat(),
        }
        
        logger.info(f"Successfully navigated to event page for {event_id}")
        return event_data
        
    except Exception as e:
        logger.error(f"Error navigating to event page for {event_id}: {str(e)}")
        # Take a screenshot if possible for debugging
        try:
            await save_screenshot(page, f"event_error_{event_id}.png")
        except:
            pass
        raise


async def _fetch_listing_data(page: Page, event_id: str, fetch_venue_map: bool = False) -> Dict[str, Any]:
    """Fetch listing data from StubHub Pro by intercepting the API request
    
    Args:
        page: Playwright page object
        event_id: StubHub event ID
        fetch_venue_map: Whether to fetch venue map data (default: False)
        
    Returns:
        Dictionary containing listings and optionally venue map data
    """
    try:
        logger.info(f"Setting up API interception for event {event_id} listings")
        
        # Variable to store intercepted API data
        api_listings_data = []
        venue_map_data = None
        api_response_received = asyncio.Event()
        venue_map_received = asyncio.Event()
        
        # Set up response interception for listings
        async def handle_response(response):
            nonlocal api_listings_data, venue_map_data
            
            # Check if this is the GetCompListingsByEventId endpoint
            if "GetCompListingsByEventId" in response.url and response.status == 200:
                try:
                    logger.info(f"Intercepted response from StubHub Pro API: {response.url}")
                    json_data = await response.json()
                    
                    # Save raw response for debugging
                    try:
                        save_api_response(json_data, f"api_raw_response_{event_id}", event_id)
                        logger.info(f"Saved raw API response to api_raw_response_{event_id}.json")
                    except Exception as e:
                        logger.warning(f"Failed to save raw API response: {str(e)}")
                    
                    # The API response is always a list of listings
                    if isinstance(json_data, list):
                        api_listings_data = json_data
                        logger.info(f"Found {len(api_listings_data)} listings from API interception")
                        
                        # Log a sample listing for debugging structure
                        if api_listings_data:
                            logger.info(f"Sample listing keys: {list(api_listings_data[0].keys())}")
                            
                            # Check for key fields we expect to use
                            if "sellerAllInPrice" in api_listings_data[0]:
                                logger.info(f"Price field example: {api_listings_data[0]['sellerAllInPrice']}")
                            else:
                                logger.warning("Expected price field 'sellerAllInPrice' not found in listing")
                                
                            if "section" in api_listings_data[0]:
                                logger.info(f"Section field example: {api_listings_data[0]['section']}")
                            else:
                                logger.warning("Expected field 'section' not found in listing")
                        
                        # Take screenshot of current page state
                        await save_screenshot(page, f"api_data_received_{event_id}", "api")
                        api_response_received.set()
                    else:
                        logger.warning(f"Unexpected API response format: not a list. Type: {type(json_data)}")
                        # Try to recover - if it's not a list but has key properties, wrap it
                        if isinstance(json_data, dict) and "listings" in json_data:
                            logger.info("Found listings array in a dictionary response")
                            api_listings_data = json_data.get("listings", [])
                            logger.info(f"Extracted {len(api_listings_data)} listings from dict response")
                            api_response_received.set()
                        else:
                            save_api_response(json_data, f"api_response_{event_id}", event_id)
                            logger.error(f"Could not extract listings from non-list response")
                except Exception as e:
                    logger.error(f"Error parsing API response: {str(e)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Check if this is the venue map API response (as a separate if, not elif)
            # Only process venue map data if fetch_venue_map is True
            if fetch_venue_map and "GetVenueMapsByScoreModelForEvent" in response.url and response.status == 200:
                try:
                    logger.info(f"Intercepted venue map response from StubHub Pro API: {response.url}")
                    venue_map_data = await response.json()

                    logger.info(venue_map_data)
                    
                    # Save raw response for debugging
                    try:
                        save_api_response(venue_map_data, f"venue_map_response_{event_id}", event_id)
                        logger.info(f"Saved venue map API response for event {event_id}")
                    except Exception as e:
                        logger.warning(f"Failed to save venue map API response: {str(e)}")
                    
                    venue_map_received.set()
                except Exception as e:
                    logger.error(f"Error parsing venue map API response: {str(e)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Register the response handler
        page.on("response", handle_response)
        
        # Click on StubHub Listings button to trigger the API call
        try:
            # Wait for the StubHub Listings button to be visible 
            await page.wait_for_selector("button:has-text('StubHub Listings')", timeout=10000)
            logger.info("Clicking StubHub Listings button")
            await page.click("button:has-text('StubHub Listings')")
        except Exception as e:
            logger.warning(f"Could not find or click 'StubHub Listings' button: {str(e)}")
            
            # Try alternate approach - just wait for a while to see if API request happens
            logger.info("Waiting for potential API calls to occur...")
        
        # Add some scrolling to trigger any lazy-loading
        await page.evaluate("window.scrollBy(0, 300)")
        
        # Wait for the API response to be received or timeout
        try:
            # Wait up to 25 seconds for the API response - increased timeout for larger datasets
            await asyncio.wait_for(api_response_received.wait(), 25)
            logger.info("API response received successfully")
        except asyncio.TimeoutError:
            logger.warning("Timed out waiting for API response")
            await save_screenshot(page, f"api_timeout_{event_id}", "api")
        
        # Wait for venue map data (but don't fail if we don't get it)
        # Only wait for venue map data if fetch_venue_map is True
        if fetch_venue_map:
            try:
                # Wait a shorter time for venue map data
                await asyncio.wait_for(venue_map_received.wait(), 10)
                logger.info("Venue map data received successfully")
            except asyncio.TimeoutError:
                logger.warning("Timed out waiting for venue map data")
        
        # If we got data from API interception, use it
        if api_listings_data:
            logger.info(f"Returning {len(api_listings_data)} listings from API interception")
            
            # Validate sample of data to ensure it's processable
            if len(api_listings_data) > 0:
                sample = api_listings_data[0]
                logger.info(f"Sample listing validation - Keys present: {list(sample.keys())}")
            
            # Return both listings and venue map data (if requested and available)
            result = {
                "listings": api_listings_data,
            }
            
            # Only include venue map data if it was requested and successfully fetched
            if fetch_venue_map and venue_map_data:
                result["VenueMapsByScoreModel"] = venue_map_data
                
            return result
        
        # If we didn't get data from API interception, log an error
        logger.error(f"Failed to intercept listings data from API for event {event_id}")
        return {
            "listings": [],
            "VenueMapsByScoreModel": venue_map_data if fetch_venue_map else None
        }
    
    except Exception as e:
        logger.error(f"Error fetching listing data for {event_id}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Take a screenshot if possible for debugging
        try:
            await save_screenshot(page, f"fetch_error_{event_id}", "errors")
        except Exception as screenshot_error:
            logger.error(f"Error saving error screenshot: {str(screenshot_error)}")
        
        # Return empty data on error
        return {
            "listings": [],
            "VenueMapsByScoreModel": None
        }


def _process_event_and_listings(event_id: str, event_data: Dict[str, Any], listings_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process and combine event and listing data
    
    Args:
        event_id: StubHub event ID
        event_data: Basic event details (minimal)
        listings_data: Listing data from API interception (list of listing objects)
        
    Returns:
        Combined and processed data
    """
    # Calculate some stats about the listings
    total_listings = len(listings_data.get("listings", []))
    logger.info(f"Processing {total_listings} listings for event {event_id}")
    
    # Initialize price data
    prices = []
    
    # Process listings and extract pricing info
    sections = {}
    
    # Process listings directly (they're already in the right format)
    for listing in listings_data.get("listings", []):
        # Extract price from sellerAllInPrice.amt field (based on sample data structure)
        if "sellerAllInPrice" in listing and "amt" in listing["sellerAllInPrice"]:
            price = listing["sellerAllInPrice"]["amt"]
            if price is not None and price > 0:
                prices.append(price)
        
        # Extract section info for stats
        section = listing.get("section", "Unknown")
        
        # Track section counts for stats
        if section not in sections:
            sections[section] = 0
        sections[section] += 1
    
    # Calculate price stats if we have prices
    if prices:
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        # Handle median calculation
        sorted_prices = sorted(prices)
        median_price = sorted_prices[len(sorted_prices)//2]
    else:
        min_price = max_price = avg_price = median_price = 0
    
    # Extract tracking status from event data if available
    is_tracked = True  # Default to True for backward compatibility
    if event_data and "is_tracked" in event_data:
        is_tracked = bool(event_data["is_tracked"])
    
    # Build the response
    result = {
        "event_id": event_id,
        "listings": listings_data.get("listings", []),  # Return the original listings data
        "stats": {
            "total_listings": total_listings,
            "min_price": round(min_price, 2) if min_price else 0,
            "max_price": round(max_price, 2) if max_price else 0,
            "avg_price": round(avg_price, 2) if avg_price else 0,
            "median_price": round(median_price, 2) if median_price else 0,
            "sections": sections
        },
        "metadata": {
            "source": "stubhub_pro",
            "fetched_at": datetime.now().isoformat(),
            "is_tracked": is_tracked  # Use the extracted value
        },
        "VenueMapsByScoreModel": listings_data.get("VenueMapsByScoreModel")
    }
    
    # Add any additional event data if available
    if event_data:
        for key, value in event_data.items():
            if key not in result:
                result[key] = value
    
    logger.info(f"Successfully processed data for event {event_id}: {total_listings} listings with {len(sections)} sections")
    
    # Make sure all data is serializable before returning
    return _ensure_serializable(result)


async def _extract_event_name(page: Page) -> str:
    """Extract event name from the page"""
    try:
        # Try different selectors that might contain the event name
        selectors = [
            "h1.event-title", 
            ".event-header h1",
            "title"
        ]
        
        for selector in selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=5000)
                if element:
                    return await element.inner_text()
            except:
                continue
                
        # Fallback to page title
        return await page.title()
        
    except Exception as e:
        logger.error(f"Error extracting event name: {str(e)}")
        return "Unknown Event"


async def _extract_event_datetime(page: Page) -> str:
    """Extract event datetime from the page"""
    try:
        # Try different selectors that might contain the date/time
        selectors = [
            ".event-date-time",
            ".event-details time",
            ".event-info .date"
        ]
        
        for selector in selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=5000)
                if element:
                    return await element.inner_text()
            except:
                continue
                
        return "Unknown Date/Time"
        
    except Exception as e:
        logger.error(f"Error extracting event datetime: {str(e)}")
        return "Unknown Date/Time"


async def _extract_venue_info(page: Page) -> Dict[str, str]:
    """Extract venue information from the page"""
    try:
        venue_info = {}
        
        # Try to get venue name
        try:
            venue_name = await page.locator(".event-venue").inner_text()
            venue_info["name"] = venue_name
        except:
            venue_info["name"] = "Unknown Venue"
            
        # Try to get venue location
        try:
            venue_location = await page.locator(".event-location").inner_text()
            venue_info["location"] = venue_location
        except:
            pass
            
        return venue_info
        
    except Exception as e:
        logger.error(f"Error extracting venue info: {str(e)}")
        return {"name": "Unknown Venue"}


async def _extract_listings_from_dom(page: Page) -> List[Dict[str, Any]]:
    """Fallback method to extract listings from the DOM"""
    listings = []
    
    try:
        # Evaluate JavaScript in the page context to extract data
        # This is a more flexible approach when the exact structure is unknown
        listings_data = await page.evaluate("""
            () => {
                const listings = [];
                
                // Look for tables with listing data
                const tables = Array.from(document.querySelectorAll('table'));
                const listingTable = tables.find(table => {
                    // Find the table most likely containing listings
                    return table.textContent.includes('Section') || 
                           table.textContent.includes('Price') ||
                           table.textContent.includes('Qty');
                });
                
                if (listingTable) {
                    // Extract headers to know which column is which
                    const headers = Array.from(listingTable.querySelectorAll('th')).map(th => th.textContent.trim());
                    
                    // Find indexes for important columns
                    const sectionIdx = headers.findIndex(h => h.includes('Section'));
                    const rowIdx = headers.findIndex(h => h.includes('Row'));
                    const seatsIdx = headers.findIndex(h => h.includes('Seat'));
                    const qtyIdx = headers.findIndex(h => h.includes('Qty'));
                    const priceIdx = headers.findIndex(h => h.includes('Price'));
                    
                    // Process each row
                    const rows = Array.from(listingTable.querySelectorAll('tbody tr'));
                    
                    rows.forEach(row => {
                        const cells = Array.from(row.querySelectorAll('td'));
                        if (cells.length > 2) { // Make sure it's a data row
                            const listing = {
                                section: sectionIdx >= 0 ? cells[sectionIdx].textContent.trim() : 'Unknown',
                                row: rowIdx >= 0 ? cells[rowIdx].textContent.trim() : 'Unknown',
                                seats: seatsIdx >= 0 ? cells[seatsIdx].textContent.trim() : '',
                                quantity: qtyIdx >= 0 ? parseInt(cells[qtyIdx].textContent.trim()) || 1 : 1,
                                price: 0
                            };
                            
                            // Parse price
                            if (priceIdx >= 0) {
                                const priceText = cells[priceIdx].textContent.trim();
                                const priceNumber = priceText.replace(/[^0-9.]/g, '');
                                listing.price = parseFloat(priceNumber) || 0;
                            }
                            
                            listings.push(listing);
                        }
                    });
                }
                
                return listings;
            }
        """)
        
        for item in listings_data:
            item["fetched_at"] = datetime.now().isoformat()
            listings.append(item)
            
        return listings
        
    except Exception as e:
        logger.error(f"Error extracting listings from DOM: {str(e)}")
        return []
