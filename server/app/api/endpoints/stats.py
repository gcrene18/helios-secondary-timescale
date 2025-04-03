"""
Statistics and usage metrics endpoints
"""
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from app.services.browser_pool import get_browser_pool
from app.services.stats_service import get_system_stats

router = APIRouter()

@router.get("/")
async def get_stats():
    """
    Get system statistics and usage metrics
    """
    try:
        browser_pool = get_browser_pool()
        
        # Get system stats
        stats = await get_system_stats()
        
        # Add browser pool stats
        browser_stats = {
            "total_browsers": browser_pool.total_browsers,
            "available_browsers": browser_pool.available_browsers,
            "active_sessions": browser_pool.active_sessions,
            "session_creation_failures": browser_pool.session_creation_failures,
            "total_requests_handled": browser_pool.total_requests_handled
        }
        
        stats["browser_pool"] = browser_stats
        
        return stats
    except Exception as e:
        logger.error(f"Failed to fetch system stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch system stats: {str(e)}"
        )
