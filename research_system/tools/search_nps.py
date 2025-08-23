import httpx
import logging
from typing import Dict, Any, List
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
def _make_nps_request(query: str, limit: int, api_key: str, timeout: int = 30) -> Dict[str, Any]:
    """Make HTTP request to National Park Service API with retry logic"""
    url = "https://developer.nps.gov/api/v1/parks"
    params = {
        "q": query,
        "limit": min(limit, 50),  # NPS API max is 50
        "api_key": api_key,
        "fields": "fullName,parkCode,description,designation,url,states,topics,activities"
    }
    
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()

def _parse_nps_results(data: Dict[str, Any]) -> list[SearchHit]:
    """Parse NPS API response into SearchHit objects"""
    results = []
    
    # Get park data
    parks = data.get("data", [])
    
    for park in parks:
        try:
            # Extract park information
            full_name = park.get("fullName", "Unknown Park")
            park_code = park.get("parkCode", "")
            description = park.get("description", "")
            designation = park.get("designation", "")
            url = park.get("url", "https://www.nps.gov/")
            states = park.get("states", "")
            
            # Build title with state info
            title = full_name
            if states:
                title = f"{full_name} ({states})"
            
            # Build snippet from description and designation
            snippet = description[:300] if description else designation
            if designation and designation not in snippet:
                snippet = f"{designation}. {snippet}"
            
            # Add topics/activities if available
            topics = park.get("topics", [])
            if topics and isinstance(topics, list):
                topic_names = [t.get("name", "") for t in topics[:3] if isinstance(t, dict)]
                if topic_names:
                    snippet += f" Topics: {', '.join(topic_names)}"
            
            results.append(SearchHit(
                title=title,
                url=url,
                snippet=snippet,
                date=None,  # NPS doesn't provide publication dates
                provider="nps"
            ))
        except Exception as e:
            logger.warning(f"Failed to parse NPS result: {e}")
            continue
    
    return results

def run(req: SearchRequest) -> list[SearchHit]:
    """Execute search using National Park Service API"""
    settings = Settings()
    
    # Increment request counter
    SEARCH_REQUESTS.labels(provider="nps").inc()
    
    # Start latency timer
    with SEARCH_LATENCY.labels(provider="nps").time():
        try:
            # Get API key
            api_key = settings.NPS_API_KEY
            if not api_key:
                logger.error("NPS_API_KEY not configured")
                SEARCH_ERRORS.labels(provider="nps").inc()
                return []
            
            # Make the API request
            timeout = settings.HTTP_TIMEOUT_SECONDS
            response_data = _make_nps_request(
                query=req.query,
                limit=req.count,
                api_key=api_key,
                timeout=timeout
            )
            
            # Parse results
            results = _parse_nps_results(response_data)
            
            # NPS is domain-specific, so boost relevance for park-related queries
            if any(term in req.query.lower() for term in ["park", "national", "nature", "trail", "camping", "wilderness"]):
                # These are highly relevant for park queries
                for result in results:
                    result.snippet = f"[NPS Official] {result.snippet}"
            
            logger.info(f"NPS search for '{req.query}' returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"NPS search failed for query '{req.query}': {e}")
            SEARCH_ERRORS.labels(provider="nps").inc()
            return []