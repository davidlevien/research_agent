"""Wayback Machine provider for archived content."""

from typing import Optional, Dict, Any
from .http import http_json
import logging

logger = logging.getLogger(__name__)

CDX = "https://web.archive.org/cdx/search/cdx"

def wayback_latest(url: str) -> Optional[Dict[str, Any]]:
    """Find the latest archived version of a URL."""
    try:
        params = {
            "url": url,
            "output": "json",
            "filter": "statuscode:200",
            "limit": 1,
            "from": "2016"
        }
        data = http_json("GET", CDX, params=params)
        
        if isinstance(data, list) and len(data) > 1:
            # First row is headers, second is data
            headers = data[0]
            row = data[1]
            
            # Create dict from headers and row
            result = {headers[i]: row[i] for i in range(len(headers))}
            
            # Add wayback URL
            timestamp = result.get("timestamp", "")
            original = result.get("original", "")
            if timestamp and original:
                result["wayback_url"] = f"https://web.archive.org/web/{timestamp}/{original}"
            
            return result
    except Exception as e:
        logger.debug(f"Wayback lookup failed for {url}: {e}")
    
    return None

def save_page_now(url: str) -> Optional[str]:
    """Request archiving of a URL and return the archive URL."""
    try:
        save_url = f"https://web.archive.org/save/{url}"
        # This would need proper implementation with status checking
        # For now, just return None as placeholder
        logger.debug(f"SavePageNow not fully implemented for {url}")
        return None
    except Exception as e:
        logger.debug(f"SavePageNow failed for {url}: {e}")
        return None