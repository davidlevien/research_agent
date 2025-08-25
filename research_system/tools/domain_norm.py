"""Domain normalization for primary source recognition."""

from __future__ import annotations
from urllib.parse import urlparse

# Primary domain families with all their aliases
_PRIMARY_ALIASES = {
    # UNWTO family
    "unwto.org": {
        "unwto.org", "www.unwto.org", "e-unwto.org", "www.e-unwto.org",
        "pre-webunwto.s3.eu-west-1.amazonaws.com", 
        "unwto-ap.org", "en.unwto-ap.org", "www.unwto-ap.org"
    },
    # IATA family
    "iata.org": {
        "iata.org", "www.iata.org", "data.iata.org", 
        "publications.iata.org", "api.iata.org"
    },
    # WTTC family
    "wttc.org": {
        "wttc.org", "www.wttc.org", "research.wttc.org"
    },
    # World Bank family
    "worldbank.org": {
        "worldbank.org", "www.worldbank.org", "data.worldbank.org",
        "documents.worldbank.org", "openknowledge.worldbank.org"
    },
    # IMF family
    "imf.org": {
        "imf.org", "www.imf.org", "data.imf.org"
    },
    # OECD family
    "oecd.org": {
        "oecd.org", "www.oecd.org", "data.oecd.org", "stats.oecd.org"
    },
    # European Commission
    "ec.europa.eu": {
        "ec.europa.eu", "data.europa.eu"
    },
    # WHO family
    "who.int": {
        "who.int", "www.who.int", "data.who.int"
    },
    # UN family
    "un.org": {
        "un.org", "www.un.org", "data.un.org", "unstats.un.org"
    },
}

# Build reverse lookup map: alias -> canonical
_CANON = {}
for canon, aliases in _PRIMARY_ALIASES.items():
    for alias in aliases:
        _CANON[alias] = canon

# Set of canonical primary domains
PRIMARY_CANONICALS = set(_PRIMARY_ALIASES.keys())


def canonical_domain(url_or_domain: str) -> str:
    """
    Normalize a URL or domain to its canonical primary form.
    
    Args:
        url_or_domain: URL string or domain name
        
    Returns:
        Canonical domain if it's a primary alias, otherwise the cleaned domain
    """
    if not url_or_domain:
        return ""
    
    host = url_or_domain
    
    # Extract hostname from URL if needed
    if "://" in url_or_domain:
        try:
            parsed = urlparse(url_or_domain)
            host = parsed.netloc
        except Exception:
            host = url_or_domain
    
    # Clean and normalize
    host = (host or "").lower().strip()
    
    # Remove port if present
    if ":" in host:
        host = host.split(":")[0]
    
    # Remove www. prefix for non-primary lookups
    # (but keep it for the alias map lookup first)
    canonical = _CANON.get(host)
    if canonical:
        return canonical
    
    # Try without www. if not found
    if host.startswith("www."):
        host_no_www = host[4:]
        canonical = _CANON.get(host_no_www)
        if canonical:
            return canonical
    
    # Return cleaned domain if not a known primary
    return host


def is_primary_domain(url_or_domain: str) -> bool:
    """Check if a URL/domain is a primary source."""
    return canonical_domain(url_or_domain) in PRIMARY_CANONICALS


def get_primary_search_sites() -> list[str]:
    """Get site: search operators for all primary domains."""
    sites = []
    for aliases in _PRIMARY_ALIASES.values():
        # Use the most common variants for search
        for alias in list(aliases)[:3]:  # Top 3 aliases per family
            sites.append(f"site:{alias}")
    return sites