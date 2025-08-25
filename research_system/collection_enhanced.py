"""Enhanced collection with free API provider integration."""

import asyncio
import os
import time
import re
from typing import Dict, List, Optional, Any
from research_system.config import Settings
from research_system.tools.registry import Registry
from research_system.tools.search_models import SearchRequest, SearchHit
from research_system.metrics import SEARCH_REQUESTS, SEARCH_ERRORS, SEARCH_LATENCY
from research_system.providers.registry import PROVIDERS
from research_system.tools.domain_norm import canonical_domain
from research_system.models import EvidenceCard
from research_system.routing.provider_router import choose_providers
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

async def _exec(loop, registry: Registry, tool_name: str, req: SearchRequest) -> list[SearchHit]:
    """Execute search tool asynchronously."""
    provider = tool_name.replace("search_", "")
    SEARCH_REQUESTS.labels(provider=provider).inc()
    start = time.perf_counter()
    try:
        res = await asyncio.to_thread(registry.execute, tool_name, req.model_dump())
        return res
    except Exception:
        SEARCH_ERRORS.labels(provider=provider).inc()
        raise
    finally:
        SEARCH_LATENCY.labels(provider=provider).observe(time.perf_counter() - start)

def _provider_policy(query: str, providers: List[str]) -> List[str]:
    """Heuristic: include 'nps' only for park-specific queries."""
    q = query.lower()
    wants_nps = bool(re.search(r"\b(park|nps|national\s+park|trail|camp|permit|monument|memorial)\b", q))
    normalized = [p for p in providers if p != "nps"]
    if wants_nps and "nps" in providers:
        normalized.append("nps")
    return normalized

async def parallel_provider_search(registry: Registry, query: str, count: int, freshness: Optional[str], region: Optional[str]):
    """Search across web search providers in parallel."""
    s = Settings()
    providers = s.enabled_providers()
    tool_map = {
        "tavily": "search_tavily",
        "brave": "search_brave",
        "serper": "search_serper",
        "serpapi": "search_serpapi",
        "nps": "search_nps"
    }
    req = SearchRequest(query=query, count=count, freshness_window=freshness, region=region)
    # Apply provider policy to filter out irrelevant providers
    normalized = _provider_policy(query, providers)
    valid_providers = [p for p in normalized if p in tool_map]
    tasks = [_exec(asyncio.get_running_loop(), registry, tool_map[p], req) for p in valid_providers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    per_provider: Dict[str, List[SearchHit]] = {}
    for p, res in zip(valid_providers, results):
        per_provider[p] = [] if isinstance(res, Exception) else res
        # Do NOT backfill; failures remain empty by design
    return per_provider

def collect_from_free_apis(
    topic: str,
    providers: Optional[List[str]] = None,
    settings: Optional[Any] = None
) -> List[EvidenceCard]:
    """
    Collect evidence from free API providers.
    
    Args:
        topic: Research topic
        providers: List of provider names to use (or None for auto-routing)
        settings: Optional settings object with logger
        
    Returns:
        List of evidence cards from free providers
    """
    # Environment override for testing
    if os.getenv("ENABLED_PROVIDERS"):
        provs = [p.strip() for p in os.getenv("ENABLED_PROVIDERS").split(",") if p.strip()]
    elif providers:
        provs = providers
    else:
        # Use router to choose providers based on topic
        decision = choose_providers(topic)
        provs = decision.providers
        if settings and hasattr(settings, 'logger'):
            settings.logger.info(f"Router selected providers: {provs} for categories: {decision.categories}")
    
    cards: List[EvidenceCard] = []
    
    for p in provs:
        impl = PROVIDERS.get(p, {})
        
        try:
            # Most providers have standard search + to_cards pattern
            if p in ("openalex", "crossref", "wikipedia", "worldbank", "oecd", 
                     "imf", "arxiv", "pubmed", "europepmc", "eurostat", "ec", "overpass"):
                # These have direct search functions
                search_fn = impl.get("search")
                to_cards_fn = impl.get("to_cards")
                
                if not search_fn:
                    continue
                
                # Execute search
                results = search_fn(topic)
                
                # Convert to cards
                if to_cards_fn and results:
                    seed_cards = to_cards_fn(results)
                    for s in seed_cards:
                        cards.append(EvidenceCard.from_seed(s, provider=p))
                        
            elif p == "gdelt":
                # GDELT uses events function
                events_fn = impl.get("events")
                to_cards_fn = impl.get("to_cards")
                
                if events_fn:
                    events = events_fn(topic)
                    if to_cards_fn and events:
                        seed_cards = to_cards_fn(events)
                        for s in seed_cards:
                            cards.append(EvidenceCard.from_seed(s, provider="gdelt"))
                            
            elif p == "fred":
                # FRED needs special handling - look for economic indicators in topic
                if any(term in topic.lower() for term in ["inflation", "cpi", "gdp", "unemployment", "interest"]):
                    series_fn = impl.get("series")
                    to_cards_fn = impl.get("to_cards")
                    
                    if series_fn:
                        # Map common terms to FRED series IDs
                        series_map = {
                            "inflation": "CPIAUCSL",
                            "cpi": "CPIAUCSL",
                            "gdp": "GDP",
                            "unemployment": "UNRATE",
                            "interest": "DFF"
                        }
                        
                        for term, series_id in series_map.items():
                            if term in topic.lower():
                                resp = series_fn(series_id)
                                if to_cards_fn and resp.get("observations"):
                                    seed_cards = to_cards_fn(resp, series_id)
                                    for s in seed_cards:
                                        cards.append(EvidenceCard.from_seed(s, provider="fred"))
                                break
                                
            # Wayback is used for resilience, not search
            # Unpaywall is used for enrichment by DOI
            # Wikidata is used for entity resolution
            
        except Exception as e:
            if settings and hasattr(settings, 'logger'):
                settings.logger.warning(f"Provider {p} error: {e}")
            else:
                logger.warning(f"Provider {p} error: {e}")
    
    # Canonicalize domains and ensure provider is set
    for c in cards:
        c.source_domain = canonical_domain(c.source_domain or "")
        if not getattr(c, "provider", None):
            c.provider = "free_api"
    
    return cards

def collect_initial_cards(
    topic: str,
    settings: Any,
    providers: Optional[List[str]] = None,
    use_free_apis: bool = True
) -> List[EvidenceCard]:
    """
    Collect initial evidence cards from all sources.
    
    Combines traditional web search with free API providers.
    
    Args:
        topic: Research topic
        settings: Settings object
        providers: Optional list of free API providers to use
        use_free_apis: Whether to include free API results
        
    Returns:
        Combined list of evidence cards
    """
    all_cards = []
    
    # Get cards from traditional web search
    # This would normally call the existing collection logic
    # For now, we'll skip it to focus on free APIs
    
    # Get cards from free APIs if enabled
    if use_free_apis:
        free_cards = collect_from_free_apis(topic, providers, settings)
        all_cards.extend(free_cards)
    
    # Deduplicate by URL
    seen_urls = set()
    deduped = []
    for card in all_cards:
        if card.url not in seen_urls:
            seen_urls.add(card.url)
            deduped.append(card)
    
    return deduped