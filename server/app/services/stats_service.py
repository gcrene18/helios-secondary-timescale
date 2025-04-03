"""
Statistics service for tracking system usage and performance
"""
from loguru import logger
import time
import asyncio
import os
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Global stats tracking
_stats = {
    "start_time": datetime.now().isoformat(),
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "avg_response_time_ms": 0,
    "requests_by_event": {},
    "hourly_requests": [0] * 24  # Requests by hour of day
}

_response_times = []  # List to calculate rolling average

def increment_request_counter(event_id: str = None, success: bool = True):
    """Increment request counters"""
    global _stats
    
    _stats["total_requests"] += 1
    
    if success:
        _stats["successful_requests"] += 1
    else:
        _stats["failed_requests"] += 1
        
    # Track by event_id if provided
    if event_id:
        if event_id not in _stats["requests_by_event"]:
            _stats["requests_by_event"][event_id] = 0
        _stats["requests_by_event"][event_id] += 1
    
    # Track by hour
    current_hour = datetime.now().hour
    _stats["hourly_requests"][current_hour] += 1


def record_response_time(response_time_ms: float):
    """Record response time for averaging"""
    global _stats, _response_times
    
    # Keep last 100 response times for rolling average
    _response_times.append(response_time_ms)
    if len(_response_times) > 100:
        _response_times.pop(0)
    
    # Update average
    _stats["avg_response_time_ms"] = sum(_response_times) / len(_response_times)


def increment_cache_counter(hit: bool = True):
    """Increment cache hit/miss counters"""
    global _stats
    
    if hit:
        _stats["cache_hits"] += 1
    else:
        _stats["cache_misses"] += 1


async def get_system_stats() -> Dict[str, Any]:
    """
    Get comprehensive system statistics
    """
    global _stats
    
    try:
        # Get process stats
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        cpu_percent = process.cpu_percent(interval=0.1)
        
        # Calculate uptime
        start_time = datetime.fromisoformat(_stats["start_time"])
        uptime_seconds = (datetime.now() - start_time).total_seconds()
        
        # Get cache stats directly from the cache module to avoid circular imports
        from app.db.cache import get_cache_stats
        
        # Combine all stats
        system_stats = {
            "api": {
                "uptime_seconds": uptime_seconds,
                "start_time": _stats["start_time"],
                "total_requests": _stats["total_requests"],
                "successful_requests": _stats["successful_requests"],
                "failed_requests": _stats["failed_requests"],
                "success_rate": (_stats["successful_requests"] / _stats["total_requests"]) * 100 if _stats["total_requests"] > 0 else 0,
                "avg_response_time_ms": _stats["avg_response_time_ms"],
                "requests_by_hour": _stats["hourly_requests"],
                "top_requested_events": sorted(_stats["requests_by_event"].items(), key=lambda x: x[1], reverse=True)[:10]
            },
            "cache": {
                "hits": _stats["cache_hits"],
                "misses": _stats["cache_misses"],
                "hit_rate": (_stats["cache_hits"] / (_stats["cache_hits"] + _stats["cache_misses"])) * 100 if (_stats["cache_hits"] + _stats["cache_misses"]) > 0 else 0,
                **await get_cache_stats()
            },
            "system": {
                "memory_usage_mb": memory_info.rss / (1024 * 1024),
                "cpu_percent": cpu_percent,
                "thread_count": len(psutil.Process().threads())
            }
        }
        
        return system_stats
        
    except Exception as e:
        logger.error(f"Error getting system stats: {str(e)}")
        return {
            "error": str(e),
            "api": _stats
        }
