"""
StubHub API client for fetching ticket listings.
"""
from typing import List, Dict, Any, Optional
import aiohttp
import asyncio
import json
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import random

from ..core.logging import get_logger, console
from ..config.settings import settings
from ..domain.listing import Listing
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

logger = get_logger(__name__)

class StubHubClient:
    """
    Client for interacting with the StubHub API.
    
    This class is responsible for fetching ticket listings from the
    StubHub API for tracked events, with retry capability and error handling.
    """
    
    def __init__(self, base_url: str = None):
        """
        Initialize the StubHub API client.
        
        Args:
            base_url: Base URL for the StubHub API
        """
        self.base_url = base_url or settings.stubhub_proxy_api_url
        self.api_key = settings.stubhub_proxy_api_key
        
    async def get_listings(self, viagogo_id: str) -> List[Dict[str, Any]]:
        """
        Get ticket listings for an event.
        
        Args:
            viagogo_id: The viagogo event ID to fetch listings for
            
        Returns:
            List of ticket listings
        """
        url = f"{self.base_url}/listings/{viagogo_id}"

        logger.info(f"Fetching listings for event with viagogo ID: {viagogo_id} with URL: {url}")
        
        # Create headers with API key if available
        headers = {}
        if self.api_key:
            headers['x-api-key'] = self.api_key
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Successfully fetched listings for event {viagogo_id}")
                        return self._parse_listings(data)
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"API error for event {viagogo_id}", 
                            status=response.status, 
                            error=error_text
                        )
                        return []
        except Exception as e:
            logger.error(f"Failed to fetch listings for event {viagogo_id}", error=str(e))
            return []
    
    def _parse_listings(self, response_data: Any) -> List[Dict[str, Any]]:
        """
        Parse ticket listings from the API response.
        
        Args:
            response_data: Raw API response data
            
        Returns:
            List of parsed ticket listings
        """
        listings = []
        
        try:
            # Parse the proxy API response format
            if isinstance(response_data, dict) and 'listings' in response_data:
                # Extract metadata if needed
                event_name = response_data.get('event_name')
                event_datetime = response_data.get('event_datetime')
                venue = response_data.get('venue', {})
                
                if event_name:
                    logger.info(f"Event name: {event_name}")
                if event_datetime:
                    logger.info(f"Event datetime: {event_datetime}")
                
                # Process each listing
                for item in response_data.get('listings', []):
                    if not isinstance(item, dict):
                        continue
                        
                    # Map the proxy API response to our expected format
                    listing = {
                        'section': item.get('section', 'Unknown'),
                        'row': item.get('row'),
                        'quantity': item.get('quantity', 1),
                        'pricePerTicket': float(item.get('price_per_ticket', 0)),
                        'totalPrice': float(item.get('total_price', 0)),
                        'currency': item.get('currency', 'USD'),
                        'listingUrl': item.get('listing_url')
                    }
                    listings.append(listing)
                
                logger.info(f"Parsed {len(listings)} listings from API response")
                return listings
            else:
                logger.error("Unexpected response format from proxy API")
                return []
        except Exception as e:
            logger.error("Error parsing listings from API response", error=str(e))
            return []
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def get_listings_with_retry(self, viagogo_id: str) -> List[Listing]:
        """
        Get ticket listings with retry logic and convert to domain models.
        
        Args:
            viagogo_id: The viagogo event ID to fetch listings for
            
        Returns:
            List of Listing domain models
        """
        raw_listings = await self.get_listings(viagogo_id)
        
        if not raw_listings:
            return []
            
        # Convert to domain models
        return Listing.from_list(raw_listings, viagogo_id)
    
    async def fetch_all_listings(self, viagogo_ids: List[str]) -> Dict[str, List[Listing]]:
        """
        Fetch listings for multiple events concurrently.
        
        Args:
            viagogo_ids: List of viagogo event IDs to fetch listings for
            
        Returns:
            Dictionary mapping viagogo IDs to lists of listings
        """
        results = {}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task(f"Fetching listings for {len(viagogo_ids)} events...", total=len(viagogo_ids))
            
            for viagogo_id in viagogo_ids:
                # Add some randomized delay to avoid detection
                delay = random.uniform(1.5, 4.5)
                await asyncio.sleep(delay)
                
                listings = await self.get_listings_with_retry(viagogo_id)
                results[viagogo_id] = listings
                
                progress.update(task, advance=1)
                
        return results