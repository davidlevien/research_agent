"""
Targeted Adaptive Research Expansion (AREX) - primary-first, bounded
"""

from __future__ import annotations
from typing import List, Dict, Any

PRIMARY_HINTS = [
    "site:unwto.org",
    "site:e-unwto.org",
    "site:iata.org",
    "site:wttc.org",
    "site:.gov",
    "site:.edu", 
    "site:doi.org",
    "filetype:pdf",
    "official statistics",
    "official data"
]

def build_arex_queries(
    entity: str, 
    metric: str, 
    period: str, 
    primary_domains: List[str]
) -> List[str]:
    """
    Build targeted AREX queries for a specific structured claim.
    Prioritizes primary domains and authoritative sources.
    
    Args:
        entity: Entity name (e.g., "global", "europe")
        metric: Metric name (e.g., "tourist_arrivals")
        period: Time period (e.g., "Q1 2025")
        primary_domains: List of primary domains sorted by trust
    
    Returns:
        List of search queries, max 6
    """
    base_terms = []
    
    # Build base query terms
    if entity:
        base_terms.append(entity)
    if metric:
        # Expand metric abbreviations
        metric_expanded = metric.replace("_", " ")
        base_terms.append(metric_expanded)
    if period:
        base_terms.append(period)
    
    base_query = " ".join(base_terms)
    queries = [base_query]
    
    # Add primary domain queries (top 3)
    for domain in primary_domains[:3]:
        queries.append(f"{base_query} site:{domain}")
    
    # Add generic primary hints
    for hint in PRIMARY_HINTS[:2]:
        queries.append(f"{base_query} {hint}")
    
    # Deduplicate while preserving order
    seen = set()
    out = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            out.append(q)
    
    return out[:6]  # Max 6 queries


def select_uncorroborated_keys(
    structured_claims: List[Dict[str, Any]], 
    triangulated_keys: set,
    max_keys: int = 2
) -> List[Dict[str, Any]]:
    """
    Select top uncorroborated structured claims for AREX expansion.
    
    Args:
        structured_claims: List of structured claim dicts with keys
        triangulated_keys: Set of already triangulated keys
        max_keys: Maximum number of keys to expand (default 2)
    
    Returns:
        List of uncorroborated claims to expand
    """
    # Find uncorroborated claims with structured keys
    uncorroborated = []
    for claim in structured_claims:
        key = claim.get("key")
        if key and key not in triangulated_keys:
            # Priority: claims with specific values > generic claims
            priority = 0
            if claim.get("value") is not None:
                priority = 1
            if claim.get("entity") and claim.get("period"):
                priority += 1
            
            uncorroborated.append({
                "claim": claim,
                "priority": priority
            })
    
    # Sort by priority (higher first)
    uncorroborated.sort(key=lambda x: x["priority"], reverse=True)
    
    # Return top N
    return [item["claim"] for item in uncorroborated[:max_keys]]


def build_arex_batch(
    uncorroborated_claims: List[Dict[str, Any]],
    primary_domains: List[str],
    max_queries_per_claim: int = 4
) -> List[str]:
    """
    Build a batch of AREX queries for multiple uncorroborated claims.
    
    Args:
        uncorroborated_claims: List of claims needing corroboration
        primary_domains: Trusted domains sorted by priority
        max_queries_per_claim: Max queries per claim (default 4)
    
    Returns:
        List of all queries to execute
    """
    all_queries = []
    
    for claim in uncorroborated_claims:
        entity = claim.get("entity", "")
        metric = claim.get("metric", "")
        period = claim.get("period", "")
        
        if metric:  # Must have at least a metric
            queries = build_arex_queries(
                entity, metric, period, primary_domains
            )
            all_queries.extend(queries[:max_queries_per_claim])
    
    return all_queries