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
def _make_serper_request(query: str, count: int, api_key: str, gl: str = "us", hl: str = "en", timeout: int = 30) -> Dict[str, Any]:
    """Make HTTP request to Serper.dev API with retry logic"""
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "q": query,
        "num": min(count, 100),  # Serper API max is 100
        "gl": gl,  # Country code
        "hl": hl,  # Language
        "type": "search"
    }
    
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

def _parse_serper_response(data: Dict[str, Any]) -> list[SearchHit]:
    """Parse Serper.dev API response into SearchHit objects"""
    results = []
    
    organic_results = data.get("organic", [])
    if not organic_results:
        logger.warning("No organic results in Serper response")
        return results
    
    for item in organic_results:
        try:
            # Extract date if available
            date = item.get("date")
            
            hit = SearchHit(
                title=item.get("title", "No title"),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                date=date,
                provider="serper"
            )
            results.append(hit)
        except Exception as e:
            logger.warning(f"Failed to parse Serper result: {e}", exc_info=True)
            continue
    
    return results

def run(req: SearchRequest) -> list[SearchHit]:
    """Execute search using Serper.dev API"""
    settings = Settings()
    
    # Increment request counter
    SEARCH_REQUESTS.labels(provider="serper").inc()
    
    # Start latency timer
    with SEARCH_LATENCY.labels(provider="serper").time():
        try:
            # Get API key
            api_key = settings.SERPER_API_KEY
            if not api_key:
                logger.error("SERPER_API_KEY not configured")
                SEARCH_ERRORS.labels(provider="serper").inc()
                return []
            
            # Determine country code from region if specified
            gl = "us"  # Default to US
            if req.region:
                region_map = {
                    "US": "us",
                    "EU": "de",  # Use Germany as EU representative
                    "UK": "uk",
                    "CA": "ca",
                    "AU": "au",
                    "IN": "in",
                    "JP": "jp",
                    "BR": "br",
                    "FR": "fr",
                    "DE": "de",
                    "ES": "es",
                    "IT": "it"
                }
                gl = region_map.get(req.region.upper(), "us")
            
            # Make API request
            response_data = _make_serper_request(
                query=req.query,
                count=req.count,
                api_key=api_key,
                gl=gl,
                hl="en",
                timeout=settings.HTTP_TIMEOUT_SECONDS
            )
            
            # Parse response
            results = _parse_serper_response(response_data)
            
            logger.info(f"Serper search returned {len(results)} results for query: {req.query}")
            return results
            
        except Exception as e:
            logger.error(f"Serper search failed for query '{req.query}': {e}", exc_info=True)
            SEARCH_ERRORS.labels(provider="serper").inc()
            return []