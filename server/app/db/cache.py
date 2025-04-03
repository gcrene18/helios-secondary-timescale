"""
Cache implementation for storing event listing data
"""
import redis.asyncio as redis
import json
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger

from app.config import settings

# Global redis client
_redis_client = None

# Internal stats counters - moved here to avoid circular imports
_cache_stats = {
    "hits": 0,
    "misses": 0,
    "last_hit": None,
    "last_miss": None
}

async def get_redis_client() -> redis.Redis:
    """Get or create Redis client"""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(settings.REDIS_URL)
            # Test connection
            await _redis_client.ping()
            logger.info(f"Connected to Redis at {settings.REDIS_URL}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            _redis_client = None
    return _redis_client


async def get_cached_listings(event_id: str) -> Optional[Dict[str, Any]]:
    """
    Get cached listings for an event
    
    Args:
        event_id: StubHub event ID
        
    Returns:
        Cached listing data if available, None otherwise
    """
    global _cache_stats
    try:
        redis_client = await get_redis_client()
        if not redis_client:
            logger.warning("Redis client not available for cache lookup")
            return None
            
        # Check if data exists in cache
        cache_key = f"listings:{event_id}"
        cached_data = await redis_client.get(cache_key)
        
        if cached_data:
            # Update stats
            _cache_stats["hits"] += 1
            _cache_stats["last_hit"] = datetime.now().isoformat()
            
            logger.info(f"Cache hit for event {event_id}")
            return json.loads(cached_data)
        else:
            # Update stats
            _cache_stats["misses"] += 1
            _cache_stats["last_miss"] = datetime.now().isoformat()
            
            logger.info(f"Cache miss for event {event_id}")
            return None
    except Exception as e:
        logger.error(f"Error reading from cache: {e}")
        return None


async def cache_listings(event_id: str, listings_data: Dict[str, Any]) -> bool:
    """
    Cache listings data for an event
    
    Args:
        event_id: StubHub event ID
        listings_data: Listing data to cache
    """
    try:
        redis_client = await get_redis_client()
        if not redis_client:
            logger.warning("Redis client not available for caching")
            return False
            
        # Store data in cache with TTL
        cache_key = f"listings:{event_id}"
        serialized_data = json.dumps(listings_data)
        await redis_client.setex(
            cache_key,
            settings.CACHE_TTL_SECONDS,
            serialized_data
        )
        logger.info(f"Cached listings for event {event_id} with TTL {settings.CACHE_TTL_SECONDS}s")
        return True
    except Exception as e:
        logger.error(f"Error writing to cache: {e}")
        return False


async def get_cache_status() -> Dict[str, Any]:
    """
    Get cache connection status and metrics
    
    Returns:
        Dictionary with cache status information
    """
    try:
        redis_client = await get_redis_client()
        if not redis_client:
            return {
                "connected": False,
                "error": "Redis client not available"
            }
            
        # Get basic Redis info
        info = await redis_client.info()
        
        # Calculate cache size
        db_keys = await redis_client.keys("listings:*")
        
        return {
            "connected": True,
            "version": info.get("redis_version", "unknown"),
            "uptime_seconds": info.get("uptime_in_seconds", 0),
            "memory_used_mb": round(info.get("used_memory", 0) / (1024 * 1024), 2),
            "total_cached_events": len(db_keys),
            "cache_ttl_seconds": settings.CACHE_TTL_SECONDS
        }
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        return {
            "connected": False,
            "error": str(e)
        }


async def get_cache_stats() -> Dict[str, Any]:
    """
    Get detailed cache statistics
    
    Returns:
        Dictionary with cache statistics
    """
    global _cache_stats
    
    try:
        redis_client = await get_redis_client()
        if not redis_client:
            return {
                "connected": False,
                "hits": _cache_stats["hits"],
                "misses": _cache_stats["misses"],
                "hit_ratio": calculate_hit_ratio(_cache_stats["hits"], _cache_stats["misses"]),
                "last_hit": _cache_stats["last_hit"],
                "last_miss": _cache_stats["last_miss"]
            }
            
        # Get all cached events
        event_keys = await redis_client.keys("listings:*")
        events = []
        
        # Get TTL for each event
        for key in event_keys:
            event_id = key.decode('utf-8').split(':')[1]
            ttl = await redis_client.ttl(key)
            events.append({
                "event_id": event_id,
                "ttl_seconds": ttl
            })
            
        return {
            "connected": True,
            "hits": _cache_stats["hits"],
            "misses": _cache_stats["misses"],
            "hit_ratio": calculate_hit_ratio(_cache_stats["hits"], _cache_stats["misses"]),
            "last_hit": _cache_stats["last_hit"],
            "last_miss": _cache_stats["last_miss"],
            "cached_events": events
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {
            "connected": False,
            "hits": _cache_stats["hits"],
            "misses": _cache_stats["misses"],
            "hit_ratio": calculate_hit_ratio(_cache_stats["hits"], _cache_stats["misses"]),
            "last_hit": _cache_stats["last_hit"],
            "last_miss": _cache_stats["last_miss"],
            "error": str(e)
        }


def calculate_hit_ratio(hits: int, misses: int) -> float:
    """Calculate cache hit ratio"""
    if hits + misses == 0:
        return 0
    return round(hits / (hits + misses), 2)


def increment_cache_counter(hit: bool = True) -> None:
    """
    Increment cache hit/miss counters
    
    Args:
        hit: True if cache hit, False if miss
    """
    global _cache_stats
    if hit:
        _cache_stats["hits"] += 1
        _cache_stats["last_hit"] = datetime.now().isoformat()
    else:
        _cache_stats["misses"] += 1
        _cache_stats["last_miss"] = datetime.now().isoformat()
