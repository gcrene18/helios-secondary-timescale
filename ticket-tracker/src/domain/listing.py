"""
Domain model for ticket listings.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, validator


class Listing(BaseModel):
    """
    Domain model for ticket listings.
    
    A listing represents a ticket or set of tickets available for 
    purchase on the secondary market for a specific event.
    """
    listing_id: Optional[int] = None
    event_id: Optional[int] = None
    viagogo_id: str
    section: str
    row: Optional[str] = None
    quantity: int
    price_per_ticket: float
    total_price: float
    currency: str = "USD"
    listing_url: Optional[str] = None
    provider: str = "StubHub"
    captured_at: datetime = Field(default_factory=datetime.now)
    
    @validator('total_price', pre=True)
    def calculate_total_price(cls, value, values):
        """Calculate total price if not provided but price per ticket is available."""
        if value is not None:
            return value
            
        price = values.get('price_per_ticket')
        quantity = values.get('quantity')
        
        if price is not None and quantity is not None:
            return price * quantity
            
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert listing to dictionary for database operations."""
        return {
            "listing_id": self.listing_id,
            "event_id": self.event_id,
            "viagogo_id": self.viagogo_id,
            "section": self.section,
            "row": self.row,
            "quantity": self.quantity,
            "price_per_ticket": self.price_per_ticket,
            "total_price": self.total_price,
            "currency": self.currency,
            "listing_url": self.listing_url,
            "provider": self.provider,
            "captured_at": self.captured_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Listing':
        """Create a Listing instance from a dictionary."""
        return cls(**data)
    
    @classmethod
    def from_stubhub_api(cls, data: Dict[str, Any], viagogo_id: str) -> 'Listing':
        """Create a Listing instance from StubHub API response."""
        return cls(
            viagogo_id=viagogo_id,
            section=data.get('section', 'Unknown'),
            row=data.get('row'),
            quantity=data.get('quantity', 1),
            price_per_ticket=data.get('pricePerTicket', 0.0),
            total_price=data.get('totalPrice', 0.0),
            currency=data.get('currency', 'USD'),
            listing_url=data.get('listingUrl')
        )
    
    @classmethod
    def from_list(cls, listings_data: List[Dict[str, Any]], viagogo_id: str) -> List['Listing']:
        """Create multiple Listing instances from a list of StubHub API responses."""
        return [cls.from_stubhub_api(listing, viagogo_id) for listing in listings_data]
    
    def __str__(self) -> str:
        """String representation of the listing."""
        return (f"{self.quantity} ticket(s) in {self.section} "
                f"(row: {self.row or 'N/A'}) @ {self.price_per_ticket:.2f} {self.currency} each")
