"""
API routes for the StubHub Proxy API Server
"""
from fastapi import APIRouter, Depends, HTTPException, status
from app.api.deps import verify_api_key

# Import endpoint routers
from app.api.endpoints.listings import router as listings_router
from app.api.endpoints.health import router as health_router
from app.api.endpoints.stats import router as stats_router

# Create main API router
api_router = APIRouter()

# Include endpoint routers with dependencies
api_router.include_router(
    listings_router,
    prefix="/listings",
    tags=["Listings"],
    dependencies=[Depends(verify_api_key)]
)

api_router.include_router(
    health_router,
    prefix="/health",
    tags=["Health"]
)

api_router.include_router(
    stats_router,
    prefix="/stats",
    tags=["Stats"],
    dependencies=[Depends(verify_api_key)]
)
