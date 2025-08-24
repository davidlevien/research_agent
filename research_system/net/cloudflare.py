"""Cloudflare challenge detection."""
import httpx
from typing import Optional


def is_cf_challenge(resp: httpx.Response) -> bool:
    """Detect Cloudflare challenge/interstitial pages.
    
    Args:
        resp: httpx Response to check
        
    Returns:
        True if Cloudflare challenge detected
    """
    h = {k.lower(): v for k, v in resp.headers.items()}
    
    # Check for Cloudflare server header
    if h.get("server", "").lower().startswith("cloudflare"):
        body = (resp.text or "").lower()
        # Check for known challenge indicators
        return "just a moment" in body or "cf-chl" in body or "checking your browser" in body
    
    return False


def get_unwto_mirror_url(url: str) -> Optional[str]:
    """Get UNWTO Asia-Pacific mirror URL.
    
    Args:
        url: Original UNWTO URL
        
    Returns:
        Mirror URL or None if not UNWTO
    """
    if "unwto.org" in (url or ""):
        # Try Asia-Pacific mirror
        return url.replace("www.unwto.org", "en.unwto-ap.org").replace("unwto.org", "en.unwto-ap.org")
    return None