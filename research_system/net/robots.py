"""Robots.txt compliance with allowlist for public resources."""
import httpx
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse
from typing import Set
import logging

logger = logging.getLogger(__name__)

# Public report domains that should always be accessible
PUBLIC_ALLOWLIST: Set[str] = {
    "unwto.org",
    "www.unwto.org",
    "iata.org",
    "www.iata.org",
    "wttc.org",
    "www.wttc.org",
    "weforum.org",
    "www.weforum.org",
    "oecd.org",
    "www.oecd.org",
    "worldbank.org",
    "www.worldbank.org",
    "imf.org",
    "www.imf.org",
    "who.int",
    "www.who.int",
    "unesco.org",
    "www.unesco.org",
    "un.org",
    "www.un.org"
}

# Cache of parsed robots.txt files
_ROBOTS_CACHE = {}


def is_allowed(url: str, user_agent: str = "ResearchAgent/1.0") -> bool:
    """Check if URL is allowed by robots.txt or is in allowlist.
    
    Args:
        url: URL to check
        user_agent: User agent string
        
    Returns:
        True if allowed to fetch
    """
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        
        # Check allowlist first
        if host in PUBLIC_ALLOWLIST:
            return True
        
        # Check robots.txt cache
        if host not in _ROBOTS_CACHE:
            robots_url = f"{parsed.scheme}://{host}/robots.txt"
            rp = RobotFileParser()
            rp.set_url(robots_url)
            
            try:
                # Fetch robots.txt with timeout
                r = httpx.get(robots_url, timeout=5, follow_redirects=True)
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                else:
                    # No robots.txt means allowed
                    rp.allow_all = True
            except Exception:
                # Can't fetch robots.txt = assume allowed
                rp.allow_all = True
            
            _ROBOTS_CACHE[host] = rp
        
        # Check if allowed
        rp = _ROBOTS_CACHE[host]
        if hasattr(rp, 'allow_all') and rp.allow_all:
            return True
        
        return rp.can_fetch(user_agent, url)
        
    except Exception as e:
        logger.debug(f"Robots check failed for {url}: {e}")
        # Default to allowed on error
        return True


def clear_cache():
    """Clear the robots.txt cache."""
    _ROBOTS_CACHE.clear()