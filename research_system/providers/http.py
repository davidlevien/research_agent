"""HTTP utilities for provider integrations."""

from __future__ import annotations
import httpx
import time
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0, read=7.0)
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}

def http_json(
    method: str, 
    url: str, 
    params: Optional[Dict] = None, 
    headers: Optional[Dict] = None, 
    data: Optional[Any] = None, 
    max_retries: int = 3
) -> Dict[str, Any]:
    """Make HTTP request with retries and return JSON response."""
    backoff = 0.5
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT, headers=headers) as client:
                response = client.request(method, url, params=params, json=data)
            
            if response.status_code in RETRY_STATUSES:
                raise httpx.HTTPStatusError(
                    f"Retryable status {response.status_code}", 
                    request=response.request, 
                    response=response
                )
            
            response.raise_for_status()
            return response.json()
            
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            last_error = e
            if attempt == max_retries:
                logger.warning(f"HTTP request failed after {max_retries} attempts: {url}")
                raise
            
            logger.debug(f"Retry {attempt}/{max_retries} for {url}: {e}")
            time.sleep(backoff)
            backoff *= 2
    
    raise last_error or Exception(f"Failed to complete request to {url}")