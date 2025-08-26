"""Domain-specific fetch policies for anti-bot handling."""

from typing import Dict, Any, Optional

# Domain-specific policies to handle anti-bot measures
DOMAIN_POLICIES: Dict[str, Dict[str, Any]] = {
    "www.sec.gov": {
        "headers": {
            "User-Agent": "ResearchAgent/8.4 (research@example.com); academic research",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        },
        "robots": "respect",
        "rate_limit": "10/min",
        "skip_if_403": True,  # Mark as unreachable to avoid loops
        "description": "SEC requires proper User-Agent with contact info"
    },
    
    "reports.weforum.org": {
        "headers": {
            "Referer": "https://reports.weforum.org/",
            "User-Agent": "Mozilla/5.0 (compatible; ResearchAgent/8.4; +https://example.com)"
        },
        "head_ok": False,  # Go straight to GET; HEAD tends to 404
        "description": "WEF needs Referer header, HEAD requests often fail"
    },
    
    "www.weforum.org": {
        "headers": {
            "Referer": "https://www.weforum.org/",
            "User-Agent": "Mozilla/5.0 (compatible; ResearchAgent/8.4)"
        },
        "head_ok": False
    },
    
    "www.mastercard.com": {
        "headers": {
            "Referer": "https://www.mastercard.com/",
            "User-Agent": "Mozilla/5.0 (compatible; ResearchAgent/8.4)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        },
        "description": "Mastercard blocks without proper Referer"
    },
    
    "www.statista.com": {
        "login_wall": True,  # Early exit when /sso/authorize|/iplogin detected
        "skip_if_auth": True,
        "description": "Statista has aggressive login walls, skip if auth detected"
    },
    
    # Additional common domains with anti-bot
    "www.bloomberg.com": {
        "headers": {
            "User-Agent": "Mozilla/5.0 (compatible; ResearchAgent/8.4)"
        },
        "paywall": True
    },
    
    "www.ft.com": {
        "paywall": True,
        "headers": {
            "User-Agent": "Mozilla/5.0 (compatible; ResearchAgent/8.4)"
        }
    },
    
    "www.wsj.com": {
        "paywall": True,
        "headers": {
            "User-Agent": "Mozilla/5.0 (compatible; ResearchAgent/8.4)"
        }
    }
}

def get_domain_policy(domain: str) -> Dict[str, Any]:
    """Get fetch policy for a domain."""
    # Direct match first
    if domain in DOMAIN_POLICIES:
        return DOMAIN_POLICIES[domain]
    
    # Check if it's a subdomain
    for policy_domain, policy in DOMAIN_POLICIES.items():
        if domain.endswith(policy_domain):
            return policy
    
    # Default policy
    return {
        "headers": {
            "User-Agent": "ResearchAgent/8.4 (mailto:research@example.com)"
        }
    }

def should_skip_domain(domain: str, response_code: Optional[int] = None) -> bool:
    """Check if we should skip a domain based on policy."""
    policy = get_domain_policy(domain)
    
    # Skip if login wall detected
    if policy.get("login_wall"):
        return True
    
    # Skip on 403 if policy says so
    if response_code == 403 and policy.get("skip_if_403"):
        return True
    
    return False

def get_headers_for_domain(domain: str) -> Dict[str, str]:
    """Get appropriate headers for a domain."""
    policy = get_domain_policy(domain)
    return policy.get("headers", {
        "User-Agent": "ResearchAgent/8.4 (mailto:research@example.com)"
    })