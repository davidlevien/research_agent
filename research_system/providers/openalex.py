"""OpenAlex provider for scholarly search and metadata."""

from typing import List, Dict, Any
from .http import http_json_with_policy as http_json
import logging
import os
import re

logger = logging.getLogger(__name__)

BASE = "https://api.openalex.org/works"

def search_openalex(query: str, per_page: int = 25) -> List[Dict[str, Any]]:
    """v8.16.0: Search OpenAlex with robust query degradation and graceful fallback."""
    
    # Get contact email from environment or use default
    contact_email = os.getenv("OPENALEX_EMAIL", "ci@example.org")
    
    def _call(params: dict) -> List[Dict[str, Any]]:
        """Make API call with error handling."""
        try:
            data = http_json("openalex", "GET", BASE, params=params)
            return data.get("results", [])
        except Exception as e:
            # Re-raise to allow fallback handling
            raise e
    
    # Clean query - remove problematic characters
    clean_query = re.sub(r'[^\w\s]', ' ', query).strip()
    clean_query = ' '.join(clean_query.split())[:100]  # Limit length
    
    # Common parameters - skip mailto if empty or example domain
    common = {
        "per_page": min(10, per_page)
    }
    
    # Only add mailto if it's a real email (not empty or example.org)
    if contact_email and not contact_email.endswith("@example.org"):
        common["mailto"] = contact_email
    
    # Strategy 1: Try fulltext search with select
    try:
        params = {
            **common,
            "search": clean_query,
            "select": "id,title,doi,authorships,host_venue,publication_year"
        }
        return _call(params)
    except Exception as e:
        if "400" not in str(e) and "Bad Request" not in str(e):
            logger.warning(f"OpenAlex search unexpected error: {e}")
            return []
        logger.debug("OpenAlex fulltext search failed, trying title.search")
    
    # Strategy 2: Fallback to title.search filter (no select)
    try:
        # Use first 5 significant words for title search
        title_query = ' '.join(clean_query.split()[:5])
        params = {
            **common,
            "filter": f"title.search:{title_query}"
        }
        return _call(params)
    except Exception as e:
        if "400" not in str(e) and "Bad Request" not in str(e):
            logger.warning(f"OpenAlex title search error: {e}")
            return []
        logger.debug("OpenAlex title.search failed, trying abstract.search")
    
    # Strategy 3: Fallback to abstract.search (broader)
    try:
        # Use first 3 words for abstract search
        abstract_query = ' '.join(clean_query.split()[:3])
        params = {
            **common,
            "filter": f"abstract.search:{abstract_query}"
        }
        return _call(params)
    except Exception as e:
        logger.debug(f"OpenAlex abstract.search failed: {e}")
    
    # All strategies failed - return empty
    logger.info(f"OpenAlex all query strategies exhausted for: {query[:50]}")
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