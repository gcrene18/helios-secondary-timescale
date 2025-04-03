"""
Stealth utilities to mimic human-like browsing behavior
"""
from playwright.async_api import BrowserContext, Page
import asyncio
import random
from loguru import logger
from typing import List, Tuple
import time


async def setup_stealth_browser(context: BrowserContext):
    """
    Configure a browser context with stealth settings to avoid detection
    
    Args:
        context: Playwright browser context
    """
    # Apply stealth script to mask browser automation
    await context.add_init_script("""
    // Overwrite the languages property to use a popular language
    Object.defineProperty(navigator, 'languages', {
        get: function() {
            return ['en-US', 'en'];
        },
    });
    
    // Overwrite permissions
    Object.defineProperty(navigator, 'permissions', {
        get: function() {
            return {
                query: function() {
                    return Promise.resolve({ state: 'granted' });
                }
            };
        },
    });
    
    // Prevent detection via webdriver-related properties
    delete Object.getPrototypeOf(navigator).webdriver;
    
    // Fake chrome.runtime for anti-bot checks
    window.chrome = {
        runtime: {}
    };
    
    // Hide that we're automating
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
    );
    """)
    
    logger.debug("Applied stealth settings to browser context")


async def add_random_delay(min_ms: int = 1000, max_ms: int = 5000):
    """
    Add a random delay to mimic human timing
    
    Args:
        min_ms: Minimum delay in milliseconds
        max_ms: Maximum delay in milliseconds
    """
    delay_ms = random.randint(min_ms, max_ms)
    await asyncio.sleep(delay_ms / 1000)  # Convert to seconds


async def perform_human_like_actions(page: Page, action_count: int = None):
    """
    Perform random human-like actions on the page to avoid detection
    
    Args:
        page: Playwright page object
        action_count: Number of random actions to perform (default: random 1-3)
    """
    if action_count is None:
        action_count = random.randint(1, 3)
        
    viewport_size = await page.evaluate("""
        () => {
            return {
                width: window.innerWidth,
                height: window.innerHeight
            }
        }
    """)
    
    width = viewport_size['width']
    height = viewport_size['height']
    
    for _ in range(action_count):
        action_type = random.choice([
            'scroll',
            'mouse_move',
            'hover_element',
            'pause'
        ])
        
        if action_type == 'scroll':
            # Random scroll
            scroll_y = random.randint(100, 800)
            await page.evaluate(f"window.scrollBy(0, {scroll_y})")
            await add_random_delay(500, 2000)
            
        elif action_type == 'mouse_move':
            # Random mouse movement
            x = random.randint(0, width)
            y = random.randint(0, height)
            await page.mouse.move(x, y)
            await add_random_delay(300, 1000)
            
        elif action_type == 'hover_element':
            # Try to hover over a random link or button
            elements = await get_random_interactive_elements(page)
            if elements:
                element = random.choice(elements)
                try:
                    await element.hover()
                    await add_random_delay(500, 2000)
                except Exception:
                    # If hovering fails, just pause
                    await add_random_delay(500, 1500)
                    
        elif action_type == 'pause':
            # Just pause
            await add_random_delay(1000, 3000)
    
    logger.debug(f"Performed {action_count} human-like actions")


async def get_random_interactive_elements(page: Page) -> List:
    """
    Get a list of random interactive elements from the page
    
    Args:
        page: Playwright page object
        
    Returns:
        List of element handles
    """
    # Find all links and buttons
    selectors = [
        'a', 
        'button', 
        '[role="button"]', 
        '.btn', 
        '[tabindex="0"]'
    ]
    
    elements = []
    for selector in selectors:
        try:
            # Try to find elements with this selector
            selector_elements = await page.query_selector_all(selector)
            elements.extend(selector_elements)
        except Exception:
            continue
    
    # Get only visible elements
    visible_elements = []
    for element in elements:
        try:
            is_visible = await element.is_visible()
            if is_visible:
                visible_elements.append(element)
        except Exception:
            continue
            
    # Limit to a smaller subset to avoid too many elements
    if len(visible_elements) > 10:
        visible_elements = random.sample(visible_elements, 10)
        
    return visible_elements


def get_random_user_agent() -> str:
    """
    Get a random user agent string to mimic different browsers
    
    Returns:
        User agent string
    """
    user_agents = [
        # Chrome
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
        
        # Firefox
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:95.0) Gecko/20100101 Firefox/95.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:95.0) Gecko/20100101 Firefox/95.0",
        
        # Safari
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
        
        # Edge
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36 Edg/96.0.1054.62"
    ]
    
    return random.choice(user_agents)
