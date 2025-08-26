"""Domain normalization for recognizing primary sources across aliases."""

from __future__ import annotations
from urllib.parse import urlparse
from pathlib import Path
import yaml
import re

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
PRIMARY_PATTERNS = []

def load_primary_domains():
    """Load primary domain configurations from YAML."""
    global PRIMARY_CANONICALS, PRIMARY_PATTERNS
    p = Path(__file__).resolve().parents[1] / "resources" / "primary_domains.yaml"
    if p.exists():
        cfg = yaml.safe_load(p.read_text())
        base = cfg.get("default", {})
        # Add canonical domains from config
        PRIMARY_CANONICALS |= set(base.get("canonical", []))
        # Compile patterns
        PRIMARY_PATTERNS[:] = [re.compile(x, re.I) for x in base.get("patterns", [])]
        # Return full config for pack-specific processing
        return cfg
    return {"default": {"canonical": list(PRIMARY_CANONICALS), "patterns": []}}

# Load primary domains on module init
PRIMARY_CONFIG = load_primary_domains()

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

def normalize_domain(url_or_domain: str) -> str:
    """Extract and normalize domain from URL or domain string."""
    host = url_or_domain
    if "://" in (url_or_domain or ""):
        try:
            host = urlparse(url_or_domain).netloc
        except Exception:
            host = url_or_domain
    host = (host or "").lower()
    # strip port
    host = host.split(":")[0]
    # strip www prefix for consistency
    if host.startswith("www."):
        host = host[4:]
    return host

def is_primary_domain(url_or_domain: str, additional_domains: set[str] = None, patterns: list = None) -> bool:
    """Check if domain is a primary source."""
    domain = canonical_domain(url_or_domain)
    
    # Check against primary canonicals and any additional domains
    domains_to_check = PRIMARY_CANONICALS
    if additional_domains:
        domains_to_check = domains_to_check | additional_domains
    
    if domain in domains_to_check:
        return True
    
    # Check against patterns
    patterns_to_check = patterns if patterns is not None else PRIMARY_PATTERNS
    for pattern in patterns_to_check:
        if pattern.search(domain):
            return True
    
    return False