"""DOI resolution to prevent doi.org from dominating triangulation."""

import httpx
import logging

logger = logging.getLogger(__name__)

def resolve_doi(url: str, timeout: float = 20.0):
    """
    Resolve a DOI URL to its final publisher landing page.
    
    This prevents doi.org from dominating in domain caps and triangulation
    by following redirects to the actual publisher site.
    
    Args:
        url: DOI URL (e.g., https://doi.org/10.1234/...)
        timeout: Request timeout in seconds
        
    Returns:
        Final URL after following redirects, or None on failure
    """
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": "Mozilla/5.0 (compatible; research_agent/1.0)"
        }) as client:
            r = client.get(url)
            if r.is_success:
                final_url = str(r.url)
                if final_url != url:
                    logger.debug(f"Resolved DOI {url} -> {final_url}")
                return final_url
    except Exception as e:
        logger.debug(f"Failed to resolve DOI {url}: {e}")
        return None
    return None