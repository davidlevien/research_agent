"""Primary source corroboration backfill for triangulated families."""

from __future__ import annotations
from typing import Iterable, List, Dict, Any, Callable, Optional
from research_system.tools.domain_norm import PRIMARY_CANONICALS, canonical_domain
import logging

logger = logging.getLogger(__name__)

PRIMARY_SITES = [
    "site:unwto.org", "site:unwto-ap.org", "site:e-unwto.org",
    "site:wttc.org", "site:iata.org", "site:oecd.org",
    "site:imf.org", "site:worldbank.org", "site:ec.europa.eu",
    "site:who.int", "site:un.org"
]

def _queries_for_family(fam: Dict) -> List[str]:
    """Build tight queries from the representative claim/key if present."""
    key = fam.get("key") or fam.get("rep_claim") or ""
    parts = []
    # include numbers/period tokens if available
    if key:
        parts.append(key[:140])
    
    # Also try to use any specific metric patterns found
    import re
    metric_pattern = re.compile(r'\b(?:\d{1,3}(?:\.\d+)?%|Q[1-4]\s*\d{4}|\b20\d{2}\b|\bmillion\b|\bbillion\b)')
    metrics = metric_pattern.findall(key)
    if metrics:
        parts.extend(metrics[:2])  # Use first couple metrics
    
    queries = []
    for site in PRIMARY_SITES:
        for q in parts:
            if q.strip():
                queries.append(f"{q.strip()} {site}")
    return queries

def primary_fill_for_families(
    families: Iterable[Dict],
    topic: str,
    search_fn: Callable,
    extract_fn: Callable,
    k_per_family: int = 2
) -> List[Any]:
    """
    Fill triangulated families with primary sources where missing.
    
    Args:
        families: triangulated paraphrase clusters or structured triangles (post-filter)
        topic: Research topic for context
        search_fn: (query, n) -> list[SearchResult(url,title)]
        extract_fn: (url) -> Optional[EvidenceCard]
        k_per_family: Max cards to add per family
        
    Returns:
        list[EvidenceCard] (new primary source cards)
    """
    new_cards = []
    families_needing_primary = []
    
    # First identify families without primary sources
    for fam in families:
        fam_domains = {canonical_domain(d) for d in fam.get("domains", []) if d}
        if not (fam_domains & PRIMARY_CANONICALS):
            families_needing_primary.append(fam)
    
    if not families_needing_primary:
        logger.info("All triangulated families already have primary sources")
        return new_cards
    
    logger.info(f"Found {len(families_needing_primary)} families needing primary sources")
    
    for fam in families_needing_primary:
        family_cards_added = 0
        queries = _queries_for_family(fam)
        
        for q in queries[:5]:  # Limit queries per family
            if family_cards_added >= k_per_family:
                break
                
            try:
                results = search_fn(q, n=3)
            except Exception as e:
                logger.debug(f"Search error for query '{q}': {e}")
                continue
            
            for r in results:
                if family_cards_added >= k_per_family:
                    break
                    
                # Check if URL is from a primary domain
                if not r.url or canonical_domain(r.url) not in PRIMARY_CANONICALS:
                    continue
                
                try:
                    card = extract_fn(r.url)
                    if not card:
                        continue
                    
                    # Ensure canonical domain stored
                    card.source_domain = canonical_domain(card.source_domain or r.url)
                    card.metadata = card.metadata or {}
                    card.metadata["primary_fill"] = True
                    card.metadata["family_key"] = fam.get("key", "")[:100]
                    
                    new_cards.append(card)
                    family_cards_added += 1
                    logger.debug(f"Added primary source: {card.source_domain}")
                    
                except Exception as e:
                    logger.debug(f"Extraction error for {r.url}: {e}")
                    continue
    
    logger.info(f"Added {len(new_cards)} primary source cards across families")
    return new_cards

def dedup_merge(existing: List[Any], new: List[Any]) -> List[Any]:
    """
    Merge new cards into existing list, deduplicating by URL.
    
    Args:
        existing: Existing list of cards
        new: New cards to merge
        
    Returns:
        Merged list with duplicates removed
    """
    seen_urls = {c.url for c in existing if hasattr(c, 'url')}
    merged = list(existing)
    
    for card in new:
        if hasattr(card, 'url') and card.url not in seen_urls:
            merged.append(card)
            seen_urls.add(card.url)
    
    return merged