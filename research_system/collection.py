import asyncio
import time
from typing import Dict, List, Optional
from research_system.config import Settings
from research_system.tools.registry import Registry
from research_system.tools.search_models import SearchRequest, SearchHit
from research_system.metrics import SEARCH_REQUESTS, SEARCH_ERRORS, SEARCH_LATENCY

async def _exec(loop, registry: Registry, tool_name: str, req: SearchRequest) -> list[SearchHit]:
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
    # Only execute tools that are in the tool_map and enabled
    valid_providers = [p for p in providers if p in tool_map]
    tasks = [_exec(asyncio.get_running_loop(), registry, tool_map[p], req) for p in valid_providers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    per_provider: Dict[str, List[SearchHit]] = {}
    for p, res in zip(valid_providers, results):
        per_provider[p] = [] if isinstance(res, Exception) else res
        # Do NOT backfill; failures remain empty by design
    return per_provider