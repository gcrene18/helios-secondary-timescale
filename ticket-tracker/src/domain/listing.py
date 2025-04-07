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
    viagogo_listing_id: Optional[int] = None  # The specific listing ID from viagogo
    row_id: Optional[int] = None  # The row ID from viagogo for tracking
    section: str
    row: Optional[str] = None
    quantity: int
    price_per_ticket: float
    total_price: float
    currency: str = "USD"
    listing_url: Optional[str] = None
    provider: str = "StubHub"
    listing_notes: Optional[Any] = None  # Notes about the listing (e.g., "Side or rear view")
    captured_at: datetime = Field(default_factory=datetime.now)
    
    @validator('listing_notes', pre=True)
    def convert_listing_notes(cls, value):
        """Ensure listing_notes is properly formatted for database storage."""
        import json
        
        if value is None:
            return None
            
        # If it's already a string, assume it's already JSON
        if isinstance(value, str):
            try:
                # Validate it's proper JSON by parsing and re-serializing
                return json.dumps(json.loads(value))
            except (TypeError, ValueError):
                # If it's not valid JSON, store it as a JSON string
                return json.dumps(value)
                
        # Convert list or dict to JSON string
        try:
            return json.dumps(value)
        except (TypeError, ValueError):
            # If conversion fails, return empty JSON array
            return '[]'
    
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
            "viagogo_listing_id": self.viagogo_listing_id,
            "row_id": self.row_id,
            "section": self.section,
            "row": self.row,
            "quantity": self.quantity,
            "price_per_ticket": self.price_per_ticket,
            "total_price": self.total_price,
            "currency": self.currency,
            "listing_url": self.listing_url,
            "provider": self.provider,
            "listing_notes": self.listing_notes,
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
            viagogo_listing_id=data.get('viagogoListingId'),
            row_id=data.get('rowId'),
            section=data.get('section', 'Unknown'),
            row=data.get('row'),
            quantity=data.get('quantity', 1),
            price_per_ticket=data.get('pricePerTicket', 0.0),
            total_price=data.get('totalPrice', 0.0),
            currency=data.get('currency', 'USD'),
            listing_url=data.get('listingUrl'),
            listing_notes=data.get('listingNotes')
        )
    
    @classmethod
    def from_list(cls, listings_data: List[Dict[str, Any]], viagogo_id: str) -> List['Listing']:
        """Create multiple Listing instances from a list of StubHub API responses."""
        return [cls.from_stubhub_api(listing, viagogo_id) for listing in listings_data]
    
    def __str__(self) -> str:
        """String representation of the listing."""
        return (f"{self.quantity} ticket(s) in {self.section} "
                f"(row: {self.row or 'N/A'}) @ {self.price_per_ticket:.2f} {self.currency} each")
