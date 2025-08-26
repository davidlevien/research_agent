"""OpenAlex provider for scholarly search and metadata."""

from typing import List, Dict, Any
from .http import http_json_with_policy as http_json
import logging

logger = logging.getLogger(__name__)

BASE = "https://api.openalex.org/works"

def search_openalex(query: str, per_page: int = 25) -> List[Dict[str, Any]]:
    """Search OpenAlex for scholarly works with fallback to filter API."""
    try:
        params = {
            "search": query, 
            "per_page": per_page, 
            "mailto": "research@example.com"  # Polite crawling
        }
        
        try:
            # Try search parameter first (preferred)
            data = http_json("openalex", "GET", BASE, params=params)
            return data.get("results", [])
        except Exception as e:
            if "400" in str(e):
                # Fallback to filter API on 400 error
                logger.info(f"OpenAlex search failed with 400, trying filter fallback")
                params = {
                    "filter": f"title.search:{query}",
                    "per_page": per_page, 
                    "mailto": "research@example.com"
                }
                data = http_json("openalex", "GET", BASE, params=params)
                return data.get("results", [])
            raise
            
    except Exception as e:
        logger.warning(f"OpenAlex search failed: {e}")
        return []

def to_cards(rows: List[Dict[str, Any]]) -> List[Dict]:
    """Convert OpenAlex results to evidence card format."""
    cards = []
    for w in rows:
        try:
            # Extract primary information
            title = w.get("title") or w.get("display_name", "")
            doi = w.get("doi", "")
            url = w.get("id") or (f"https://doi.org/{doi.split('/')[-1]}" if doi else "")
            
            if not url:
                continue
                
            # Extract metadata
            open_access = w.get("open_access", {})
            is_oa = open_access.get("is_oa", False)
            oa_url = open_access.get("oa_url", "")
            
            # Host venue information
            host_venue = w.get("host_venue", {})
            venue_name = host_venue.get("display_name", "")
            
            # Publication year
            year = w.get("publication_year")
            published_at = f"{year}-01-01" if year else None
            
            cards.append({
                "title": title,
                "url": oa_url if is_oa and oa_url else url,
                "source_domain": "openalex.org",
                "published_at": published_at,
                "metadata": {
                    "doi": doi,
                    "open_access": is_oa,
                    "host_venue": venue_name,
                    "cited_by_count": w.get("cited_by_count", 0),
                    "provider": "openalex"
                }
            })
        except Exception as e:
            logger.debug(f"Failed to process OpenAlex result: {e}")
            continue
    
    return cards