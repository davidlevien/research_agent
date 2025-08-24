"""Domain diversity enforcement for balanced evidence selection."""

from collections import defaultdict
from typing import List, Any, Dict


def enforce_domain_cap(cards: List[Any], cap: float = 0.25) -> List[Any]:
    """
    Enforce a maximum percentage cap per domain to ensure diversity.
    
    Args:
        cards: List of evidence cards
        cap: Maximum fraction of cards from any single domain
        
    Returns:
        List of cards with domain caps enforced
    """
    if not cards:
        return cards
    
    N = len(cards)
    keep = []
    by_domain = defaultdict(list)
    
    # Group cards by domain
    for c in cards:
        by_domain[c.source_domain].append(c)
    
    # Calculate limit per domain
    limit = {}
    for domain, domain_cards in by_domain.items():
        # At least 1 card per domain, but cap at percentage
        limit[domain] = min(len(domain_cards), max(1, int(cap * N)))
    
    # Keep highest-ranked within each domain
    for domain, arr in by_domain.items():
        # Sort by rank (or credibility if rank not available)
        sorted_cards = sorted(
            arr, 
            key=lambda x: -getattr(x, "rank", getattr(x, "credibility_score", 0))
        )
        keep.extend(sorted_cards[:limit[domain]])
    
    return keep if keep else cards


def calculate_domain_share(cards: List[Any], domain: str) -> float:
    """
    Calculate the share of cards from a specific domain.
    
    Args:
        cards: List of evidence cards
        domain: Domain to check
        
    Returns:
        Fraction of cards from the specified domain
    """
    if not cards:
        return 0.0
    
    count = sum(1 for c in cards if c.source_domain == domain)
    return count / len(cards)


def fetch_diversity_fill(topic: str, target_domains: List[str]) -> List[Dict]:
    """
    Fetch additional cards from specific domains for diversity.
    
    Args:
        topic: Research topic
        target_domains: List of domains to target
        
    Returns:
        List of search queries for diversity fill
    """
    queries = []
    
    # Build targeted queries for each domain
    for domain in target_domains:
        queries.append({
            "query": f"site:{domain} {topic}",
            "domain": domain,
            "priority": "diversity_fill"
        })
    
    return queries


def dedup_merge(existing: List[Any], new: List[Any]) -> List[Any]:
    """
    Merge new cards into existing list, deduplicating by URL.
    
    Args:
        existing: Existing list of cards
        new: New cards to merge
        
    Returns:
        Merged list with duplicates removed
    """
    seen_urls = {c.url for c in existing}
    merged = list(existing)
    
    for card in new:
        if card.url not in seen_urls:
            merged.append(card)
            seen_urls.add(card.url)
    
    return merged