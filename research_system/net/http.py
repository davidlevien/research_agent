"""Resilient HTTP client with retries and concurrency control."""

import httpx
import asyncio
import random
import time
from typing import Optional, Any


class Client:
    """
    Resilient HTTP client with automatic retries and backoff.
    """
    
    def __init__(self, timeout: int = 20, max_retries: int = 2, 
                 backoff: float = 0.6, limit: int = 16):
        """
        Initialize the resilient HTTP client.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            backoff: Base backoff delay multiplier
            limit: Maximum concurrent requests
        """
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)
        self.max_retries = max_retries
        self.backoff = backoff
        self.sem = asyncio.Semaphore(limit)
    
    def get(self, url: str, **kwargs) -> httpx.Response:
        """
        Make a GET request with automatic retries.
        
        Args:
            url: URL to fetch
            **kwargs: Additional arguments to pass to httpx
            
        Returns:
            httpx.Response object
            
        Raises:
            httpx.HTTPError: If all retries fail
        """
        delay = 0
        
        for i in range(self.max_retries + 1):
            try:
                # Apply backoff delay if not first attempt
                if delay:
                    time.sleep(delay)
                
                # Make the request
                r = self.client.get(url, **kwargs)
                
                # Retry on server errors
                if r.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPError(f"HTTP {r.status_code}")
                
                return r
                
            except Exception as e:
                # Calculate exponential backoff with jitter
                delay = self.backoff * (2 ** i) + random.uniform(0, 0.2)
                
                # Re-raise on last attempt
                if i == self.max_retries:
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