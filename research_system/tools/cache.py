"""HTTP cache with ETag and Last-Modified support."""

import hashlib
import json
import os
import httpx
from datetime import datetime, timedelta
from typing import Tuple, Dict, Optional, Any
import logging
from ..config import get_settings

logger = logging.getLogger(__name__)

# Lazy load settings to avoid import-time instantiation
def _get_cache_dir():
    return get_settings().HTTP_CACHE_DIR

DEFAULT_TTL = timedelta(days=7)


def _cache_key(url: str) -> str:
    """Generate cache key from URL."""
    return hashlib.sha256(url.encode()).hexdigest()


def _cache_path(url: str) -> str:
    """Get cache file path for URL."""
    key = _cache_key(url)
    # Use subdirectories to avoid too many files in one directory
    subdir = key[:2]
    return os.path.join(_get_cache_dir(), subdir, f"{key}.json")


def _save_to_cache(path: str, response: httpx.Response):
    """Save response to cache file."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        cache_data = {
            "ts": datetime.utcnow().timestamp(),
            "status": response.status_code,
            "headers": dict(response.headers),
            "content": response.text[:2_000_000],  # Limit content size
            "url": str(response.url)
        }
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)
            
    except Exception as e:
        logger.warning(f"Failed to save cache: {e}")


def get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 25,
    ttl: Optional[timedelta] = None
) -> Tuple[int, Dict[str, str], str]:
    """
    HTTP GET with caching and conditional requests.
    
    Args:
        url: URL to fetch
        headers: Request headers
        timeout: Request timeout in seconds
        ttl: Cache time-to-live (default: 7 days)
        
    Returns:
        Tuple of (status_code, headers, content)
    """
    if ttl is None:
        ttl = DEFAULT_TTL
        
    os.makedirs(_get_cache_dir(), exist_ok=True)
    cache_path = _cache_path(url)
    
    # Check cache
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            
            # Check if cache is still valid
            cache_age = datetime.utcnow().timestamp() - cache_data["ts"]
            
            if cache_age < ttl.total_seconds():
                # Cache is fresh, return it
                logger.debug(f"Cache hit for {url}")
                return (
                    cache_data["status"],
                    cache_data["headers"],
                    cache_data["content"]
                )
            
            # Cache is stale, try conditional GET
            req_headers = headers or {}
            
            # Add conditional headers if available
            if "ETag" in cache_data["headers"]:
                req_headers["If-None-Match"] = cache_data["headers"]["ETag"]
            if "Last-Modified" in cache_data["headers"]:
                req_headers["If-Modified-Since"] = cache_data["headers"]["Last-Modified"]
            
            # Make conditional request
            r = httpx.get(url, headers=req_headers, timeout=timeout, follow_redirects=True)
            
            if r.status_code == 304:
                # Not modified, update timestamp and return cached content
                logger.debug(f"304 Not Modified for {url}")
                cache_data["ts"] = datetime.utcnow().timestamp()
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(cache_data, f)
                return (
                    cache_data["status"],
                    cache_data["headers"],
                    cache_data["content"]
                )
            
            # Content has changed, save new version
            _save_to_cache(cache_path, r)
            return r.status_code, dict(r.headers), r.text
            
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
    
    # No cache or error, make fresh request
    r = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
    _save_to_cache(cache_path, r)
    return r.status_code, dict(r.headers), r.text


def get_binary(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 45,
    ttl: Optional[timedelta] = None
) -> Tuple[int, Dict[str, str], bytes]:
    """
    HTTP GET for binary content with caching.
    
    Args:
        url: URL to fetch
        headers: Request headers
        timeout: Request timeout in seconds
        ttl: Cache time-to-live
        
    Returns:
        Tuple of (status_code, headers, content_bytes)
    """
    if ttl is None:
        ttl = DEFAULT_TTL
        
    os.makedirs(_get_cache_dir(), exist_ok=True)
    
    # Use separate binary cache
    key = _cache_key(url)
    subdir = key[:2]
    cache_path = os.path.join(_get_cache_dir(), subdir, f"{key}.bin")
    meta_path = os.path.join(_get_cache_dir(), subdir, f"{key}.meta.json")
    
    # Check cache
    if os.path.exists(cache_path) and os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            
            # Check if cache is still valid
            cache_age = datetime.utcnow().timestamp() - meta["ts"]
            
            if cache_age < ttl.total_seconds():
                # Cache is fresh
                logger.debug(f"Binary cache hit for {url}")
                with open(cache_path, "rb") as f:
                    content = f.read()
                return meta["status"], meta["headers"], content
                
        except Exception as e:
            logger.warning(f"Binary cache read error: {e}")
    
    # Make fresh request
    r = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
    
    # Save to cache
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        
        with open(cache_path, "wb") as f:
            f.write(r.content)
        
        meta = {
            "ts": datetime.utcnow().timestamp(),
            "status": r.status_code,
            "headers": dict(r.headers),
            "url": str(r.url)
        }
        
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f)
            
    except Exception as e:
        logger.warning(f"Failed to save binary cache: {e}")
    
    return r.status_code, dict(r.headers), r.content


def clear_cache():
    """Clear all cached files."""
    import shutil
    
    if os.path.exists(_get_cache_dir()):
        try:
            cache_dir = _get_cache_dir()
            shutil.rmtree(cache_dir)
            logger.info(f"Cleared cache directory: {cache_dir}")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")


def get_cache_size() -> int:
    """Get total size of cache in bytes."""
    total_size = 0
    
    if not os.path.exists(_get_cache_dir()):
        return 0
    
    for dirpath, _, filenames in os.walk(_get_cache_dir()):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            try:
                total_size += os.path.getsize(filepath)
            except Exception:
                pass
                
    return total_size