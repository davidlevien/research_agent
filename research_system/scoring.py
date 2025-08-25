"""
Scoring and confidence recalibration based on domain authority and triangulation
"""

from __future__ import annotations
from typing import Optional

# Domain credibility priors based on authority and primary source status
DOMAIN_PRIOR = {
    # International organizations (highest trust)
    "unwto.org": 0.95,
    "wttc.org": 0.90,
    "iata.org": 0.90,
    "oecd.org": 0.90,
    "ec.europa.eu": 0.90,
    "eurostat.ec.europa.eu": 0.90,
    "worldbank.org": 0.90,
    "imf.org": 0.90,
    "un.org": 0.90,
    "who.int": 0.90,
    
    # Government and official statistics
    "ustravel.org": 0.88,
    ".gov": 0.85,  # Generic government domains
    ".edu": 0.80,  # Academic institutions
    ".ac.uk": 0.80,
    
    # Industry research firms
    "str.com": 0.88,
    "costar.com": 0.88,
    "statista.com": 0.85,
    "gartner.com": 0.85,
    "forrester.com": 0.85,
    "mckinsey.com": 0.85,
    "bcg.com": 0.85,
    "deloitte.com": 0.85,
    "pwc.com": 0.85,
    
    # Industry media (trusted)
    "skift.com": 0.82,
    "phocuswright.com": 0.80,
    "traveldailynews.com": 0.75,
    
    # Industry portals (secondary)
    "hospitalitynet.org": 0.65,
    "travelpulse.com": 0.65,
    "travelweekly.com": 0.65,
    
    # Vendor/blog sites (lower trust)
    "revfine.com": 0.60,
    "coaxsoft.com": 0.60,
    "blog.": 0.55,  # Generic blog subdomains
    
    # Default for unknown
    "unknown": 0.50
}

def domain_prior(domain: str) -> float:
    """
    Get credibility prior for a domain.
    Checks exact match first, then suffix patterns.
    """
    if not domain:
        return 0.50
    
    domain_lower = domain.lower().strip()
    
    # Check exact match
    if domain_lower in DOMAIN_PRIOR:
        return DOMAIN_PRIOR[domain_lower]
    
    # Check suffix patterns
    for pattern, score in DOMAIN_PRIOR.items():
        if pattern.startswith(".") and domain_lower.endswith(pattern):
            return score
        if pattern.endswith(".") and domain_lower.startswith(pattern):
            return score
    
    # Default
    return 0.50

def recompute_confidence(
    card,
    triangulated: bool,
    recency_days: Optional[int] = None
) -> float:
    """
    Recompute confidence score based on:
    - Domain authority (40%)
    - Triangulation status (40%)
    - Recency (20%)
    
    Returns confidence score between 0.0 and 1.0
    """
    # Weights for each factor
    w_domain = 0.4
    w_triangulation = 0.4
    w_recency = 0.2
    
    # Domain score
    domain = getattr(card, "source_domain", "unknown")
    domain_score = domain_prior(domain)
    
    # Triangulation score
    triangulation_score = 1.0 if triangulated else 0.0
    
    # Recency score
    if recency_days is not None:
        if recency_days <= 30:
            recency_score = 1.0
        elif recency_days <= 90:
            recency_score = 0.8
        elif recency_days <= 180:
            recency_score = 0.6
        elif recency_days <= 365:
            recency_score = 0.4
        else:
            recency_score = 0.2
    else:
        recency_score = 0.5  # Unknown date
    
    # Compute weighted confidence
    confidence = (
        w_domain * domain_score +
        w_triangulation * triangulation_score +
        w_recency * recency_score
    )
    
    return min(1.0, max(0.0, confidence))


def domain_prior_for(topic: str, url: str) -> float:
    """
    Get domain prior for a URL based on the topic's discipline.
    Uses discipline-specific domain priors from policy.
    
    Args:
        topic: Research topic string
        url: URL to evaluate
        
    Returns:
        Domain credibility score (0-1)
    """
    from .routing.topic_router import route_topic
    from .policy import get_policy
    from .tools.url_norm import domain_of
    
    # Route topic to discipline
    discipline = route_topic(topic)
    
    # Get policy for discipline
    policy = get_policy(discipline)
    
    # Extract domain from URL
    domain = domain_of(url)
    
    # Look up domain in policy priors
    return policy.domain_priors.get(domain, 0.5)


def recompute_confidence_with_discipline(
    card,
    topic: str,
    triangulated: bool,
    recency_days: Optional[int] = None
) -> float:
    """
    Recompute confidence using discipline-aware domain priors.
    
    Args:
        card: Evidence card
        topic: Research topic (for discipline routing)
        triangulated: Whether claim is triangulated
        recency_days: Age of source in days
        
    Returns:
        Confidence score (0-1)
    """
    # Weights for each factor
    w_domain = 0.4
    w_triangulation = 0.4
    w_recency = 0.2
    
    # Domain score using discipline-specific priors
    url = getattr(card, "url", None) or getattr(card, "source_url", "")
    domain_score = domain_prior_for(topic, url) if url else 0.5
    
    # Triangulation score
    triangulation_score = 1.0 if triangulated else 0.0
    
    # Recency score
    if recency_days is not None:
        if recency_days <= 30:
            recency_score = 1.0
        elif recency_days <= 90:
            recency_score = 0.8
        elif recency_days <= 180:
            recency_score = 0.6
        elif recency_days <= 365:
            recency_score = 0.4
        else:
            recency_score = 0.2
    else:
        recency_score = 0.5  # Unknown date
    
    # Compute weighted confidence
    confidence = (
        w_domain * domain_score +
        w_triangulation * triangulation_score +
        w_recency * recency_score
    )
    
    return min(1.0, max(0.0, confidence))