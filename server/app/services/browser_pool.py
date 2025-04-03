"""
Browser Pool service for managing browser instances
"""
from playwright.async_api import async_playwright
import asyncio
from typing import Dict, List, Optional, Any
from loguru import logger
import random
import time
from datetime import datetime, timedelta
import json

from app.config import settings
from app.utils.stealth import setup_stealth_browser

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
        
    async def close(self):
        """Close the browser session"""
        try:
            await self.context.close()
            await self.browser.close()
        except Exception as e:
            logger.error(f"Error closing browser session {self.id}: {str(e)}")
            
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
        if self.initialized:
            return
            
        try:
            self.playwright = await async_playwright().start()
            logger.info(f"Initializing browser pool with max {self.max_browsers} instances")
            self.initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize browser pool: {str(e)}")
            raise
    
    async def get_session(self) -> BrowserSession:
        """Get an available browser session or create a new one"""
        if not self.initialized:
            await self.initialize()
            
        async with self.lock:
            # First try to find an available session
            for session_id, session in self.sessions.items():
                if not session.in_use:
                    # Check if session needs recycling
                    if session.is_expired(settings.MAX_REQUESTS_PER_SESSION):
                        logger.info(f"Recycling expired session {session_id}")
                        await session.close()
                        del self.sessions[session_id]
                    else:
                        # Use this session
                        session.in_use = True
                        return session
            
            # No available sessions, create a new one if under max limit
            if len(self.sessions) < self.max_browsers:
                try:
                    new_session = await self._create_new_session()
                    new_session.in_use = True
                    return new_session
                except Exception as e:
                    self.session_creation_failures += 1
                    logger.error(f"Failed to create new browser session: {str(e)}")
                    raise
            
            # All sessions in use and at max limit
            logger.warning("All browser sessions in use, waiting for one to become available")
            raise RuntimeError("All browser sessions in use")
            
    async def release_session(self, session_id: str):
        """Release a browser session back to the pool"""
        async with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id].in_use = False
                self.sessions[session_id].update_usage()
                self.total_requests_handled += 1
                logger.debug(f"Released session {session_id} back to pool")
            else:
                logger.warning(f"Attempted to release unknown session {session_id}")
    
    async def _create_new_session(self) -> BrowserSession:
        """Create a new browser session"""
        try:
            # Create a new browser instance
            browser = await self.playwright.chromium.launch(
                headless=settings.BROWSER_HEADLESS
            )
            
            # Create a new browser context
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
            )
            
            # Apply stealth techniques
            await setup_stealth_browser(context)
            
            # Generate a unique session ID
            session_id = f"session_{len(self.sessions) + 1}_{int(time.time())}"
            
            # Create and store the session
            session = BrowserSession(browser, context, session_id)
            self.sessions[session_id] = session
            
            logger.info(f"Created new browser session: {session_id}")
            return session
            
        except Exception as e:
            logger.error(f"Error creating browser session: {str(e)}")
            self.session_creation_failures += 1
            raise
    
    async def close_all(self):
        """Close all browser sessions"""
        async with self.lock:
            for session_id, session in list(self.sessions.items()):
                logger.info(f"Closing browser session {session_id}")
                await session.close()
                
            self.sessions.clear()
            
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
                
            self.initialized = False
            logger.info("All browser sessions closed")


# Singleton pattern for browser pool
def get_browser_pool() -> BrowserPool:
    """Get the global browser pool instance"""
    global _browser_pool
    if _browser_pool is None:
        _browser_pool = BrowserPool(max_browsers=settings.MAX_BROWSER_INSTANCES)
    return _browser_pool
