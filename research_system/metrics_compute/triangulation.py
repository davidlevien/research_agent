"""PE-grade triangulation metrics computation."""

from collections import Counter
from math import log
from typing import List, Dict, Any
from research_system.tools.domain_norm import canonical_domain, PRIMARY_CANONICALS


def compute_union_triangulation(filtered_para: List[Dict], structured: List[Dict], n_cards: int) -> float:
    """
    Calculate the union rate of triangulated evidence.
    
    This is the percentage of cards that are triangulated via either paraphrase or structure,
    where each cluster/triangle must have ≥2 distinct domains.
    
    Args:
        filtered_para: Filtered paraphrase clusters
        structured: Structured triangulation results
        n_cards: Total number of cards
        
    Returns:
        Union triangulation rate [0, 1]
    """
    def accept(item):
        """Accept only multi-domain clusters (using canonical domains)."""
        canonical_doms = {canonical_domain(d) for d in item.get("domains", []) if d}
        return len(canonical_doms) >= 2
    
    union = set()
    
    # Add indices from filtered paraphrase clusters
    for c in (filtered_para or []):
        if accept(c):
            union.update(c.get("indices", []))
    
    # Add indices from structured triangulation
    for t in (structured or []):
        if accept(t):
            union.update(t.get("indices", []))
    
    return len(union) / max(1, n_cards)


def provider_entropy(cards: List[Any]) -> float:
    """
    Calculate normalized Shannon entropy of provider distribution.
    
    Args:
        cards: List of evidence cards
        
    Returns:
        Normalized entropy [0, 1]
    """
    # Extract providers
    prov = []
    for c in cards:
        p = getattr(c, "provider", None) or c.get("provider")
        if p:
            prov.append(p)
    
    # Count occurrences
    counts = Counter(prov)
    N = sum(counts.values())
    
    if not counts or N == 0:
        return 0.0
    
    # Calculate Shannon entropy
    H = -sum((n/N) * log((n/N) + 1e-12) for n in counts.values())
    
    # Normalize by log(#providers) - but don't normalize when there's only one provider
    if len(counts) > 1:
        return H / log(len(counts))
    else:
        return 0.0  # Single provider = no diversity


def primary_share_in_triangulated(cards: List[Any], filtered_para: List[Dict], structured: List[Dict], 
                                  primary_domains: set = None) -> float:
    """
    Calculate the share of primary sources in triangulated evidence.
    
    Args:
        cards: List of evidence cards
        filtered_para: Filtered paraphrase clusters
        structured: Structured triangulation results
        primary_domains: Set of primary source domains (defaults to PRIMARY_CANONICALS)
        
    Returns:
        Primary share in triangulated evidence [0, 1]
    """
    # Use canonical primary domains if not specified
    if primary_domains is None:
        primary_domains = PRIMARY_CANONICALS
    
    # Get all triangulated indices (multi-domain only, using canonical domains)
    tri_indices = set()
    
    for c in (filtered_para or []):
        canonical_doms = {canonical_domain(d) for d in c.get("domains", []) if d}
        if len(canonical_doms) >= 2:
            tri_indices.update(c.get("indices", []))
    
    for t in (structured or []):
        canonical_doms = {canonical_domain(d) for d in t.get("domains", []) if d}
        if len(canonical_doms) >= 2:
            tri_indices.update(t.get("indices", []))
    
    if not tri_indices:
        return 0.0
    
    # Count primary sources in triangulated set
    primary_count = 0
    for idx in tri_indices:
        if idx < len(cards):
            card = cards[idx]
            domain = canonical_domain(getattr(card, "source_domain", None) or card.get("source_domain", ""))
            if domain in primary_domains:
                primary_count += 1
    
    return primary_count / len(tri_indices)


def label_finding(domains: List[str]) -> str:
    """
    Label a finding based on domain diversity.
    
    Args:
        domains: List of domains for this finding
        
    Returns:
        "Triangulated" if ≥2 distinct domains, "[Single-source]" otherwise
    """
    unique_domains = set(d.lower() for d in domains if d)
    return "Triangulated" if len(unique_domains) >= 2 else "[Single-source]"