"""Wikipedia provider for encyclopedia content."""

from typing import List, Dict, Any
from .http import http_json_with_policy as http_json
from urllib.parse import quote
import logging

logger = logging.getLogger(__name__)

def wiki_search(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search Wikipedia for relevant articles."""
    try:
        # Wikipedia REST API 1.0: page search (searches content, not just titles)
        url = "https://en.wikipedia.org/w/rest.php/v1/search/page"
        data = http_json("wikipedia", "GET", url, params={"q": query, "limit": limit})
        return data.get("pages", [])
    except Exception as e:
        logger.warning(f"Wikipedia search failed: {e}")
        return []

def to_cards(rows: List[Dict[str, Any]]) -> List[Dict]:
    """Convert Wikipedia results to evidence card format."""
    cards = []
    for p in rows:
        try:
            title = p.get("title", "")
            if not title:
                continue
            
            # Build Wikipedia URL
            url = f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
            
            # Extract description if available
            description = p.get("description", "")
            excerpt = p.get("excerpt", "")
            snippet = description or excerpt or ""
            
            cards.append({
                "title": title,
                "url": url,
                "snippet": snippet,
                "source_domain": "wikipedia.org",
                "metadata": {
                    "provider": "wikipedia",
                    "page_id": p.get("id"),
                    "thumbnail": p.get("thumbnail", {}).get("url")
                }
            })
        except Exception as e:
            logger.debug(f"Failed to process Wikipedia result: {e}")
            continue
    
    return cards