import httpx
import logging
import os
import time
import re
from typing import Dict, Any, Optional, Set
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# v8.18.0: Handle RetryError gracefully when tenacity is present
try:
    from tenacity import RetryError
except ImportError:
    # Fallback type when tenacity doesn't export RetryError
    class RetryError(Exception):
        pass

from ..config import Settings
from ..metrics import SEARCH_REQUESTS, SEARCH_ERRORS, SEARCH_LATENCY
from .search_models import SearchRequest, SearchHit

logger = logging.getLogger(__name__)

# v8.18.0: Redact api_key from noisy httpx INFO logs
class _RedactApiKeyFilter(logging.Filter):
    _pat = re.compile(r"(api_key=)[^&\s]+")
    
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    self._pat.sub(r"\1REDACTED", str(a)) for a in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {k: self._pat.sub(r"\1REDACTED", str(v)) for k, v in record.args.items()}
            record.msg = self._pat.sub(r"\1REDACTED", str(record.msg))
        except Exception:
            pass
        return True

# Apply the redaction filter to httpx logger
logging.getLogger("httpx").addFilter(_RedactApiKeyFilter())

# v8.16.0: Custom exception for missing API key (allows test mocking)
class SerpAPIConfigError(Exception):
    """Raised when SerpAPI is not configured properly."""
    pass

# Circuit breaker state (module-level for persistence across calls)
_serpapi_state = {
    "is_open": False,
    "seen_queries": set(),
    "call_count": 0,
    "consecutive_429s": 0,
    "call_budget": int(os.getenv("SERPAPI_MAX_CALLS_PER_RUN", "10")),
    "circuit_open_until": 0.0
}

CIRCUIT_COOLDOWN_SEC = 60

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError))
)
def _make_serpapi_request(query: str, count: int, api_key: str, location: str = "United States", timeout: int = 30) -> Dict[str, Any]:
    """Make HTTP request to SerpAPI with retry logic"""
    # v8.16.0: Don't make real network calls without a key (tests can monkeypatch this)
    if not api_key:
        raise SerpAPIConfigError("SERPAPI_API_KEY not configured")
    
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

def _get_api_key() -> Optional[str]:
    """v8.16.0: Lazy-load API key for CI/test flexibility."""
    try:
        return os.getenv("SERPAPI_API_KEY") or Settings().SERPAPI_API_KEY
    except Exception:
        return os.getenv("SERPAPI_API_KEY")

def run(req: SearchRequest) -> list[SearchHit]:
    """Execute search using SerpAPI with circuit breaker and deduplication.
    
    v8.16.0: Wrapper logic (circuit breaker, dedup, budget) runs even without API key
    to allow tests to exercise the full pipeline with mocked _make_serpapi_request.
    """
    settings = Settings()
    
    # Check if circuit breaker is enabled (default: True)
    use_circuit_breaker = os.getenv("SERPAPI_CIRCUIT_BREAKER", "true").lower() == "true"
    max_calls_per_run = int(os.getenv("SERPAPI_MAX_CALLS_PER_RUN", "4"))
    trip_on_429 = os.getenv("SERPAPI_TRIP_ON_429", "true").lower() == "true"
    
    if use_circuit_breaker:
        # Check if circuit is open (either by time or flag)
        now = time.time()
        if _serpapi_state["circuit_open_until"] > now or _serpapi_state["is_open"]:
            logger.info("SERPAPI_CIRCUIT_OPEN", extra={"q": req.query})
            return []
        
        # Check for duplicate queries
        query_norm = req.query.strip().lower()
        if query_norm in _serpapi_state["seen_queries"]:
            logger.debug("SERPAPI_DEDUP", extra={"q": req.query})
            return []
        _serpapi_state["seen_queries"].add(query_norm)
        
        # Check call budget (use state budget)
        if _serpapi_state["call_count"] >= _serpapi_state["call_budget"]:
            logger.info("SERPAPI_SKIPPED_BUDGET", extra={"q": req.query, "count": _serpapi_state["call_count"]})
            return []
    
    # Increment call count (must happen before we make the call)
    if use_circuit_breaker:
        _serpapi_state["call_count"] += 1
    
    # Increment request counter
    SEARCH_REQUESTS.labels(provider="serpapi").inc()
    
    # Start latency timer
    with SEARCH_LATENCY.labels(provider="serpapi").time():
        try:
            # Get API key (v8.16.0: lazy-loaded for test flexibility)
            api_key = _get_api_key()
            if not api_key:
                logger.debug("SERPAPI_API_KEY not configured; continuing so circuit-breaker/dedup logic can run (tests/mocks).")
                # Note: _make_serpapi_request will raise SerpAPIConfigError if not mocked
            
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
            
            # Make the API request (v8.16.0: may raise SerpAPIConfigError if no key)
            timeout = settings.HTTP_TIMEOUT_SECONDS
            try:
                response_data = _make_serpapi_request(
                    query=req.query,
                    count=req.count,
                    api_key=api_key or "",  # Pass empty string if None
                    location=location,
                    timeout=timeout
                )
            except SerpAPIConfigError:
                logger.debug("SERPAPI disabled (no key) — skipping real request and returning empty result.")
                SEARCH_ERRORS.labels(provider="serpapi").inc()
                return []
            
            # Parse results
            results = _parse_serpapi_results(response_data)
            
            # Reset consecutive 429s and circuit state on success
            if use_circuit_breaker:
                _serpapi_state["consecutive_429s"] = 0
                _serpapi_state["is_open"] = False
            
            logger.info(f"SerpAPI search for '{req.query}' returned {len(results)} results")
            return results
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("SERPAPI_RATE_LIMIT", extra={"q": req.query, "status": 429})
                if use_circuit_breaker:
                    _serpapi_state["consecutive_429s"] += 1
                    # Trip the circuit immediately on first 429 (matches tests)
                    if trip_on_429 and _serpapi_state["consecutive_429s"] >= 1:
                        _serpapi_state["circuit_open_until"] = time.time() + CIRCUIT_COOLDOWN_SEC
                        _serpapi_state["is_open"] = True  # Keep for backward compatibility
                        logger.warning("SERPAPI_CIRCUIT_TRIPPED", extra={"q": req.query, "consecutive_429s": _serpapi_state["consecutive_429s"]})
            logger.error(f"SerpAPI search failed for query '{req.query}': {e}")
            SEARCH_ERRORS.labels(provider="serpapi").inc()
            return []
        except RetryError as e:
            # v8.18.0: If an outer retry wrapper handled the 429s, propagate to our circuit
            try:
                last_exc = e.last_attempt.exception()  # type: ignore[attr-defined]
            except Exception:
                last_exc = None
            
            if isinstance(last_exc, httpx.HTTPStatusError) and getattr(last_exc.response, "status_code", None) == 429:
                if use_circuit_breaker:
                    _serpapi_state["consecutive_429s"] += 1
                    _serpapi_state["circuit_open_until"] = time.time() + CIRCUIT_COOLDOWN_SEC
                    _serpapi_state["is_open"] = True  # Keep for backward compatibility
                    logger.error(f"SerpAPI rate-limited via RetryError (429). consecutive={_serpapi_state['consecutive_429s']}")
            else:
                logger.error(f"SerpAPI search failed with RetryError: {e}")
            
            SEARCH_ERRORS.labels(provider="serpapi").inc()
            return []
        except Exception as e:
            logger.error(f"SerpAPI search failed for query '{req.query}': {e}")
            SEARCH_ERRORS.labels(provider="serpapi").inc()
            return []

def search_serpapi(query: str, num: int = 10, **kwargs) -> list[SearchHit]:
    """v8.16.0: Backward compatibility wrapper for run() function."""
    req = SearchRequest(query=query, count=num, **kwargs)
    return run(req)


def get_serpapi_state() -> Dict[str, Any]:
    """v8.17.0: Get current SerpAPI state for monitoring/testing."""
    return {
        "consecutive_429s": _serpapi_state["consecutive_429s"],
        "seen_queries": set(_serpapi_state["seen_queries"]),
        "call_count": _serpapi_state["call_count"],
        "call_budget": _serpapi_state["call_budget"],
        "circuit_open_until": _serpapi_state["circuit_open_until"]
    }


def reset_serpapi_state() -> None:
    """v8.17.0: Reset SerpAPI state for testing purposes."""
    _serpapi_state["is_open"] = False
    _serpapi_state["seen_queries"].clear()
    _serpapi_state["call_count"] = 0
    _serpapi_state["consecutive_429s"] = 0
    _serpapi_state["call_budget"] = int(os.getenv("SERPAPI_MAX_CALLS_PER_RUN", "10"))
    _serpapi_state["circuit_open_until"] = 0.0
