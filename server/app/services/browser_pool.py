"""
Browser Pool service for managing browser instances
"""
from playwright.async_api import async_playwright, BrowserContext, Browser
import asyncio
from typing import Dict, List, Optional, Any
from loguru import logger
import random
import time
from datetime import datetime, timedelta
import json
import os
import uuid

from app.config import settings
from app.utils.stealth import setup_stealth_browser
from app.utils.debug import save_screenshot

# Global singleton instance
_browser_pool = None

class BrowserSession:
    """Represents a single browser session"""
    def __init__(self, browser, context, id: str):
        self.browser = browser
        self.context = context
        self.id = id
        self.created_at = datetime.now()
        self.last_used = datetime.now()
        self.request_count = 0
        self.in_use = False
        self.logged_in = False
        self._is_alive = True  # Track if the session is alive
        
    @property
    def is_alive(self) -> bool:
        """Check if the session is still alive and usable"""
        return self._is_alive
        
    async def close(self):
        """Close the browser session"""
        try:
            self._is_alive = False  # Mark as not alive before closing
            await self.context.close()
            await self.browser.close()
        except Exception as e:
            logger.error(f"Error closing browser session {self.id}: {str(e)}")
            self._is_alive = False  # Ensure it's marked as not alive even if there's an error
            
    async def ensure_login(self, page=None) -> bool:
        """Ensure the browser is logged into StubHub Pro"""
        if self.logged_in:
            # Check if still logged in by verifying cookies or other methods
            return True
            
        try:
            logger.info(f"Logging into StubHub Pro with session {self.id}")
            if page is None:
                page = await self.context.new_page()
            
            # Navigate to StubHub login page
            await page.goto("https://pro.stubhub.com/login", timeout=settings.BROWSER_TIMEOUT_SECONDS * 1000)
            
            # Take screenshot for debugging
            await save_screenshot(page, f"login_start_{self.id}.png")
            
            # Wait for login form and check if we're already logged in
            try:
                # First check if we're already logged in (redirected to home)
                if page.url.startswith("https://pro.stubhub.com/home"):
                    logger.info(f"Already logged in with session {self.id}")
                    self.logged_in = True
                    if page is not None:
                        await page.close()
                    return True
                
                # Wait for email input field
                logger.info(f"Looking for email input field on {page.url}")
                await page.wait_for_selector("input[id='Login_UserName']", timeout=10000)
                
                # Enter email
                await page.fill("input[id='Login_UserName']", settings.STUBHUB_USERNAME)
                await save_screenshot(page, f"login_email_{self.id}.png")

                # Submit email and wait for password field
                logger.info("Submitting email address")
                
                # Wait for password field
                logger.info("Waiting for password field")
                await page.wait_for_selector("input[id='Login_Password']", timeout=10000)
                await page.fill("input[id='Login_Password']", settings.STUBHUB_PASSWORD)
                await save_screenshot(page, f"login_password_{self.id}.png")
                
                # Submit login
                logger.info("Submitting password")
                await page.click("input[id='sbmt']")
                
                # Multiple possible success indicators
                try:
                    # Try to detect successful login with a more flexible approach
                    await asyncio.sleep(2)  # Brief pause to allow navigation to start
                    
                    # Wait for a reasonable time for navigation to complete
                    try:
                        await page.wait_for_load_state("networkidle", timeout=30000)
                    except:
                        logger.warning("Network didn't reach idle state, continuing anyway")
                    
                    # Take a screenshot of where we ended up
                    await save_screenshot(page, f"login_success_{self.id}.png")
                    
                    # Check if we're on the home page or any other success indicator
                    current_url = page.url
                    
                    if (current_url.startswith("https://account.stubhub.com/home") or 
                        current_url.startswith("https://www.stubhub.com") or
                        current_url.startswith("https://pro.stubhub.com")):
                        logger.info(f"Successfully logged in, redirected to: {current_url}")
                        self.logged_in = True
                        if page is not None:
                            await page.close()
                        return True
                    else:
                        logger.error(f"Login might have failed, unexpected URL: {current_url}")
                        if page is not None:
                            await page.close()
                        return False
                except Exception as e:
                    logger.error(f"Login post-submit issue: {str(e)}")
                    await save_screenshot(page, f"login_error_redirect_{self.id}.png")
                    
                    # Check if we're on the home page or any other success indicator
                    if (page.url.startswith("https://account.stubhub.com/home") or 
                        page.url.startswith("https://www.stubhub.com") or
                        page.url.startswith("https://pro.stubhub.com")):
                        logger.info(f"Detected successful login by URL: {page.url}")
                        self.logged_in = True
                        if page is not None:
                            await page.close()
                        return True
                        
                    # Failed login
                    if page is not None:
                        await page.close()
                    return False
                    
            except Exception as e:
                logger.error(f"Login process issue: {str(e)}")
                await save_screenshot(page, f"login_error_process_{self.id}.png")
                if page is not None:
                    await page.close()
                return False
                
        except Exception as e:
            logger.error(f"Failed to login to StubHub: {str(e)}")
            try:
                await save_screenshot(page, f"login_error_general_{self.id}.png")
                if page is not None:
                    await page.close()
            except:
                pass
            return False


    def is_expired(self, max_requests: int, max_age_hours: int = 12) -> bool:
        """Check if the session should be recycled"""
        if self.request_count >= max_requests:
            return True
            
        if datetime.now() - self.created_at > timedelta(hours=max_age_hours):
            return True
            
        return False
        
    def update_usage(self):
        """Update session usage statistics"""
        self.last_used = datetime.now()
        self.request_count += 1
        
class BrowserPool:
    """Manages a pool of browser instances for parallel processing"""
    def __init__(self, max_browsers: int = settings.MAX_BROWSER_INSTANCES):
        self.max_browsers = max_browsers
        self.sessions: Dict[str, BrowserSession] = {}
        self.lock = asyncio.Lock()
        self.playwright = None
        self.initialized = False
        self.session_creation_failures = 0
        self.total_requests_handled = 0
        
    @property
    def total_browsers(self) -> int:
        """Get total number of browser sessions"""
        return len(self.sessions)
        
    @property
    def available_browsers(self) -> int:
        """Get number of available browser sessions"""
        return sum(1 for session in self.sessions.values() if not session.in_use)
        
    @property
    def active_sessions(self) -> int:
        """Get number of active browser sessions"""
        return sum(1 for session in self.sessions.values() if session.in_use)
    
    async def initialize(self):
        """Initialize the browser pool"""
        async with self.lock:
            if self.initialized:
                return
                
            try:
                logger.info("Initializing browser pool")
                self.playwright = await async_playwright().start()
                self.initialized = True
                
                # Pre-create at least one browser session
                session = await self._create_new_session()
                if session:
                    # Attempt to login with this session
                    await session.ensure_login()
                
            except Exception as e:
                logger.error(f"Failed to initialize browser pool: {str(e)}")
                if self.playwright:
                    await self.playwright.stop()
                raise
    
    async def get_session(self) -> Optional[BrowserSession]:
        """
        Get an available browser session or create a new one
        Prioritizes reusing existing sessions to maintain login state
        """
        if not self.initialized:
            await self.initialize()
            
        async with self.lock:
            self.total_requests_handled += 1
            
            # First, try to find an existing non-in-use session
            for session in list(self.sessions.values()):
                if not session.in_use and session.is_alive:
                    logger.info(f"Reusing existing session {session.id}")
                    session.in_use = True
                    session.update_usage()  # Update the usage statistics
                    
                    # Check for login status - if session exists it should still be logged in
                    # but we'll confirm without forcing a new login
                    if not session.logged_in:
                        logger.info(f"Session {session.id} may have lost login state, verifying...")
                        try:
                            # Create a new page to check login status without changing existing pages
                            test_page = await session.context.new_page()
                            await test_page.goto("https://pro.stubhub.com", timeout=5000)
                            
                            # If we're redirected to login, we need to log in again
                            if "account.stubhub.com/login" in test_page.url:
                                logger.info(f"Session {session.id} needs to re-authenticate")
                                await session.ensure_login(test_page)
                            else:
                                logger.info(f"Session {session.id} is still authenticated")
                                session.logged_in = True
                                
                            # Close the test page
                            await test_page.close()
                        except Exception as e:
                            logger.warning(f"Error checking login status: {str(e)}")
                            # Continue anyway, we'll handle login issues during the actual request
                    
                    # Periodically save the storage state to ensure persistence
                    asyncio.create_task(self._save_storage(session.context, f"browser_data/{session.id}"))
                    
                    return session
        
            # If no available session exists and we haven't reached max, create a new one
            if len(self.sessions) < self.max_browsers:
                logger.info(f"Creating new session (total: {len(self.sessions)})")
                session = await self._create_new_session()
                
                if session:
                    session.in_use = True
                    session.update_usage()  # Update the usage statistics
                    
                    # Ensure the session is logged in to StubHub
                    await session.ensure_login()
                    
                    return session
                    
            # All sessions are in use, we need to wait
            logger.warning("All browser sessions in use, waiting for one to become available")
            for i in range(30):  # Wait up to 30 seconds
                await asyncio.sleep(1)
                for session in list(self.sessions.values()):
                    if not session.in_use and session.is_alive:
                        logger.info(f"Session {session.id} became available")
                        session.in_use = True
                        session.update_usage()  # Update the usage statistics
                        
                        # Quick check to ensure login state is maintained
                        if not session.logged_in:
                            await session.ensure_login()
                        
                        return session
                        
            # If we got here, we timed out waiting
            logger.error("Timed out waiting for an available browser session")
            return None
        
    async def release_session(self, session_id: str) -> bool:
        """Release a browser session back to the pool"""
        async with self.lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.in_use = False
                logger.info(f"Released session {session_id} back to pool")
                
                # Save storage state to maintain login cookies etc.
                await self._save_storage(session.context, f"browser_data/{session_id}")
                
                return True
            return False

    async def _create_new_session(self) -> Optional[BrowserSession]:
        """Create a new browser session"""
        try:
            # Create a unique ID for the session
            session_id = f"session_{uuid.uuid4().hex[:8]}"
            
            # Create user data directory for persistent storage
            user_data_dir = f"browser_data/{session_id}"
            os.makedirs(user_data_dir, exist_ok=True)
            
            # Launch browser with persistent storage
            browser_args = {
                "headless": settings.BROWSER_HEADLESS,
                "slow_mo": 50
            }
            
            # Add proxy if configured
            if settings.PROXY_URL:
                logger.info(f"Using proxy: {settings.PROXY_URL}")

                # From this format: http://ggFpDGhEtc:3JbtLBMgeA@142.173.179.233:5998 we want to extract
                # http://142.173.179.233:5998, ggFpDGhEtc, 3JbtLBMgeA

                try:
                    auth, proxy_url = settings.PROXY_URL.split("://")[1].split("@")
                    username, password = auth.split(":")
                except ValueError:
                    logger.error("Failed to parse proxy URL - please check the format")
                    return None

                browser_args["proxy"] = {
                    "server": f"http://{proxy_url}",
                    "username": username,
                    "password": password
                }
            
            browser = await self.playwright.chromium.launch(**browser_args)
            
            # Create browser context with persistent storage
            context = await browser.new_context(
                storage_state=f"{user_data_dir}/storage.json" if os.path.exists(f"{user_data_dir}/storage.json") else None,
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            
            # Apply stealth settings to avoid detection
            await setup_stealth_browser(context)
            
            # Create the session object
            session = BrowserSession(browser, context, session_id)
            
            # Set up storage persistence
            context.on("close", lambda: asyncio.ensure_future(self._save_storage(context, user_data_dir)))
            
            # Store session
            self.sessions[session_id] = session
            logger.info(f"Created new browser session {session_id}")
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to create browser session: {str(e)}")
            self.session_creation_failures += 1
            return None

    async def _save_storage(self, context: BrowserContext, user_data_dir: str):
        """Save browser storage for persistence between sessions"""
        try:
            storage = await context.storage_state()
            os.makedirs(user_data_dir, exist_ok=True)
            with open(f"{user_data_dir}/storage.json", 'w') as f:
                json.dump(storage, f)
            logger.debug(f"Saved browser storage to {user_data_dir}/storage.json")
        except Exception as e:
            logger.error(f"Failed to save browser storage: {str(e)}")
            
    async def close_all(self):
        """Close all browser sessions"""
        async with self.lock:
            logger.info(f"Closing {len(self.sessions)} browser sessions")
            close_tasks = []
            
            for session in self.sessions.values():
                close_tasks.append(session.close())
                
            if close_tasks:
                await asyncio.gather(*close_tasks)
                
            self.sessions = {}
            
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
                
            self.initialized = False


# Singleton pattern for browser pool
async def get_browser_pool() -> BrowserPool:
    """Get the global browser pool instance"""
    global _browser_pool
    if _browser_pool is None:
        _browser_pool = BrowserPool()
        await _browser_pool.initialize()
    return _browser_pool
