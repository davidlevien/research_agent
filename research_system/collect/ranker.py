"""
Evidence ranking with domain quality and popularity priors
"""

from typing import Any, Optional
from .filter import PRIMARY, domain_quality_score

def popularity_prior(domain: str) -> float:
    """
    Simple popularity prior based on domain.
    In production, this could use Tranco or similar ranking.
    """
    # Well-known high-traffic sites
    popular = {
        "nytimes.com": 0.8,
        "bbc.com": 0.8,
        "reuters.com": 0.85,
        "bloomberg.com": 0.8,
        "ft.com": 0.8,
        "wsj.com": 0.8,
        "economist.com": 0.75,
        "nature.com": 0.9,
        "science.org": 0.9,
        "arxiv.org": 0.85
    }
    
    if domain and domain.lower() in popular:
        return popular[domain.lower()]
    
    # Default bounded prior
    return 0.6

def rank_evidence(card: Any) -> float:
    """
    Rank an evidence card based on multiple factors.
    Returns a score between 0 and 1.
    """
    # Base score from card's own metrics
    base = (
        0.6 * getattr(card, "relevance_score", 0.5) +
        0.3 * getattr(card, "credibility_score", 0.5) +
        0.1 * getattr(card, "recency_score", 0.5)
    )
    
    domain = getattr(card, "source_domain", "")
    
    # Primary source boost
    if domain in PRIMARY:
        base += 0.06
    
    # Domain quality adjustment
    quality = domain_quality_score(domain)
    base = base * 0.7 + quality * 0.3
    
    # Popularity adjustment (smaller weight)
    pop = popularity_prior(domain)
    base += 0.1 * (pop - 0.5)
    
    # Ensure within bounds
    return max(0.0, min(1.0, base))

def rerank_cards(cards: list) -> list:
    """
    Rerank evidence cards using enhanced scoring.
    Returns sorted list with highest quality first.
    """
    return sorted(cards, key=rank_evidence, reverse=True)