"""Primary source backfill for triangulated families."""

from __future__ import annotations
from typing import Iterable, List, Dict, Any, Optional, Callable
import logging
from research_system.tools.domain_norm import PRIMARY_CANONICALS, canonical_domain, get_primary_search_sites

logger = logging.getLogger(__name__)


def _queries_for_family(fam: Dict, topic: str) -> List[str]:
    """Build targeted queries for finding primary sources for a family."""
    queries = []
    
    # Extract key information from the family
    key = fam.get("key", "")
    rep_claim = fam.get("representative_claim", "")
    
    # Use the most specific information available
    if key:
        # Structured key like "global|tourist_arrivals|2024"
        parts = key.split("|")
        if len(parts) >= 3:
            entity, metric, period = parts[:3]
            # Build query from components
            query_base = f"{entity} {metric.replace('_', ' ')} {period}"
        else:
            query_base = key
    elif rep_claim:
        # Use first 100 chars of representative claim
        query_base = rep_claim[:100]
    else:
        # Fallback to topic
        query_base = topic
    
    # Add site restrictions for primary sources
    primary_sites = get_primary_search_sites()[:6]  # Top 6 primary site operators
    
    for site in primary_sites:
        queries.append(f"{query_base} {site}")
    
    return queries


def primary_fill_for_families(
    families: Iterable[Dict],
    topic: str,
    search_fn: Callable,
    extract_fn: Callable,
    k_per_family: int = 2
) -> List[Any]:
    """
    Add primary source cards for families that lack them.
    
    Args:
        families: Triangulated paraphrase clusters or structured triangles (post-filter)
        topic: Research topic for fallback queries
        search_fn: Function (query, n) -> list[SearchResult(url, title)]
        extract_fn: Function (url) -> Optional[EvidenceCard]
        k_per_family: Max new cards to add per family
        
    Returns:
        List of new evidence cards from primary sources
    """
    new_cards = []
    processed_urls = set()
    
    for i, fam in enumerate(families):
        # Check if family already has a primary source
        fam_domains = {canonical_domain(d) for d in fam.get("domains", []) if d}
        
        if fam_domains & PRIMARY_CANONICALS:
            logger.debug(f"Family {i} already has primary source(s): {fam_domains & PRIMARY_CANONICALS}")
            continue
        
        logger.info(f"Family {i} needs primary source. Current domains: {fam_domains}")
        
        # Try targeted queries
        queries = _queries_for_family(fam, topic)
        cards_added = 0
        
        for query in queries:
            if cards_added >= k_per_family:
                break
                
            try:
                logger.debug(f"Searching: {query}")
                results = search_fn(query, n=3)
            except Exception as e:
                logger.warning(f"Search failed for '{query}': {e}")
                continue
            
            for result in results:
                if cards_added >= k_per_family:
                    break
                    
                # Check if URL is from a primary domain
                url_domain = canonical_domain(result.url)
                if url_domain not in PRIMARY_CANONICALS:
                    continue
                
                # Skip already processed URLs
                if result.url in processed_urls:
                    continue
                    
                processed_urls.add(result.url)
                
                try:
                    # Extract evidence from the URL
                    card = extract_fn(result.url)
                    
                    if not card:
                        logger.debug(f"No content extracted from {result.url}")
                        continue
                    
                    # Ensure canonical domain is stored
                    card.source_domain = canonical_domain(card.source_domain)
                    card.is_primary_source = True
                    
                    # Add relevance context
                    if not hasattr(card, 'related_reason'):
                        card.related_reason = f"primary_backfill_family_{i}"
                    
                    new_cards.append(card)
                    cards_added += 1
                    
                    logger.info(f"Added primary source card from {url_domain} for family {i}")
                    
                except Exception as e:
                    logger.warning(f"Failed to extract from {result.url}: {e}")
                    continue
        
        if cards_added == 0:
            logger.warning(f"Could not find primary source for family {i}")
    
    logger.info(f"Primary backfill complete: added {len(new_cards)} cards")
    return new_cards


def needs_primary_backfill(metrics: Dict[str, float], threshold: float = 0.50) -> bool:
    """Check if primary backfill is needed based on metrics."""
    current = metrics.get("primary_share_in_union", 0.0)
    return current < threshold