"""
URL canonicalization for consistent deduplication
"""

from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import re

def canonical_url(u: str) -> str:
    """
    Canonicalize a URL by removing tracking parameters and fragments.
    Returns normalized URL for deduplication.
    """
    if not u:
        return ""
    
    try:
        p = urlparse(u)
        
        # Remove tracking/session parameters
        tracking_params = {
            "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "gclid", "fbclid", "ref", "referer", "referrer",
            "sessionid", "sid", "ssid", "s", "source",
            "versionid", "v", "t", "timestamp"
        }
        
        # Parse and filter query parameters
        if p.query:
            q = [(k, v) for (k, v) in parse_qsl(p.query, keep_blank_values=True)
                 if k.lower() not in tracking_params]
            # Sort for consistency
            q.sort()
            new_query = urlencode(q)
        else:
            new_query = ""
        
        # Remove fragment and rebuild URL
        canonical = p._replace(query=new_query, fragment="")
        result = urlunparse(canonical)
        
        # Normalize trailing slashes for consistency
        if result.endswith("/") and result.count("/") > 3:
            result = result.rstrip("/")
        
        return result
        
    except Exception:
        return u  # Return original if parsing fails