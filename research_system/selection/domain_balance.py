from __future__ import annotations
from collections import Counter, defaultdict
from typing import List, Iterable, Dict, Tuple, Set
from dataclasses import dataclass
from research_system.tools.domain_norm import canonical_domain

@dataclass(frozen=True)
class BalanceConfig:
    cap: float = 0.25           # ≤ 25% per domain
    min_cards: int = 24         # target floor; triggers backfill if trimmed
    prefer_primary: bool = True # when backfilling, prefer primary institutions

# Domain families for grouping related domains
DOMAIN_FAMILIES = {
    "nps": {"nps.gov", "npshistory.com"},
    "usgs": {"usgs.gov"},
    "gov": {"*.gov"},  # Wildcard for any .gov domain
    "edu": {"*.edu"},  # Wildcard for any .edu domain
    "econ": {"worldbank.org", "oecd.org", "imf.org", "wto.org", "bis.org"},
    "eu": {"data.europa.eu", "ec.europa.eu", "eurostat.ec.europa.eu", "ecb.europa.eu"},
    "un": {"un.org", "unctad.org", "who.int"},
}

# Intent-based primary pools
PRIMARY_POOLS_BY_INTENT = {
    "encyclopedia": {"nps.gov", "usgs.gov", "loc.gov", "archives.gov", "congress.gov", "gpo.gov"},
    "policy": {"federalregister.gov", "regulations.gov", "ec.europa.eu"},
    "stats": {"census.gov", "bls.gov", "bea.gov", "data.gov"},
    "macroecon": {"imf.org", "worldbank.org", "oecd.org", "wto.org", "bis.org"},
    "academic": {"*.edu", "arxiv.org", "ncbi.nlm.nih.gov", "pubmed.gov"},
    "medical": {"nih.gov", "cdc.gov", "who.int", "pubmed.gov"},
    "news": {},  # No specific primary sources for news
    "generic": {"*.gov", "*.edu"},  # Generic government and education sources
}

# Default pool for backward compatibility
PRIMARY_POOL: Set[str] = PRIMARY_POOLS_BY_INTENT.get("macroecon", set())

def get_primary_pool_for_intent(intent: str) -> Set[str]:
    """Get the primary pool for a specific intent"""
    return PRIMARY_POOLS_BY_INTENT.get(intent, PRIMARY_POOLS_BY_INTENT["generic"])

def is_primary_source(domain: str, intent: str = "generic") -> bool:
    """Check if a domain is a primary source for the given intent"""
    primary_pool = get_primary_pool_for_intent(intent)
    
    # Check exact match first
    if domain in primary_pool:
        return True
    
    # Check wildcard patterns
    for pattern in primary_pool:
        if pattern.startswith("*."):
            suffix = pattern[1:]  # Remove the *
            if domain.endswith(suffix):
                return True
    
    return False

def get_domain_family(domain: str) -> str:
    """Get the family name for a domain"""
    for family_name, domains in DOMAIN_FAMILIES.items():
        if domain in domains:
            return family_name
        # Check wildcards
        for pattern in domains:
            if pattern.startswith("*."):
                suffix = pattern[1:]
                if domain.endswith(suffix):
                    return family_name
    return domain  # Return the domain itself if no family found

def _domain(card) -> str:
    return canonical_domain(getattr(card, "source_domain", "") or "")

def enforce_cap(cards: List, cfg: BalanceConfig) -> Tuple[List, Dict[str,int]]:
    """
    Enforce domain cap with family-aware grouping.
    Prioritizes triangulated cards and respects domain families.
    """
    n = len(cards) or 1
    # Calculate absolute cap: floor of 25% of total cards
    cap_abs = max(1, int(cfg.cap * n))
    
    # Group by domain families instead of raw domains
    family_cards = defaultdict(list)
    for c in cards:
        d = _domain(c)
        family = get_domain_family(d)
        family_cards[family].append(c)
    
    keep: List = []
    kept_per_family = defaultdict(int)
    
    # Sort cards within each family by triangulation status and credibility
    for family, family_card_list in family_cards.items():
        # Sort by: triangulated first, then by credibility
        sorted_cards = sorted(
            family_card_list,
            key=lambda c: (
                -int(getattr(c, 'is_triangulated', False)),  # Triangulated cards first
                -getattr(c, 'credibility_score', 0)  # Then by credibility
            )
        )
        
        # Keep up to cap from this family
        for c in sorted_cards:
            if kept_per_family[family] < cap_abs:
                keep.append(c)
                kept_per_family[family] += 1
    
    # For backward compat, also track raw domains
    kept_per_domain = defaultdict(int)
    for c in keep:
        d = _domain(c)
        kept_per_domain[d] += 1
    
    return keep, dict(kept_per_domain)

def enforce_domain_cap(cards: List, cap: float = 0.25, use_families: bool = True) -> List:
    """
    Enforce a maximum percentage cap per domain/family to ensure diversity.
    Uses triangulation status and credibility-based sorting to keep best cards.
    
    Args:
        cards: List of evidence cards
        cap: Maximum fraction of cards from any single domain/family
        use_families: If True, group by families; if False, use raw domains
        
    Returns:
        List of cards with domain caps enforced
    """
    if not cards:
        return cards
    
    N = len(cards)
    keep = []
    
    if use_families:
        # Group by domain families
        by_family = defaultdict(list)
        for c in cards:
            canon = canonical_domain(getattr(c, "source_domain", ""))
            family = get_domain_family(canon)
            by_family[family].append(c)
        
        # Calculate limit per family
        limit = {}
        for family, family_cards in by_family.items():
            # At least 1 card per family, but cap at percentage
            limit[family] = min(len(family_cards), max(1, int(cap * N)))
        
        # Keep highest-ranked within each family
        for family, arr in by_family.items():
            # Sort by: triangulated first, then rank/credibility
            sorted_cards = sorted(
                arr,
                key=lambda x: (
                    -int(getattr(x, "is_triangulated", False)),  # Triangulated cards first
                    -(getattr(x, "rank", None) or getattr(x, "credibility_score", 0))
                )
            )
            keep.extend(sorted_cards[:limit[family]])
    else:
        # Original domain-based grouping (backward compat)
        by_domain = defaultdict(list)
        for c in cards:
            canon = canonical_domain(getattr(c, "source_domain", ""))
            by_domain[canon].append(c)
        
        # Calculate limit per domain
        limit = {}
        for domain, domain_cards in by_domain.items():
            limit[domain] = min(len(domain_cards), max(1, int(cap * N)))
        
        # Keep highest-ranked within each domain
        for domain, arr in by_domain.items():
            sorted_cards = sorted(
                arr, 
                key=lambda x: -(getattr(x, "rank", None) or getattr(x, "credibility_score", 0))
            )
            keep.extend(sorted_cards[:limit[domain]])
    
    return keep if keep else cards

def need_backfill(cards: List, cfg: BalanceConfig) -> bool:
    return len(cards) < cfg.min_cards

def backfill_queries(topic: str) -> Iterable[str]:
    # Simple, cheap related-topic expansion: add synonyms for macro
    seeds = [
        topic,
        f"{topic} site:oecd.org", f"{topic} site:imf.org", f"{topic} site:data.europa.eu",
        f"{topic} site:eurostat.ec.europa.eu", f"{topic} site:unctad.org", f"{topic} site:wto.org",
        f"{topic} site:ecb.europa.eu", f"{topic} site:bis.org"
    ]
    # unique order
    seen = set()
    for q in seeds:
        if q not in seen:
            seen.add(q); yield q

def backfill(cards: List, topic: str, search_fn, to_cards_fn, cfg: BalanceConfig) -> List:
    have = {_domain(c) for c in cards}
    additions: List = []
    for q in backfill_queries(topic):
        rows = search_fn(q)
        seeds = to_cards_fn(rows) if to_cards_fn else rows
        for s in seeds:
            d = canonical_domain(s.get("source_domain",""))
            if d in have and d not in PRIMARY_POOL:
                continue  # prefer new primaries
            additions.append(s)
        if len(cards) + len(additions) >= cfg.min_cards:
            break
    return additions