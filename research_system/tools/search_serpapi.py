import httpx
import logging
import os
from typing import Dict, Any, Optional, Set
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ..config import Settings
from ..metrics import SEARCH_REQUESTS, SEARCH_ERRORS, SEARCH_LATENCY
from .search_models import SearchRequest, SearchHit

logger = logging.getLogger(__name__)

# Circuit breaker state (module-level for persistence across calls)
_serpapi_state = {
    "is_open": False,
    "seen_queries": set(),
    "call_count": 0,
    "consecutive_429s": 0
}

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError))
)
def _make_serpapi_request(query: str, count: int, api_key: str, location: str = "United States", timeout: int = 30) -> Dict[str, Any]:
    """Make HTTP request to SerpAPI with retry logic"""
    url = "https://serpapi.com/search.json"
    params = {
        "q": query,
        "num": min(count, 100),
        "api_key": api_key,
        "engine": "google",
        "location": location,
        "safe": "active",
        "filter": "1"
    }
    
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()

def _parse_serpapi_results(data: Dict[str, Any]) -> list[SearchHit]:
    """Parse SerpAPI response into SearchHit objects"""
    results = []
    
    # Get organic results
    organic_results = data.get("organic_results", [])
    
    for item in organic_results:
        try:
            title = item.get("title", "")
            url = item.get("link", "")
            snippet = item.get("snippet", "")
            date = item.get("date", None)
            
            if url and title:
                results.append(SearchHit(
                    title=title,
                    url=url,
                    snippet=snippet,
                    date=date,
                    provider="serpapi"
                ))
        except Exception as e:
            logger.warning(f"Failed to parse SerpAPI result: {e}")
            continue
    
    # Also check for answer box results
    answer_box = data.get("answer_box", {})
    if answer_box and answer_box.get("type") == "organic_result":
        title = answer_box.get("title", "")
        url = answer_box.get("link", "")
        snippet = answer_box.get("snippet", answer_box.get("answer", ""))
        if url and title:
            results.append(SearchHit(
                title=title,
                url=url,
                snippet=snippet,
                date=None,
                provider="serpapi"
            ))
    
    return results

def run(req: SearchRequest) -> list[SearchHit]:
    """Execute search using SerpAPI with circuit breaker and deduplication"""
    settings = Settings()
    
    # Check if circuit breaker is enabled (default: True)
    use_circuit_breaker = os.getenv("SERPAPI_CIRCUIT_BREAKER", "true").lower() == "true"
    max_calls_per_run = int(os.getenv("SERPAPI_MAX_CALLS_PER_RUN", "4"))
    trip_on_429 = os.getenv("SERPAPI_TRIP_ON_429", "true").lower() == "true"
    
    if use_circuit_breaker:
        # Check if circuit is open
        if _serpapi_state["is_open"]:
            logger.info(f"SERPAPI_SKIPPED_CIRCUIT_OPEN", extra={"q": req.query})
            return []
        
        # Check for duplicate queries
        query_norm = req.query.strip().lower()
        if query_norm in _serpapi_state["seen_queries"]:
            logger.debug("SERPAPI_DEDUP", extra={"q": req.query})
            return []
        _serpapi_state["seen_queries"].add(query_norm)
        
        # Check call budget
        if _serpapi_state["call_count"] >= max_calls_per_run:
            logger.info("SERPAPI_SKIPPED_BUDGET", extra={"q": req.query, "count": _serpapi_state["call_count"]})
            return []
        _serpapi_state["call_count"] += 1
    
    # Increment request counter
    SEARCH_REQUESTS.labels(provider="serpapi").inc()
    
    # Start latency timer
    with SEARCH_LATENCY.labels(provider="serpapi").time():
        try:
            # Get API key
            api_key = settings.SERPAPI_API_KEY
            if not api_key:
                logger.error("SERPAPI_API_KEY not configured")
                SEARCH_ERRORS.labels(provider="serpapi").inc()
                return []
            
            # Determine location from region if specified
            location = "United States"
            if req.region:
                region_map = {
                    "US": "United States",
                    "EU": "Germany",  # Use Germany as EU representative
                    "UK": "United Kingdom",
                    "CA": "Canada",
                    "AU": "Australia",
                    "FR": "France",
                    "DE": "Germany",
                    "JP": "Japan"
                }
                location = region_map.get(req.region, location)
            
            # Make the API request
            timeout = settings.HTTP_TIMEOUT_SECONDS
            response_data = _make_serpapi_request(
                query=req.query,
                count=req.count,
                api_key=api_key,
                location=location,
                timeout=timeout
            )
            
            # Parse results
            results = _parse_serpapi_results(response_data)
            
            # Reset consecutive 429s on success
            if use_circuit_breaker:
                _serpapi_state["consecutive_429s"] = 0
            
            logger.info(f"SerpAPI search for '{req.query}' returned {len(results)} results")
            return results
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("SERPAPI_RATE_LIMIT", extra={"q": req.query, "status": 429})
                if use_circuit_breaker:
                    _serpapi_state["consecutive_429s"] += 1
                    if trip_on_429 and _serpapi_state["consecutive_429s"] >= 1:
                        _serpapi_state["is_open"] = True
                        logger.warning("SERPAPI_CIRCUIT_TRIPPED", extra={"q": req.query, "consecutive_429s": _serpapi_state["consecutive_429s"]})
            logger.error(f"SerpAPI search failed for query '{req.query}': {e}")
            SEARCH_ERRORS.labels(provider="serpapi").inc()
            return []
        except Exception as e:
            logger.error(f"SerpAPI search failed for query '{req.query}': {e}")
            SEARCH_ERRORS.labels(provider="serpapi").inc()
            return []