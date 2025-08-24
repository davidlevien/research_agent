"""Guarded GET with paywall detection and redirect loop prevention."""
import httpx
from urllib.parse import urlparse, urljoin
from typing import Set, Tuple


PAYWALL_HINTS = ("/login", "/signin", "/sso", "/subscribe", "/purchase", "/paywall")
LOW_VALUE_PAYWALLED = {"statista.com"}


def guarded_get(url: str, client: httpx.Client, max_redirects: int = 5) -> httpx.Response:
    """Perform GET request with paywall detection and loop prevention.
    
    Args:
        url: URL to fetch
        client: httpx client instance
        max_redirects: Maximum redirects to follow
        
    Returns:
        httpx Response object
        
    Raises:
        httpx.TooManyRedirects: If redirect loop detected
        PermissionError: If paywall/login detected
    """
    # Early domain policy for known paywalled sites
    parsed = urlparse(url)
    if any(d in parsed.netloc.lower() for d in LOW_VALUE_PAYWALLED):
        raise PermissionError(f"Known paywall domain: {parsed.netloc}")
    
    seen: Set[Tuple[str, str]] = set()
    
    for _ in range(max_redirects):
        r = client.get(url, follow_redirects=False)
        loc = r.headers.get("Location")
        
        if r.is_redirect and loc:
            nxt = urljoin(url, loc)
            p = urlparse(nxt)
            key = (p.netloc.lower(), p.path.split("?")[0])
            
            # Check for redirect loop
            if key in seen:
                raise httpx.TooManyRedirects(f"Redirect loop: {nxt}")
            
            # Check for paywall indicators
            if any(h in p.path.lower() for h in PAYWALL_HINTS):
                raise PermissionError(f"Paywall/login detected: {nxt}")
            
            seen.add(key)
            url = nxt
            continue
            
        return r
    
    raise httpx.TooManyRedirects(f"Too many redirects for {url}")