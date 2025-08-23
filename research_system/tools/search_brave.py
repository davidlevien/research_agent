import httpx
import logging
from typing import Dict, Any
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
def _make_brave_request(query: str, count: int, api_key: str, freshness: str = None, country: str = "US", timeout: int = 30) -> Dict[str, Any]:
    """Make HTTP request to Brave Search API with retry logic"""
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key
    }
    params = {
        "q": query,
        "count": min(count, 20),  # Brave API max is 20
        "country": country,
        "search_lang": "en",
        "ui_lang": "en-US",
        "safesearch": "moderate"
    }
    
    # Add freshness filter if specified
    if freshness:
        # Map our freshness format to Brave's format
        freshness_map = {
            "1d": "pd",
            "1w": "pw", 
            "1m": "pm",
            "1y": "py"
        }
        if freshness in freshness_map:
            params["freshness"] = freshness_map[freshness]
    
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

def _parse_brave_response(data: Dict[str, Any]) -> list[SearchHit]:
    """Parse Brave Search API response into SearchHit objects"""
    results = []
    
    web_results = data.get("web", {}).get("results", [])
    if not web_results:
        logger.warning("No web results in Brave response")
        return results
    
    for item in web_results:
        try:
            # Extract date from meta if available
            date = None
            if "meta" in item and "page_age" in item["meta"]:
                date = item["meta"]["page_age"]
            
            hit = SearchHit(
                title=item.get("title", "No title"),
                url=item.get("url", ""),
                snippet=item.get("description", ""),
                date=date,
                provider="brave"
            )
            results.append(hit)
        except Exception as e:
            logger.warning(f"Failed to parse Brave result: {e}", exc_info=True)
            continue
    
    return results

def run(req: SearchRequest) -> list[SearchHit]:
    """Execute search using Brave Search API"""
    settings = Settings()
    
    # Increment request counter
    SEARCH_REQUESTS.labels(provider="brave").inc()
    
    # Start latency timer
    with SEARCH_LATENCY.labels(provider="brave").time():
        try:
            # Get API key
            api_key = settings.BRAVE_API_KEY
            if not api_key:
                logger.error("BRAVE_API_KEY not configured")
                SEARCH_ERRORS.labels(provider="brave").inc()
                return []
            
            # Determine country from region if specified
            country = "US"
            if req.region:
                region_map = {
                    "US": "US",
                    "EU": "GB",  # Use GB as EU representative
                    "UK": "GB",
                    "CA": "CA",
                    "AU": "AU"
                }
                country = region_map.get(req.region.upper(), "US")
            
            # Make API request
            response_data = _make_brave_request(
                query=req.query,
                count=req.count,
                api_key=api_key,
                freshness=req.freshness_window,
                country=country,
                timeout=settings.HTTP_TIMEOUT_SECONDS
            )
            
            # Parse response
            results = _parse_brave_response(response_data)
            
            logger.info(f"Brave search returned {len(results)} results for query: {req.query}")
            return results
            
        except Exception as e:
            logger.error(f"Brave search failed for query '{req.query}': {e}", exc_info=True)
            SEARCH_ERRORS.labels(provider="brave").inc()
            return []