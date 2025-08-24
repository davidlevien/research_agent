"""Simple TTL cache for HTTP responses to prevent repeat fetches."""
import time
from typing import Optional, Tuple, Dict, Any


# Cache storage: (method, url) -> (expires, response_data, headers, status, content_type)
_CACHE: Dict[Tuple[str, str], Tuple[float, Any, Dict, int, str]] = {}


def get(key: Tuple[str, str], ttl: int = 0) -> Optional[Tuple[Any, Dict, int, str]]:
    """Get cached response if not expired.
    
    Args:
        key: (method, url) tuple
        ttl: Not used for get, kept for interface consistency
        
    Returns:
        (response_data, headers, status, content_type) or None if not cached/expired
    """
    v = _CACHE.get(key)
    if v and v[0] > time.time():
        return v[1:]  # Return everything except expiry time
    return None


def set(key: Tuple[str, str], ttl: int, payload: Tuple[Any, Dict, int, str]) -> None:
    """Cache response with TTL.
    
    Args:
        key: (method, url) tuple
        ttl: Time to live in seconds
        payload: (response_data, headers, status, content_type) tuple
    """
    _CACHE[key] = (time.time() + ttl,) + payload


def clear() -> None:
    """Clear all cached entries."""
    _CACHE.clear()


def cleanup() -> None:
    """Remove expired entries from cache."""
    now = time.time()
    expired = [k for k, v in _CACHE.items() if v[0] <= now]
    for k in expired:
        del _CACHE[k]


def size() -> int:
    """Get number of cached entries."""
    return len(_CACHE)


def parse_cache_control(headers: Dict[str, str]) -> int:
    """Parse Cache-Control header to determine TTL.
    
    Args:
        headers: Response headers
        
    Returns:
        TTL in seconds (default 900 if not specified)
    """
    cc = headers.get("cache-control", "").lower()
    
    # Don't cache if no-cache or no-store
    if "no-cache" in cc or "no-store" in cc:
        return 0
    
    # Look for max-age
    if "max-age=" in cc:
        try:
            parts = cc.split("max-age=")[1].split(",")[0]
            max_age = int(parts.strip())
            # Cap at 30 minutes
            return min(max_age, 1800)
        except (ValueError, IndexError):
            pass
    
    # Default to 15 minutes
    return 900