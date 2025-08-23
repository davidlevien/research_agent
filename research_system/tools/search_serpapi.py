import httpx
import logging
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ..config import Settings
from ..metrics import SEARCH_REQUESTS, SEARCH_ERRORS, SEARCH_LATENCY
from .search_models import SearchRequest, SearchHit

logger = logging.getLogger(__name__)

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
    """Execute search using SerpAPI"""
    settings = Settings()
    
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
            
            logger.info(f"SerpAPI search for '{req.query}' returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"SerpAPI search failed for query '{req.query}': {e}")
            SEARCH_ERRORS.labels(provider="serpapi").inc()
            return []