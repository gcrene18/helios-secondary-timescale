"""
Data models and schemas for the StubHub Proxy API
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Dict, Any, Optional
from datetime import datetime


class Venue(BaseModel):
    """Venue information model"""
    name: str = Field(..., description="Name of the venue")
    location: str = Field(..., description="Location of the venue (city, state)")


class Price(BaseModel):
    """Price information model"""
    amount: float = Field(..., description="Price amount")
    currency: str = Field("USD", description="Currency code")


class Listing(BaseModel):
    """Individual ticket listing model"""
    id: str = Field(..., description="Listing ID")
    currentPrice: Price
    section: str = Field(..., description="Section of the venue")
    row: Optional[str] = Field(None, description="Row within the section")
    quantity: int = Field(1, description="Number of tickets available")
    seats: Optional[List[str]] = Field(None, description="Specific seat numbers if available")
    seller: Optional[Dict[str, Any]] = Field(None, description="Information about the seller")
    
    
class EventListingResponse(BaseModel):
    """Response model for listing data"""
    event_id: str = Field(..., description="StubHub event ID")
    event_name: str = Field(..., description="Name of the event")
    event_datetime: str = Field(..., description="Date and time of the event")
    venue: Venue
    listings: List[Listing] = Field([], description="List of ticket listings")
    total_listings: int = Field(0, description="Total number of listings found")
    min_price: float = Field(0.0, description="Minimum listing price")
    max_price: float = Field(0.0, description="Maximum listing price")
    median_price: float = Field(0.0, description="Median listing price")
    fetched_at: str = Field(..., description="Timestamp when the data was fetched")
    cached: bool = Field(False, description="Whether this data came from cache")


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str = Field(..., description="Overall service status")
    message: Optional[str] = Field(None, description="Additional status message")


class DetailedHealthResponse(BaseModel):
    """Detailed health check response model"""
    status: str = Field(..., description="Overall service status")
    components: Dict[str, Dict[str, Any]] = Field(..., description="Status of individual components")


class StatsResponse(BaseModel):
    """System statistics response model"""
    api: Dict[str, Any] = Field(..., description="API usage statistics")
    browser_pool: Dict[str, Any] = Field(..., description="Browser pool statistics")
    cache: Dict[str, Any] = Field(..., description="Cache statistics")
    system: Dict[str, Any] = Field(..., description="System resource usage")
