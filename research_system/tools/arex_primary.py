"""
Targeted AREX expansion for primary sources
"""

from typing import List, Dict, Any, Optional, Set
import asyncio
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

# Primary source domains across disciplines
PRIMARY_DOMAINS = {
    "unwto.org", "e-unwto.org", "iata.org", "wttc.org", 
    "oecd.org", "worldbank.org", "imf.org", "ec.europa.eu",
    "who.int", "un.org", "unesco.org", "ilo.org",
    "federalreserve.gov", "ecb.europa.eu", "bis.org",
    "nature.com", "science.org", "nejm.org", "thelancet.com"
}

def key_has_primary(triangle: Dict[str, Any]) -> bool:
    """Check if a triangulated key already has primary source coverage"""
    return any(d in PRIMARY_DOMAINS for d in triangle.get("domains", []))

def filter_primary_first(cards: List[Any]) -> List[Any]:
    """Filter cards to keep only primary sources"""
    return [c for c in cards if c.source_domain in PRIMARY_DOMAINS]

def build_gap_queries(key_parts: Dict[str, Optional[str]]) -> List[str]:
    """Build targeted queries for primary sources based on key components"""
    entity = key_parts.get("entity", "")
    metric = key_parts.get("metric", "")
    period = key_parts.get("period", "")
    
    # Build base query from non-None parts
    parts = [p for p in [entity, metric, period] if p]
    base = " ".join(parts) if parts else ""
    
    if not base:
        return []
    
    queries = []
    
    # Target specific primary sources based on metric type
    if "tourism" in metric.lower() or "arrival" in metric.lower():
        queries.append(f"{base} site:unwto.org")
        queries.append(f"{base} site:wttc.org")
    
    if "passenger" in metric.lower() or "aviation" in metric.lower():
        queries.append(f"{base} site:iata.org")
    
    if "gdp" in metric.lower() or "economic" in metric.lower():
        queries.append(f"{base} site:oecd.org")
        queries.append(f"{base} site:worldbank.org")
    
    # Always try major international orgs
    queries.append(f"{base} site:un.org")
    
    # Add negative terms to avoid low-quality sources
    for i in range(len(queries)):
        queries[i] += " -site:wikipedia.org -site:statista.com"
    
    return queries[:4]  # Limit to 4 queries per gap

async def targeted_primary_arex(
    cards: List[Any],
    structured_triangles: List[Dict],
    registry: Any,
    providers: List[str],
    settings: Any,
    max_gaps: int = 3,
    max_new_cards: int = 20
) -> List[Any]:
    """
    Perform targeted AREX expansion for uncorroborated keys lacking primary sources.
    Returns enriched list of cards.
    """
    from research_system.collection_enhanced import parallel_provider_search
    from research_system.models import EvidenceCard
    from research_system.tools.url_norm import domain_of
    from research_system.policy import POLICIES
    from research_system.routing.topic_router import route_topic
    
    # Identify gaps: keys without primary source corroboration
    gaps = []
    for tri in structured_triangles:
        if not key_has_primary(tri):
            gaps.append({
                "key": tri.get("key"),
                "entity": tri.get("entity"),
                "metric": tri.get("metric"),
                "period": tri.get("period")
            })
    
    if not gaps:
        logger.info("All structured triangles have primary source coverage")
        return cards
    
    logger.info(f"Found {len(gaps)} uncorroborated keys without primary sources")
    
    # Process up to max_gaps
    new_cards = []
    for gap in gaps[:max_gaps]:
        if len(new_cards) >= max_new_cards:
            break
            
        queries = build_gap_queries(gap)
        logger.info(f"AREX for key {gap['key']}: {len(queries)} queries")
        
        for query in queries:
            if len(new_cards) >= max_new_cards:
                break
                
            try:
                # Execute search
                search_results = await parallel_provider_search(
                    registry, 
                    query=query, 
                    count=4,
                    freshness=getattr(settings, "FRESHNESS_WINDOW", 90),
                    region="US"
                )
                
                # Process results, prioritizing primary sources
                for provider, hits in search_results.items():
                    for h in hits:
                        domain = domain_of(h.url)
                        if domain not in PRIMARY_DOMAINS:
                            continue  # Skip non-primary sources
                        
                        # Create high-quality card for primary source
                        new_cards.append(EvidenceCard(
                            id=str(uuid.uuid4()),
                            title=h.title,
                            url=h.url,
                            snippet=h.snippet or "",
                            provider=provider,
                            date=h.date,
                            credibility_score=0.85,  # High credibility for primary
                            relevance_score=0.80,     # High relevance for targeted
                            confidence=0.85 * 0.80,
                            is_primary_source=True,
                            search_provider=provider,
                            source_domain=domain,
                            collected_at=datetime.utcnow().isoformat() + "Z",
                            related_reason=f"arex_primary_{gap.get('metric', 'unknown')}"
                        ))
                        
                        if len(new_cards) >= max_new_cards:
                            break
                            
            except Exception as e:
                logger.warning(f"AREX query failed for '{query}': {e}")
                continue
    
    if new_cards:
        logger.info(f"AREX added {len(new_cards)} primary source cards")
        # Merge with existing cards (dedup handled elsewhere)
        return cards + new_cards
    
    return cards