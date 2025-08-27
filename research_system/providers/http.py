"""HTTP utilities with rate limiting and API policy compliance."""

from __future__ import annotations
import httpx
import time
import os
from typing import Any, Dict, List, Optional
from collections import defaultdict
import logging
from urllib.parse import urlparse
from research_system.tools.log_redaction import redact_url, redact_headers, safe_log_params

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0, read=7.0)
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}

# Per-provider policies for compliance with API terms
POLICY = {
    "openalex": {
        "rps": 10,  # 10 requests per second
        "daily": 100_000,  # 100k requests per day
        "headers": lambda: {
            "User-Agent": "research-agent/1.0",
            "mailto": os.getenv("CONTACT_EMAIL", "research@example.com")
        }
    },
    "crossref": {
        "rps": 5,
        "headers": lambda: {
            "User-Agent": f"research-agent/1.0 (+mailto:{os.getenv('CONTACT_EMAIL', 'research@example.com')})"
        }
    },
    "unpaywall": {
        "rps": 5,
        "params": lambda: {
            "email": os.getenv("CONTACT_EMAIL", "research@example.com")
        }
    },
    "arxiv": {
        "min_interval_seconds": 3,  # At least 3 seconds between requests
        "headers": lambda: {
            "User-Agent": "research-agent/1.0"
        }
    },
    "pubmed": {
        "rps": 3,
        "params": lambda: {
            "tool": "research-agent",
            "email": os.getenv("CONTACT_EMAIL", "research@example.com")
        }
    },
    "europepmc": {
        "rps": 5,
        "headers": lambda: {
            "User-Agent": "research-agent/1.0"
        }
    },
    "oecd": {
        "rps": 3,
        "headers": lambda: {
            "User-Agent": "research-agent/1.0"
        }
    },
    "imf": {
        "rps": 3,
        "headers": lambda: {
            "User-Agent": "research-agent/1.0"
        }
    },
    "eurostat": {
        "rps": 3,
        "headers": lambda: {
            "User-Agent": "research-agent/1.0"
        }
    },
    "worldbank": {
        "rps": 10,
        "headers": lambda: {
            "User-Agent": "research-agent/1.0"
        }
    },
    "gdelt": {
        "rps": 5,
        "headers": lambda: {
            "User-Agent": "research-agent/1.0"
        }
    },
    "overpass": {
        "rps": 1,  # Be very courteous to Overpass
        "headers": lambda: {
            "User-Agent": "research-agent/1.0"
        }
    },
    "wikipedia": {
        "rps": 5,
        "headers": lambda: {
            "User-Agent": f"research-agent/1.0 ({os.getenv('CONTACT_EMAIL', 'research@example.com')})"
        }
    },
    "wikidata": {
        "rps": 5,
        "headers": lambda: {
            "User-Agent": f"research-agent/1.0 ({os.getenv('CONTACT_EMAIL', 'research@example.com')})"
        }
    },
    "wayback": {
        "rps": 2,
        "headers": lambda: {
            "User-Agent": "research-agent/1.0"
        }
    },
    "fred": {
        "rps": 5,
        "headers": lambda: {
            "User-Agent": "research-agent/1.0"
        }
    },
    "ec": {
        "rps": 3,
        "headers": lambda: {
            "User-Agent": "research-agent/1.0"
        }
    },
    "nominatim": {
        "rps": 1,  # OSM Nominatim usage policy
        "headers": lambda: {
            "User-Agent": f"research-agent/1.0 ({os.getenv('CONTACT_EMAIL', 'research@example.com')})"
        }
    },
    "wikivoyage": {
        "rps": 2,
        "headers": lambda: {
            "User-Agent": f"research-agent/1.0 ({os.getenv('CONTACT_EMAIL', 'research@example.com')})"
        }
    },
    "osmtags": {
        "rps": 0.5,  # Share Overpass API rate limit
        "headers": lambda: {
            "User-Agent": "research-agent/1.0"
        }
    }
}

# Track last call times for rate limiting
_last_call = defaultdict(float)
_daily_counts = defaultdict(int)
_daily_reset = defaultdict(float)

def _apply_policy(provider: str, method: str, url: str, *, params=None, headers=None):
    """Apply provider-specific policies for headers and rate limiting."""
    pol = POLICY.get(provider, {})
    
    # Check domain-specific policies for anti-bot handling
    parsed = urlparse(url)
    domain = parsed.netloc
    if domain:
        try:
            from research_system.tools.domain_policies import get_headers_for_domain, should_skip_domain
            
            # Check if we should skip this domain
            if should_skip_domain(domain):
                raise Exception(f"Domain {domain} requires authentication or has login wall")
            
            # Apply domain-specific headers
            domain_headers = get_headers_for_domain(domain)
            if domain_headers:
                headers = {**(headers or {}), **domain_headers}
                logger.debug(f"Applied domain policies for {domain}")
        except ImportError:
            pass  # Domain policies not available
    
    # Apply provider-specific headers (these take precedence)
    if "headers" in pol:
        provider_headers = pol["headers"]()
        headers = {**(headers or {}), **provider_headers}
    
    # Apply provider-specific params
    if "params" in pol:
        provider_params = pol["params"]()
        params = {**(params or {}), **provider_params}
    
    # Enforce minimum interval if configured
    min_iv = pol.get("min_interval_seconds")
    if min_iv:
        now = time.time()
        dt = now - _last_call[provider]
        if dt < min_iv:
            sleep_time = min_iv - dt
            logger.debug(f"Rate limiting {provider}: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        _last_call[provider] = time.time()
    
    # Enforce RPS limit if configured
    elif "rps" in pol:
        rps = pol["rps"]
        min_interval = 1.0 / rps
        now = time.time()
        dt = now - _last_call[provider]
        if dt < min_interval:
            sleep_time = min_interval - dt
            logger.debug(f"Rate limiting {provider}: sleeping {sleep_time:.2f}s (RPS={rps})")
            time.sleep(sleep_time)
        _last_call[provider] = time.time()
    
    # Check daily limit if configured
    if "daily" in pol:
        now = time.time()
        # Reset counter daily
        if now - _daily_reset[provider] > 86400:  # 24 hours
            _daily_counts[provider] = 0
            _daily_reset[provider] = now
        
        if _daily_counts[provider] >= pol["daily"]:
            raise Exception(f"Daily limit reached for {provider}: {pol['daily']} requests")
        
        _daily_counts[provider] += 1
    
    return params, headers

def http_json(
    method: str,
    url: str,
    params: Optional[Dict] = None,
    headers: Optional[Dict] = None,
    data: Optional[Any] = None,
    max_retries: int = 3
) -> Dict[str, Any]:
    """Make HTTP request with retries and return JSON response."""
    backoff = 0.5
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT, headers=headers) as client:
                response = client.request(method, url, params=params, json=data)
            
            if response.status_code in RETRY_STATUSES:
                raise httpx.HTTPStatusError(
                    f"Retryable status {response.status_code}",
                    request=response.request,
                    response=response
                )
            
            response.raise_for_status()
            return response.json()
            
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            last_error = e
            if attempt == max_retries:
                logger.warning(f"HTTP request failed after {max_retries} attempts: {redact_url(url)}")
                raise
            
            logger.debug(f"Retry {attempt}/{max_retries} for {redact_url(url)}: {e}")
            time.sleep(backoff)
            backoff *= 2
    
    raise last_error or Exception(f"Failed to complete request to {url}")

def http_json_with_policy(
    provider: str,
    method: str,
    url: str,
    params: Optional[Dict] = None,
    headers: Optional[Dict] = None,
    data: Optional[Any] = None,
    max_retries: int = 3
) -> Dict[str, Any]:
    """Make HTTP request with provider-specific policies applied."""
    params, headers = _apply_policy(
        provider, method, url,
        params=params,
        headers=headers
    )
    
    return http_json(
        method, url,
        params=params,
        headers=headers,
        data=data,
        max_retries=max_retries
    )