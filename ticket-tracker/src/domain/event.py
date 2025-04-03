"""
Domain model for events.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


class Event(BaseModel):
    """
    Domain model representing a live event.
    
    An event is a concert, sports game, or other live performance
    that is being tracked for ticket price analysis.
    """
    event_id: Optional[int] = None
    name: str
    venue: str
    city: str
    country: str
    event_date: datetime
    viagogo_id: str
    is_tracked: bool = True  # Default to True for backward compatibility
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    
    @validator('event_date', pre=True)
    def parse_date(cls, value):
        """Parse date from string if it's not already a datetime."""
        if isinstance(value, datetime):
            return value
            
        try:
            # Handles ISO format date strings
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            try:
                # Try a more flexible parsing approach if ISO format fails
                from dateutil import parser
                return parser.parse(value)
            except:
                raise ValueError(f"Invalid date format: {value}")
    
    @validator('is_tracked', pre=True)
    def parse_is_tracked(cls, value):
        """Parse is_tracked from various formats."""
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            # Convert string values to boolean
            return value.lower() in ('true', 't', 'yes', 'y', '1')
        
        return bool(value)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for database operations."""
        return {
            "event_id": self.event_id,
            "name": self.name,
            "venue": self.venue,
            "city": self.city,
            "country": self.country,
            "event_date": self.event_date,
            "viagogo_id": self.viagogo_id,
            "is_tracked": self.is_tracked,
            "created_at": self.created_at,
            "updated_at": self.updated_at or self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create an Event instance from a dictionary."""
        return cls(**data)
    
    @classmethod
    def from_google_sheets_row(cls, row: List[str]) -> 'Event':
        """Create an Event instance from a Google Sheets row."""
        if len(row) < 6:
            raise ValueError("Incomplete row data for event")
        
        # Parse is_tracked from the 7th column (index 6) if it exists
        is_tracked = True  # Default to True if not specified
        if len(row) > 6:
            try:
                is_tracked = row[6].lower() in ('true', 't', 'yes', 'y', '1')
            except (IndexError, AttributeError):
                # Keep default if any error occurs
                pass
            
        return cls(
            name=row[0],
            venue=row[1],
            city=row[2],
            country=row[3],
            event_date=row[4],
            viagogo_id=row[5],
            is_tracked=is_tracked
        )
    
    def __str__(self) -> str:
        """String representation of the event."""
        event_date_str = self.event_date.strftime("%Y-%m-%d %H:%M") if self.event_date else "Unknown"
        tracked_status = "tracked" if self.is_tracked else "not tracked"
        return f"{self.name} @ {self.venue}, {self.city} ({event_date_str}) - {tracked_status}"
