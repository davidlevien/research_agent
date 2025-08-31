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
def _make_tavily_request(query: str, count: int, api_key: str, timeout: int = 30) -> Dict[str, Any]:
    """Make HTTP request to Tavily API with retry logic"""
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
        
        # v8.20.0: Handle Tavily's non-standard 432 status during protection windows
        if response.status_code == 432:
            logger.warning("Tavily returned 432 (rate limited), returning empty results")
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