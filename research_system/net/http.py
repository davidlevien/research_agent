"""Resilient HTTP client with retries and concurrency control."""

import httpx
import asyncio
import random
import time
from typing import Optional, Any


class Client:
    """
    Resilient HTTP client with automatic retries and backoff.
    Enhanced for official statistics portals with aggressive retry for 403/429.
    """
    
    def __init__(self, timeout: int = 30, max_retries: int = 4, 
                 backoff: float = 1.0, limit: int = 16):
        """
        Initialize the resilient HTTP client.
        
        Args:
            timeout: Request timeout in seconds (increased for official portals)
            max_retries: Maximum number of retry attempts (increased for resilience)
            backoff: Base backoff delay multiplier 
            limit: Maximum concurrent requests
        """
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)
        self.max_retries = max_retries
        self.backoff = backoff
        self.sem = asyncio.Semaphore(limit)
        
        # Official domains that need special handling
        self.official_domains = {
            "oecd.org", "imf.org", "worldbank.org", "ec.europa.eu", 
            "eurostat.ec.europa.eu", "bea.gov", "bls.gov", "irs.gov", 
            "cbo.gov", "gao.gov", "treasury.gov", "un.org", 
            "data.worldbank.org", "ourworldindata.org"
        }
    
    def get(self, url: str, **kwargs) -> httpx.Response:
        """
        Make a GET request with automatic retries.
        Enhanced retry logic for official statistics portals.
        
        Args:
            url: URL to fetch
            **kwargs: Additional arguments to pass to httpx
            
        Returns:
            httpx.Response object
            
        Raises:
            httpx.HTTPError: If all retries fail
        """
        import logging
        from urllib.parse import urlparse
        
        logger = logging.getLogger(__name__)
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Check if this is an official domain needing special handling
        is_official = any(official in domain for official in self.official_domains)
        
        # Use more aggressive retries for official domains
        max_attempts = self.max_retries + 2 if is_official else self.max_retries + 1
        delay = 0
        
        for i in range(max_attempts):
            try:
                # Apply backoff delay if not first attempt
                if delay:
                    logger.debug(f"Waiting {delay:.1f}s before retry {i+1}/{max_attempts} for {domain}")
                    time.sleep(delay)
                
                # Make the request
                r = self.client.get(url, **kwargs)
                
                # Retry on rate limiting and server errors
                if r.status_code in (403, 429, 500, 502, 503, 504):
                    # Special handling for 403/429 from official sources
                    if is_official and r.status_code in (403, 429):
                        logger.info(f"Rate limited by official source {domain} (HTTP {r.status_code}), will retry with backoff")
                    raise httpx.HTTPError(f"HTTP {r.status_code}")
                
                return r
                
            except Exception as e:
                # Calculate exponential backoff with jitter
                # More aggressive backoff for official sources
                if is_official:
                    # Start at 1s, max 16s with exponential growth
                    delay = min(16, self.backoff * (2 ** i)) + random.uniform(0, 1.0)
                else:
                    # Standard backoff
                    delay = self.backoff * (2 ** i) + random.uniform(0, 0.2)
                
                # Re-raise on last attempt
                if i == max_attempts - 1:
                    logger.warning(f"All retries exhausted for {domain}: {e}")
                    raise
    
    async def aget(self, url: str, **kwargs) -> httpx.Response:
        """
        Async version of get with concurrency control.
        
        Args:
            url: URL to fetch
            **kwargs: Additional arguments to pass to httpx
            
        Returns:
            httpx.Response object
        """
        async with self.sem:
            # Use sync client in async context for simplicity
            return await asyncio.to_thread(self.get, url, **kwargs)
    
    def close(self):
        """Close the underlying HTTP client."""
        self.client.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, *args):
        """Context manager exit."""
        self.close()


# Shared global instance
shared_http = Client()