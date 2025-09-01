"""Domain-specific fetch policies for hardened HTTP fetching.

v8.26.0: Implements domain-specific headers, alt URLs, and fallback strategies.
"""

import os
from dataclasses import dataclass
from typing import Optional, Dict, Callable
from urllib.parse import urlparse

# Common user agent string
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")


@dataclass(frozen=True)
class DomainPolicy:
    """Policy for handling requests to specific domains."""
    headers: Dict[str, str]
    alt_url: Optional[Callable[[str], Optional[str]]] = None
    head_fallback_to_get: bool = True


def _oecd_alt(url: str) -> Optional[str]:
    """Provide alternative OECD endpoint if primary fails."""
    if "stats.oecd.org" in url:
        return url.replace("stats.oecd.org", "stats-nxd.oecd.org")
    return None


def _mastercard_alt(url: str) -> Optional[str]:
    """Provide alternative Mastercard endpoint."""
    # Sometimes their CDN requires different subdomain
    if "www.mastercard.com" in url:
        return url.replace("www.mastercard.com", "newsroom.mastercard.com")
    return None


# Domain-specific policies
POLICIES = {
    "sec.gov": DomainPolicy(
        headers={
            "User-Agent": UA + " " + (os.getenv("SEC_CONTACT", "research_agent/1.0 (contact: you@example.com)")),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate",
        },
        alt_url=None,
        head_fallback_to_get=True,
    ),
    "oecd.org": DomainPolicy(
        headers={
            "User-Agent": UA, 
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
        },
        alt_url=_oecd_alt,
        head_fallback_to_get=True,
    ),
    "mastercard.com": DomainPolicy(
        headers={
            "User-Agent": UA,
            "Referer": "https://www.mastercard.com/newsroom/",
            "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        alt_url=_mastercard_alt,
        head_fallback_to_get=True,
    ),
    "worldbank.org": DomainPolicy(
        headers={
            "User-Agent": UA,
            "Accept": "application/json,text/html,application/pdf,*/*;q=0.9",
            "Accept-Language": "en-US,en;q=0.9",
        },
        alt_url=None,
        head_fallback_to_get=True,
    ),
    "imf.org": DomainPolicy(
        headers={
            "User-Agent": UA,
            "Accept": "application/json,text/html,application/pdf,*/*;q=0.9",
            "Accept-Language": "en-US,en;q=0.9",
        },
        alt_url=None,
        head_fallback_to_get=True,
    ),
    "unwto.org": DomainPolicy(
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/pdf,*/*;q=0.9",
            "Accept-Language": "en-US,en;q=0.9",
        },
        alt_url=None,
        head_fallback_to_get=True,
    ),
    "wttc.org": DomainPolicy(
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/pdf,*/*;q=0.9", 
            "Accept-Language": "en-US,en;q=0.9",
        },
        alt_url=None,
        head_fallback_to_get=True,
    ),
}


def get_policy_for_url(url: str) -> Optional[DomainPolicy]:
    """Get the fetch policy for a given URL.
    
    Args:
        url: The URL to get policy for
        
    Returns:
        DomainPolicy if one exists for the domain, None otherwise
    """
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        
        # Check for exact domain matches and subdomains
        for domain, policy in POLICIES.items():
            if hostname == domain or hostname.endswith(f".{domain}"):
                return policy
                
        return None
    except Exception:
        return None


# Alias for backward compatibility
get_policy = get_policy_for_url


def apply_policy_headers(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Apply domain policy headers to a request.
    
    Args:
        url: The URL being requested
        headers: Existing headers to merge with
        
    Returns:
        Merged headers dictionary
    """
    policy = get_policy_for_url(url)
    
    if not policy:
        return headers or {}
    
    # Merge policy headers with provided headers (provided headers take precedence)
    merged = dict(policy.headers)
    if headers:
        merged.update(headers)
    
    return merged


def get_alt_url(url: str) -> Optional[str]:
    """Get alternative URL for a domain if available.
    
    Args:
        url: The original URL
        
    Returns:
        Alternative URL if available, None otherwise
    """
    policy = get_policy_for_url(url)
    
    if policy and policy.alt_url:
        return policy.alt_url(url)
    
    return None


def should_fallback_to_get(url: str) -> bool:
    """Check if HEAD should fallback to GET for this domain.
    
    Args:
        url: The URL being requested
        
    Returns:
        True if HEAD should fallback to GET on failure
    """
    policy = get_policy_for_url(url)
    return policy.head_fallback_to_get if policy else True