"""
StubHub Proxy API Server - Main Application Entry Point
"""
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import os
from dotenv import load_dotenv

from app.config import settings
from app.api.routes import api_router
from app.core.logging import setup_logging

# This must be the first import
import fix_asyncio

# Load environment variables
load_dotenv()

# Setup logging
setup_logging()

# Create FastAPI application
app = FastAPI(
    title="StubHub Proxy API",
    description="A proxy API service for fetching StubHub ticket data",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint for health checks"""
    return {"status": "healthy", "message": "StubHub Proxy API is running"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
