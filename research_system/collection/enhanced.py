"""Enhanced collection with free API provider integration."""

import asyncio
import os
import time
import re
from typing import Dict, List, Optional, Any
from research_system.config.settings import Settings
from research_system.tools.registry import Registry
from research_system.tools.search_models import SearchRequest, SearchHit
from research_system.monitoring_metrics import SEARCH_REQUESTS, SEARCH_ERRORS, SEARCH_LATENCY
from research_system.providers.registry import PROVIDERS
from research_system.tools.domain_norm import canonical_domain
from research_system.models import EvidenceCard
from research_system.routing.provider_router import choose_providers
from research_system.routing.topic_router import route_query, is_off_topic
import logging
import uuid
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import traceback

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
    """Heuristic: include 'nps' for park-specific queries."""
    q = query.lower()
    wants_nps = bool(re.search(r"\b(parks?|nps|national\s+park|trails?|camping|camp|permits?|monument|memorial)\b", q))
    normalized = [p for p in providers if p != "nps"]
    if wants_nps:
        # Add NPS for park queries even if not in original provider list
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

async def _execute_provider_async(
    provider_name: str,
    topic: str,
    impl: Dict[str, Any],
    settings: Optional[Any] = None,
    refined_query: Optional[str] = None,
    topic_key: Optional[str] = None
) -> List[EvidenceCard]:
    """Execute a single provider asynchronously and return evidence cards."""
    cards = []
    start_time = time.perf_counter()
    
    try:
        # Use metrics tracking
        SEARCH_REQUESTS.labels(provider=provider_name).inc()
        
        # Run provider in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        
        if provider_name in ("openalex", "crossref", "wikipedia", "worldbank", "oecd", 
                             "imf", "arxiv", "pubmed", "europepmc", "eurostat", "ec", "overpass"):
            search_fn = impl.get("search")
            to_cards_fn = impl.get("to_cards")
            
            if search_fn:
                # Use refined query if provided, otherwise fall back to original topic
                query_to_use = refined_query if refined_query else topic
                
                # Execute search in thread pool
                results = await loop.run_in_executor(None, search_fn, query_to_use)
                
                # Convert to cards with off-topic filtering
                if to_cards_fn and results:
                    seed_cards = to_cards_fn(results)
                    for s in seed_cards:
                        # Apply off-topic filtering if topic_key is provided
                        if topic_key and is_off_topic(s, topic_key):
                            if settings and hasattr(settings, 'logger'):
                                settings.logger.debug(f"Filtered off-topic content from {provider_name}: {s.get('title', 'No title')[:50]}...")
                            continue
                            
                        card = EvidenceCard.from_seed(s, provider=provider_name)
                        cards.append(card)
                        
        elif provider_name == "gdelt":
            events_fn = impl.get("events")
            to_cards_fn = impl.get("to_cards")
            
            if events_fn:
                # Use refined query if provided, otherwise fall back to original topic
                query_to_use = refined_query if refined_query else topic
                
                events = await loop.run_in_executor(None, events_fn, query_to_use)
                if to_cards_fn and events:
                    seed_cards = to_cards_fn(events)
                    for s in seed_cards:
                        # Apply off-topic filtering if topic_key is provided
                        if topic_key and is_off_topic(s, topic_key):
                            if settings and hasattr(settings, 'logger'):
                                settings.logger.debug(f"Filtered off-topic GDELT content: {s.get('title', 'No title')[:50]}...")
                            continue
                            
                        card = EvidenceCard.from_seed(s, provider="gdelt")
                        cards.append(card)
                        
        elif provider_name == "fred":
            # FRED needs special handling - look for economic indicators in topic
            if any(term in topic.lower() for term in ["inflation", "cpi", "gdp", "unemployment", "interest", "tourism", "travel"]):
                series_fn = impl.get("series")
                to_cards_fn = impl.get("to_cards")
                
                if series_fn:
                    # Extended map with tourism indicators
                    series_map = {
                        "inflation": "CPIAUCSL",
                        "cpi": "CPIAUCSL",
                        "gdp": "GDP",
                        "unemployment": "UNRATE",
                        "interest": "DFF",
                        "tourism": "HOUST",  # Housing starts as proxy
                        "travel": "HOUST"
                    }
                    
                    for term, series_id in series_map.items():
                        if term in topic.lower():
                            resp = await loop.run_in_executor(None, series_fn, series_id)
                            if to_cards_fn and resp.get("observations"):
                                seed_cards = to_cards_fn(resp, series_id)
                                for s in seed_cards:
                                    card = EvidenceCard.from_seed(s, provider="fred")
                                    cards.append(card)
                            break
                            
        # Log successful completion
        if settings and hasattr(settings, 'logger'):
            settings.logger.debug(f"Provider {provider_name} returned {len(cards)} cards")
        else:
            logger.debug(f"Provider {provider_name} returned {len(cards)} cards")
            
    except asyncio.TimeoutError:
        SEARCH_ERRORS.labels(provider=provider_name).inc()
        if settings and hasattr(settings, 'logger'):
            settings.logger.warning(f"Provider {provider_name} timed out")
        else:
            logger.warning(f"Provider {provider_name} timed out")
    except Exception as e:
        SEARCH_ERRORS.labels(provider=provider_name).inc()
        if settings and hasattr(settings, 'logger'):
            settings.logger.warning(f"Provider {provider_name} error: {e}")
        else:
            logger.warning(f"Provider {provider_name} error: {e}")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Provider {provider_name} traceback: {traceback.format_exc()}")
    finally:
        # Record latency
        SEARCH_LATENCY.labels(provider=provider_name).observe(time.perf_counter() - start_time)
    
    # Canonicalize domains and ensure provider is set
    for c in cards:
        c.source_domain = canonical_domain(c.source_domain or "")
        if not getattr(c, "provider", None):
            c.provider = provider_name
    
    return cards

async def collect_from_free_apis_async(
    topic: str,
    providers: Optional[List[str]] = None,
    settings: Optional[Any] = None,
    timeout_per_provider: int = 30
) -> List[EvidenceCard]:
    """
    Collect evidence from free API providers in parallel.
    
    Args:
        topic: Research topic
        providers: List of provider names to use (or None for auto-routing)
        settings: Optional settings object with logger
        timeout_per_provider: Maximum seconds per provider (default 30)
        
    Returns:
        List of evidence cards from free providers
    """
    # Environment override for testing
    if os.getenv("ENABLED_PROVIDERS"):
        provs = [p.strip() for p in os.getenv("ENABLED_PROVIDERS").split(",") if p.strip()]
        routing_decision = None
        topic_key = "general"
    elif providers:
        provs = providers
        routing_decision = None
        topic_key = "general"
    else:
        # Use new generalized router for provider selection
        routing_decision = route_query(topic, strategy="broad_coverage")
        provs = routing_decision.providers
        topic_key = routing_decision.topic_match.topic_key
        
        if settings and hasattr(settings, 'logger'):
            settings.logger.info(f"Router selected {len(provs)} providers for topic '{topic_key}' (confidence: {routing_decision.topic_match.confidence:.2f}): {provs[:5]}")
            if routing_decision.query_refinements:
                settings.logger.info(f"Query refinements applied for {len(routing_decision.query_refinements)} providers")
    
    # Create tasks for each provider
    tasks = []
    provider_names = []
    
    for p in provs:
        impl = PROVIDERS.get(p, {})
        if impl:
            # Get refined query for this provider if available
            refined_query = None
            if routing_decision and p in routing_decision.query_refinements:
                refined_query = routing_decision.query_refinements[p]
                
            # Create task with timeout, passing refined query and topic key
            task = asyncio.create_task(
                asyncio.wait_for(
                    _execute_provider_async(
                        p, 
                        topic, 
                        impl, 
                        settings, 
                        refined_query=refined_query, 
                        topic_key=topic_key
                    ),
                    timeout=timeout_per_provider
                )
            )
            tasks.append(task)
            provider_names.append(p)
    
    if not tasks:
        return []
    
    # Execute all providers in parallel
    if settings and hasattr(settings, 'logger'):
        settings.logger.info(f"Executing {len(tasks)} providers in parallel: {provider_names}")
    else:
        logger.info(f"Executing {len(tasks)} providers in parallel: {provider_names}")
    
    # Gather results with return_exceptions=True to handle failures gracefully
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Combine all successful results
    all_cards = []
    for provider_name, result in zip(provider_names, results):
        if isinstance(result, Exception):
            if settings and hasattr(settings, 'logger'):
                settings.logger.warning(f"Provider {provider_name} failed: {result}")
            else:
                logger.warning(f"Provider {provider_name} failed: {result}")
        elif result:
            all_cards.extend(result)
            if settings and hasattr(settings, 'logger'):
                settings.logger.info(f"Provider {provider_name} contributed {len(result)} cards")
    
    return all_cards

def collect_from_free_apis(
    topic: str,
    providers: Optional[List[str]] = None,
    settings: Optional[Any] = None
) -> List[EvidenceCard]:
    """
    Collect evidence from free API providers (synchronous wrapper).
    
    This is a synchronous wrapper around the async parallel implementation.
    It executes all providers in parallel for much better performance.
    
    Args:
        topic: Research topic
        providers: List of provider names to use (or None for auto-routing)
        settings: Optional settings object with logger
        
    Returns:
        List of evidence cards from free providers
    """
    # Check if we're already in an event loop
    try:
        loop = asyncio.get_running_loop()
        # We're in an async context, need to use run_in_executor
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                asyncio.run,
                collect_from_free_apis_async(topic, providers, settings)
            )
            return future.result(timeout=300)  # 5 minute total timeout
    except RuntimeError:
        # No event loop, we can use asyncio.run directly
        return asyncio.run(
            collect_from_free_apis_async(topic, providers, settings)
        )

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