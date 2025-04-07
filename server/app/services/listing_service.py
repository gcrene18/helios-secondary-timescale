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
from app.utils.stealth import perform_human_like_actions, add_random_delay, get_random_user_agent
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
        try:
            session = await browser_pool.get_session()
            if not session:
                logger.error(f"Failed to get browser session for event {event_id}")
                # Return a minimal response with error information
                return {
                    "event_id": event_id,
                    "event_name": event_data.get("name", "Unknown") if event_data else "Unknown",
                    "listings": [],
                    "stats": {"count": 0, "error": "Browser session unavailable"},
                    "metadata": {"error": "Browser pool exhausted", "timestamp": datetime.now().isoformat()}
                }
        except Exception as session_error:
            logger.error(f"Error getting browser session for event {event_id}: {str(session_error)}")
            # Return a minimal response with error information
            return {
                "event_id": event_id,
                "event_name": event_data.get("name", "Unknown") if event_data else "Unknown",
                "listings": [],
                "stats": {"count": 0, "error": str(session_error)},
                "metadata": {"error": "Browser session error", "timestamp": datetime.now().isoformat()}
            }
            
        # Create a new page in the browser
        page = await session.context.new_page()
        
        # Set viewport size to a common desktop resolution
        await page.set_viewport_size({"width": 1280, "height": 800})
        
        # Wait a bit before starting (like a human would)
        await add_random_delay(800, 2500)
        
        # Log the request
        logger.info(f"Fetching listings for event {event_id} using session {session.id}")
        
        # Occasionally introduce a "mistake" - navigate to the homepage first
        if random.random() < 0.3:  # 30% chance
            logger.debug("Mimicking human navigation pattern: visiting home page first")
            await page.goto("https://pro.stubhub.com/", timeout=settings.BROWSER_TIMEOUT_SECONDS * 1000)
            # Perform some actions like a human would on the homepage
            await perform_human_like_actions(page, action_count=random.randint(2, 4))
            await add_random_delay(1200, 3000)
        
        # Navigate to the event page
        event_data = await _fetch_event_data(page, event_id)
        
        # Use the interceptor to get listings
        logger.info(f"Fetching listings data for event {event_id}")
        
        # Random "thinking" delay before fetching listing data
        thinking_delay = random.randint(1500, 4000)
        logger.debug(f"User thinking delay: {thinking_delay}ms")
        await add_random_delay(thinking_delay // 2, thinking_delay)
        
        listings_data = await _fetch_listing_data(page, event_id, fetch_venue_map)
        
        # Before closing the page, do some more human-like actions
        # as if analyzing the data we just received
        await perform_human_like_actions(page, action_count=random.randint(2, 5))
        
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
        
        # Simplify the URL typing feature to be more reliable
        navigation_success = False
        max_retries = 3
        retry_count = 0
        
        while not navigation_success and retry_count < max_retries:
            try:
                # Sometimes type the URL with varying speeds but in a more reliable way
                if random.random() < 0.2 and retry_count == 0:  # Reduced to 20% chance and only on first try
                    logger.debug("Using manual URL entry navigation method")
                    # Go to StubHub Pro homepage first
                    await page.goto("https://pro.stubhub.com/", timeout=settings.BROWSER_TIMEOUT_SECONDS * 1000)
                    await add_random_delay(500, 1500)
                    
                    # Now navigate to the event page by clicking in address bar and typing
                    await page.keyboard.press("F6")  # Focus address bar
                    await add_random_delay(200, 500)
                    await page.keyboard.press("Control+A")  # Select all
                    await add_random_delay(100, 300)
                    
                    # Type the full URL at once with varying speeds between characters
                    await page.keyboard.type(pro_event_url, delay=random.randint(30, 100))
                    await add_random_delay(300, 800)
                    await page.keyboard.press("Enter")
                else:
                    # Normal direct navigation
                    logger.debug("Using standard navigation method")
                    await page.goto(pro_event_url, timeout=settings.BROWSER_TIMEOUT_SECONDS * 1000)
                
                # Wait for page to load completely
                await page.wait_for_load_state("networkidle", timeout=10000)
                
                # IMPORTANT: Verify we're actually on the correct page
                current_url = page.url
                logger.info(f"Current page URL after navigation: {current_url}")
                
                # Check if we're on about:blank or another unexpected page
                if current_url == "about:blank" or "error" in current_url.lower():
                    logger.warning(f"Navigation resulted in unexpected URL: {current_url}, retrying...")
                    retry_count += 1
                    await add_random_delay(1000, 2000)
                    continue
                
                # Verify we're on the event page by checking for expected elements
                event_page_indicators = [
                    "text=Event Details", 
                    ".event-header", 
                    "[data-testid=event-title]",
                    "text=StubHub Listings"
                ]
                
                for indicator in event_page_indicators:
                    if await page.locator(indicator).count() > 0:
                        logger.info(f"Found event page indicator: {indicator}")
                        navigation_success = True
                        break
                
                if not navigation_success:
                    screenshot_path = f"event_page_verification_{event_id}_{retry_count}.png"
                    await save_screenshot(page, screenshot_path)
                    logger.warning(f"Could not verify event page loaded properly. See {screenshot_path}")
                    retry_count += 1
                    await add_random_delay(1000, 2000)
                
            except Exception as nav_error:
                logger.warning(f"Navigation attempt {retry_count+1} failed: {str(nav_error)}")
                retry_count += 1
                if retry_count < max_retries:
                    logger.info(f"Retrying navigation ({retry_count}/{max_retries})...")
                    await add_random_delay(1000, 3000)
        
        if not navigation_success:
            logger.error(f"Failed to navigate to event page after {max_retries} attempts")
            raise Exception(f"Failed to navigate to event page for {event_id} after multiple attempts")
        
        # More complex random delay pattern
        delay_options = [
            (settings.MIN_PAGE_DELAY_MS, settings.MAX_PAGE_DELAY_MS),  # Normal delay
            (settings.MIN_PAGE_DELAY_MS * 2, settings.MAX_PAGE_DELAY_MS * 2),  # Longer delay
            (500, 1200)  # Short delay
        ]
        delay_choice = random.choices(
            delay_options, 
            weights=[0.6, 0.3, 0.1]  # 60% normal, 30% longer, 10% shorter
        )[0]
        await add_random_delay(delay_choice[0], delay_choice[1])
        
        # Check if we need to log in
        if await page.locator("text=Sign In").count() > 0 or page.url.startswith("https://account.stubhub.com/login"):
            logger.warning("Login required but should have been handled by session management")
            # The browser_pool's ensure_login should have already handled this
            await save_screenshot(page, f"login_needed_{event_id}.png")
            raise Exception("Login required but session should already be authenticated")
        
        # Perform human-like actions - scrolling, moving mouse, etc.
        await perform_human_like_actions(page, action_count=random.randint(3, 6))
        
        # Save a screenshot for debugging/verification
        await save_screenshot(page, f"event_page_{event_id}.png")
        
        # Return minimal event data - we'll get details from the API response
        event_data = {
            "event_id": event_id,
            "source": "stubhub_pro",
            "fetched_at": datetime.now().isoformat(),
            "page_url": page.url,  # Include the actual page URL for verification
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
                        
                        # Signal that we have received the response
                        api_response_received.set()
                    else:
                        logger.warning(f"Unexpected API response format: {type(json_data)}")
                except Exception as e:
                    logger.error(f"Error processing API response: {str(e)}")
            
            # Check if this is the venue map endpoint
            elif fetch_venue_map and "GetVenueMapsByScoreModelForEvent" in response.url and response.status == 200:
                try:
                    logger.info(f"Intercepted venue map data from StubHub Pro API: {response.url}")
                    json_data = await response.json()
                    
                    # Save raw response for debugging
                    try:
                        save_api_response(json_data, f"api_venue_map_{event_id}", event_id)
                        logger.info(f"Saved venue map data to api_venue_map_{event_id}.json")
                    except Exception as e:
                        logger.warning(f"Failed to save venue map data: {str(e)}")
                    
                    venue_map_data = json_data
                    venue_map_received.set()
                except Exception as e:
                    logger.error(f"Error processing venue map response: {str(e)}")
        
        # Set up the response handler
        page.on("response", handle_response)
        
        # Now trigger the API call by clicking on the refresh button
        # First, do some random human-like behavior
        # Occasionally make a "mistake" - click on irrelevant elements first
        if random.random() < 0.25:  # 25% chance
            logger.debug("Simulating human behavior: clicking on non-target elements first")
            selectors_to_try = [
                ".event-header", ".event-details", "h1", ".venue-name", 
                ".breadcrumbs", ".event-date", ".ticket-count"
            ]
            for _ in range(random.randint(1, 2)):
                try:
                    # Pick a random selector
                    selector = random.choice(selectors_to_try)
                    logger.debug(f"Trying to click on selector: {selector}")
                    
                    # Try to find and click the element
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.click()
                        await add_random_delay(400, 1200)
                except Exception as e:
                    logger.debug(f"Failed to click random element: {str(e)}")
        
        # Perform human-like mouse movements
        await perform_human_like_actions(page, action_count=random.randint(2, 4))
        
        # Take a screenshot before looking for elements
        await save_screenshot(page, f"before_refresh_button_{event_id}.png")
        
        # List of potential refresh button selectors to try
        refresh_button_selectors = [
            '[data-testid="refresh-button"]',
            'button:has-text("Refresh")',
            '.refresh-button',
            '[aria-label="Refresh"]',
            'button:has-text("Update")',
            '.update-button',
            '.listings-refresh-button',
            '.refresh-icon',
            'button.MuiButtonBase-root:has([data-testid="RefreshIcon"])'
        ]
        
        # Try to find the refresh button using multiple methods
        logger.info("Looking for refresh button to trigger API call")
        
        # Method 1: Try all selectors
        refresh_button = None
        
        for selector in refresh_button_selectors:
            try:
                logger.debug(f"Trying to find refresh button with selector: {selector}")
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    logger.info(f"Found refresh button with selector: {selector}")
                    refresh_button = element
                    break
            except Exception as e:
                logger.debug(f"Error finding refresh button with selector {selector}: {str(e)}")
        
        # Method 2: Try to find by text content if selector method failed
        if not refresh_button:
            try:
                logger.debug("Trying to find refresh button by text content")
                # Look for buttons with refresh-related text
                for text in ["Refresh", "Update", "Load"]:
                    button = await page.query_selector(f'button:has-text("{text}")')
                    if button and await button.is_visible():
                        logger.info(f"Found refresh button with text: {text}")
                        refresh_button = button
                        break
            except Exception as e:
                logger.debug(f"Error finding refresh button by text: {str(e)}")
        
        # Method 3: Try to look for the listings tab first
        if not refresh_button:
            try:
                logger.info("Trying to click on 'Listings' tab first")
                listings_tab_selectors = [
                    'button:has-text("Listings")',
                    '[data-testid="listings-tab"]',
                    '.listings-tab',
                    'div[role="tab"]:has-text("Listings")'
                ]
                
                for selector in listings_tab_selectors:
                    tab = await page.query_selector(selector)
                    if tab and await tab.is_visible():
                        logger.info(f"Found listings tab with selector: {selector}")
                        await tab.click()
                        await add_random_delay(1000, 2000)
                        
                        # Now try again to find the refresh button
                        for selector in refresh_button_selectors:
                            element = await page.query_selector(selector)
                            if element and await element.is_visible():
                                logger.info(f"Found refresh button after clicking listings tab: {selector}")
                                refresh_button = element
                                break
                        
                        if refresh_button:
                            break
            except Exception as e:
                logger.debug(f"Error handling listings tab: {str(e)}")
        
        # Fallback approach if we still can't find the refresh button
        if not refresh_button:
            logger.warning("Could not find refresh button using selectors, trying fallback")
            
            # Take a screenshot for debugging
            await save_screenshot(page, f"refresh_button_not_found_{event_id}.png")
            
            # Log all button elements on the page for debugging
            buttons = await page.query_selector_all("button")
            logger.info(f"Found {len(buttons)} button elements on the page")
            
            for i, button in enumerate(buttons[:10]):  # Log first 10 buttons
                try:
                    text = await button.text_content()
                    logger.info(f"Button {i}: '{text}'")
                except:
                    logger.info(f"Button {i}: <no text>")
            
            # Try clicking a button that might be the refresh button (first visible button)
            for button in buttons:
                if await button.is_visible():
                    logger.info("Trying to click first visible button as fallback")
                    refresh_button = button
                    break
        
        # Trigger API call if we found a button to click
        if refresh_button:
            logger.info("Refresh button found, clicking to trigger API call")
            
            # Sometimes hover first before clicking (more human-like)
            if random.random() < 0.7:  # 70% chance to hover first
                await refresh_button.hover()
                await add_random_delay(300, 800)
            
            # Click the button
            await refresh_button.click()
            logger.info("Clicked refresh button")
            
            # Wait for the API response with a reasonable timeout
            timeout = settings.BROWSER_TIMEOUT_SECONDS
            try:
                # Add randomness to timeout to appear more human-like
                randomized_timeout = timeout * (0.9 + random.random() * 0.2)  # +/- 10%
                logger.info(f"Waiting for API response with timeout of {randomized_timeout:.1f}s")
                
                # Wait for the API response
                await asyncio.wait_for(api_response_received.wait(), randomized_timeout)
                logger.info("API response received")
                
                # If we're also fetching venue map, wait for that too
                if fetch_venue_map:
                    logger.info("Waiting for venue map data")
                    try:
                        await asyncio.wait_for(venue_map_received.wait(), randomized_timeout / 2)
                        logger.info("Venue map data received")
                    except asyncio.TimeoutError:
                        logger.warning("Timeout waiting for venue map data, continuing without it")
                
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for API response")
                
                # Try to manually trigger the API call by navigating to the event page again
                logger.info("Trying to manually trigger API call by renavigating to event page")
                try:
                    await page.goto(f"https://pro.stubhub.com/inventory/event?eventId={event_id}",
                                   timeout=settings.BROWSER_TIMEOUT_SECONDS * 1000)
                    
                    # Wait a bit longer for any API calls to be triggered
                    await add_random_delay(5000, 8000)
                    
                    # Check if we've received data during this time
                    if not api_listings_data:
                        # Try to extract listings from the DOM as last resort
                        logger.info("API interception failed, attempting to extract listings from DOM")
                        dom_listings = await _extract_listings_from_dom(page)
                        if dom_listings:
                            logger.info(f"Extracted {len(dom_listings)} listings from DOM")
                            api_listings_data = dom_listings
                        else:
                            logger.warning("Failed to extract listings from DOM")
                except Exception as e:
                    logger.error(f"Error during manual API trigger attempt: {str(e)}")
        else:
            logger.error("Could not find refresh button, cannot trigger API call")
            await save_screenshot(page, f"page_without_refresh_button_{event_id}.png")
            
            # Try one last approach - navigate to the API endpoint directly
            try:
                logger.info("Attempting direct API navigation as fallback")
                api_url = f"https://pro.stubhub.com/api/events/{event_id}/listings"
                
                # Create a new page for this request to avoid disturbing the main page
                context = page.context
                api_page = await context.new_page()
                
                # Navigate to the API URL
                await api_page.goto(api_url, timeout=settings.BROWSER_TIMEOUT_SECONDS * 1000)
                
                # Check if we got any data
                try:
                    content = await api_page.content()
                    if "data" in content or "listings" in content:
                        logger.info("Direct API navigation returned potential data")
                        json_text = await api_page.text_content("pre")
                        try:
                            json_data = json.loads(json_text)
                            if isinstance(json_data, dict) and "listings" in json_data:
                                api_listings_data = json_data["listings"]
                                logger.info(f"Found {len(api_listings_data)} listings via direct API navigation")
                            elif isinstance(json_data, list):
                                api_listings_data = json_data
                                logger.info(f"Found {len(api_listings_data)} listings via direct API navigation")
                        except:
                            logger.warning("Failed to parse JSON from direct API navigation")
                except:
                    logger.warning("Failed to extract content from direct API navigation")
                
                # Close the API page
                await api_page.close()
            except Exception as direct_api_error:
                logger.error(f"Direct API navigation failed: {str(direct_api_error)}")
        
        # Log final results
        if api_listings_data:
            logger.info(f"Successfully fetched {len(api_listings_data)} listings")
        else:
            logger.warning("No listings data found after all attempts")
        
        # Construct the result
        result = {
            "listings": api_listings_data,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Add venue map data if available
        if venue_map_data:
            result["VenueMapsByScoreModel"] = venue_map_data
            
        return result
        
    except Exception as e:
        logger.error(f"Error fetching listing data: {str(e)}")
        traceback.print_exc()
        raise


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
