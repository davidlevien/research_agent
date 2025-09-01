import httpx
import logging
import time
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ..config import Settings
from ..monitoring_metrics import SEARCH_REQUESTS, SEARCH_ERRORS, SEARCH_LATENCY
from .search_models import SearchRequest, SearchHit

logger = logging.getLogger(__name__)

# Simple in-module circuit/bucket (no external dep):
_CIRCUIT_OPEN_UNTIL: Optional[float] = None
_BUCKET_TOKENS = 5           # burst
_BUCKET_REFILL_RATE = 0.5    # tokens/sec
_BUCKET_LAST_REFILL = time.time()

def _bucket_take() -> bool:
    global _BUCKET_TOKENS, _BUCKET_LAST_REFILL
    now = time.time()
    _BUCKET_TOKENS = min(5, _BUCKET_TOKENS + (now - _BUCKET_LAST_REFILL) * _BUCKET_REFILL_RATE)
    _BUCKET_LAST_REFILL = now
    if _BUCKET_TOKENS >= 1:
        _BUCKET_TOKENS -= 1
        return True
    return False

def reset_tavily_circuit():
    """Reset the circuit breaker state (for testing)"""
    global _CIRCUIT_OPEN_UNTIL, _BUCKET_TOKENS, _BUCKET_LAST_REFILL
    _CIRCUIT_OPEN_UNTIL = None
    _BUCKET_TOKENS = 5
    _BUCKET_LAST_REFILL = time.time()

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError))
)
def _make_tavily_request(query: str, count: int, api_key: str, timeout: int = 30) -> Dict[str, Any]:
    """Make HTTP request to Tavily API with retry logic"""
    global _CIRCUIT_OPEN_UNTIL
    
    # Check circuit breaker
    now = time.time()
    if _CIRCUIT_OPEN_UNTIL and now < _CIRCUIT_OPEN_UNTIL:
        logger.info("Tavily circuit open, skipping call for %.0fs", _CIRCUIT_OPEN_UNTIL - now)
        return {"results": []}
    
    # Check token bucket
    if not _bucket_take():
        logger.info("Tavily bucket empty; deferring this call.")
        return {"results": []}
    
    url = "https://api.tavily.com/search"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "include_answer": False,
        "include_domains": [],
        "exclude_domains": [],
        "max_results": count
    }
    
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=payload, headers=headers)
        
        # v8.23.0: Enhanced rate limit handling with 10-minute circuit breaker
        if response.status_code in (429, 430, 431, 432):
            # Open circuit for 10 minutes
            COOL_OFF_SECONDS = 600  # 10 minutes
            _CIRCUIT_OPEN_UNTIL = time.time() + COOL_OFF_SECONDS
            logger.warning("Tavily %s (rate limited) – opening circuit for %ss", response.status_code, COOL_OFF_SECONDS)
            return {"results": []}
        
        response.raise_for_status()
        return response.json()

def _parse_tavily_response(data: Dict[str, Any]) -> list[SearchHit]:
    """Parse Tavily API response into SearchHit objects"""
    results = []
    
    if "results" not in data:
        logger.warning("No results field in Tavily response")
        return results
    
    for item in data.get("results", []):
        try:
            hit = SearchHit(
                title=item.get("title", "No title"),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                provider="tavily"
            )
            results.append(hit)
        except Exception as e:
            logger.warning(f"Failed to parse Tavily result: {e}", exc_info=True)
            continue
    
    return results

def run(req: SearchRequest) -> list[SearchHit]:
    """Execute search using Tavily API"""
    settings = Settings()
    
    # Increment request counter
    SEARCH_REQUESTS.labels(provider="tavily").inc()
    
    # Start latency timer
    with SEARCH_LATENCY.labels(provider="tavily").time():
        try:
            # Get API key
            api_key = settings.TAVILY_API_KEY
            if not api_key:
                logger.error("TAVILY_API_KEY not configured")
                SEARCH_ERRORS.labels(provider="tavily").inc()
                return []
            
            # Make API request
            response_data = _make_tavily_request(
                query=req.query,
                count=req.count,
                api_key=api_key,
                timeout=settings.HTTP_TIMEOUT_SECONDS
            )
            
            # Parse response
            results = _parse_tavily_response(response_data)
            
            logger.info(f"Tavily search returned {len(results)} results for query: {req.query}")
            return results
            
        except Exception as e:
            logger.error(f"Tavily search failed for query '{req.query}': {e}", exc_info=True)
            SEARCH_ERRORS.labels(provider="tavily").inc()
            return []