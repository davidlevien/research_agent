import asyncio
import time
import re
from typing import Dict, List, Optional
from research_system.config import Settings
from research_system.tools.registry import Registry
from research_system.tools.search_models import SearchRequest, SearchHit
from research_system.metrics import SEARCH_REQUESTS, SEARCH_ERRORS, SEARCH_LATENCY
from research_system.net.provider_circuit import PROVIDER_CIRCUIT

async def _exec(loop, registry: Registry, tool_name: str, req: SearchRequest) -> list[SearchHit]:
    provider = tool_name.replace("search_", "")
    
    # Check circuit breaker
    is_available, reason = PROVIDER_CIRCUIT.is_available(provider)
    if not is_available:
        # Return empty result if circuit is open
        return []
    
    SEARCH_REQUESTS.labels(provider=provider).inc()
    start = time.perf_counter()
    try:
        res = await asyncio.to_thread(registry.execute, tool_name, req.model_dump())
        # Record success
        PROVIDER_CIRCUIT.record_success(provider)
        return res
    except Exception as e:
        SEARCH_ERRORS.labels(provider=provider).inc()
        # Record failure with status code if available
        status_code = None
        if "429" in str(e):
            status_code = 429
        elif "403" in str(e):
            status_code = 403
        PROVIDER_CIRCUIT.record_failure(provider, status_code)
        raise
    finally:
        SEARCH_LATENCY.labels(provider=provider).observe(time.perf_counter() - start)

def _provider_policy(query: str, providers: List[str]) -> List[str]:
    """Apply provider-specific policies: exclude verticals from generic searches."""
    q = query.lower()
    
    # Vertical APIs that should only be used for matching content
    vertical_apis = {"nps", "fred", "worldbank", "oecd", "imf", "eurostat", "pubmed", "arxiv"}
    
    # Check if query has site: or other decorators that shouldn't go to verticals
    has_site_decorator = "site:" in q
    
    # Check if NPS is relevant (only if no site: decorator)
    wants_nps = (not has_site_decorator and 
                 bool(re.search(r"\b(parks?|nps|national\s+park|trails?|camping|camp|permits?|monument|memorial)\b", q)))
    
    # Start with non-vertical providers
    normalized = [p for p in providers if p not in vertical_apis]
    
    # Only add specific verticals if relevant and no conflicting decorators
    if wants_nps and not has_site_decorator:
        normalized.append("nps")
    
    return normalized

async def parallel_provider_search(registry: Registry, query: str, count: int, freshness: Optional[str], region: Optional[str]):
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
    # Filter out providers with open circuits
    available_providers = PROVIDER_CIRCUIT.get_available_providers(normalized)
    valid_providers = [p for p in available_providers if p in tool_map]
    tasks = [_exec(asyncio.get_running_loop(), registry, tool_map[p], req) for p in valid_providers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    per_provider: Dict[str, List[SearchHit]] = {}
    for p, res in zip(valid_providers, results):
        per_provider[p] = [] if isinstance(res, Exception) else res
        # Do NOT backfill; failures remain empty by design
    return per_provider