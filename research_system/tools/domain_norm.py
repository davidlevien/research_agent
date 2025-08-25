"""Domain normalization for recognizing primary sources across aliases."""

from __future__ import annotations
from urllib.parse import urlparse

_PRIMARY_ALIASES = {
    # UNWTO family
    "unwto.org": {"unwto.org", "www.unwto.org", "e-unwto.org",
                  "pre-webunwto.s3.eu-west-1.amazonaws.com", "unwto-ap.org", "en.unwto-ap.org"},
    # IATA family
    "iata.org": {"iata.org", "www.iata.org", "data.iata.org"},
    # WTTC family
    "wttc.org": {"wttc.org", "www.wttc.org"},
    # OECD/IMF/WB/EC
    "oecd.org": {"oecd.org", "www.oecd.org", "data.oecd.org"},
    "imf.org": {"imf.org", "www.imf.org", "data.imf.org"},
    "worldbank.org": {"worldbank.org", "www.worldbank.org", "data.worldbank.org"},
    "ec.europa.eu": {"ec.europa.eu"},
    "who.int": {"who.int", "www.who.int", "data.who.int"},
    "un.org": {"un.org", "www.un.org", "data.un.org"},
}

# Build reverse map
_CANON = {alias: canon for canon, aliases in _PRIMARY_ALIASES.items() for alias in aliases}

PRIMARY_CANONICALS = set(_PRIMARY_ALIASES.keys())

def canonical_domain(url_or_domain: str) -> str:
    """Convert URL or domain to canonical form."""
    host = url_or_domain
    if "://" in (url_or_domain or ""):
        try:
            host = urlparse(url_or_domain).netloc
        except Exception:
            host = url_or_domain
    host = (host or "").lower()
    # strip port
    host = host.split(":")[0]
    return _CANON.get(host, host)

def is_primary_domain(url_or_domain: str) -> bool:
    """Check if domain is a primary source."""
    return canonical_domain(url_or_domain) in PRIMARY_CANONICALS