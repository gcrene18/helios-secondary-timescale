"""
Health check endpoints for monitoring system status
"""
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from app.services.browser_pool import get_browser_pool
from app.db.cache import get_cache_status

router = APIRouter()

@router.get("/")
async def health_check():
    """
    Basic health check endpoint
    """
    return {
        "status": "healthy",
        "message": "Service is running"
    }

@router.get("/detailed")
async def detailed_health():
    """
    Detailed health check with component status
    """
    try:
        # Get browser pool status
        browser_pool = get_browser_pool()
        browser_status = {
            "total_browsers": browser_pool.total_browsers,
            "available_browsers": browser_pool.available_browsers,
            "active_sessions": browser_pool.active_sessions
        }
        
        # Get cache status
        cache_status = await get_cache_status()
        
        return {
            "status": "healthy",
            "components": {
                "api": {"status": "healthy"},
                "browser_pool": {
                    "status": "healthy" if browser_pool.available_browsers > 0 else "degraded",
                    "metrics": browser_status
                },
                "cache": {
                    "status": "healthy" if cache_status["connected"] else "unavailable",
                    "metrics": cache_status
                }
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )
