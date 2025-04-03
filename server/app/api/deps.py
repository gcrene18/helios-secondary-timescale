"""
Dependencies for API endpoints
"""
from fastapi import Header, HTTPException, status, Depends
from app.config import settings
from typing import Optional

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """
    Verify the API key provided in the X-API-Key header
    """
    if not settings.API_KEY:
        # If API_KEY is not set in settings, we're in development mode and skip verification
        return True
        
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key"
        )
        
    if x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key"
        )
        
    return True
