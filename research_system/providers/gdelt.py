"""GDELT provider for global news and events."""

from typing import List, Dict, Any
from .http import http_json
import logging

logger = logging.getLogger(__name__)

BASE = "https://api.gdeltproject.org/api/v2/events/summary"

def gdelt_events(query: str, timespan: str = "1w") -> List[Dict[str, Any]]:
    """Search GDELT for recent events and news."""
    try:
        params = {
            "query": query,
            "timespan": timespan,
            "format": "json"
        }
        data = http_json("GET", BASE, params=params)
        return data.get("events", [])
    except Exception as e:
        logger.warning(f"GDELT search failed: {e}")
        return []

def to_cards(events: List[Dict[str, Any]]) -> List[Dict]:
    """Convert GDELT events to evidence card format."""
    cards = []
    for e in events:
        try:
            url = e.get("url", "")
            if not url:
                continue
            
            title = e.get("title") or e.get("seendesc", "")
            domain = (e.get("domain", "") or "").lower()
            
            # Extract date if available
            date_str = e.get("date", "")
            published_at = None
            if date_str and len(date_str) >= 8:
                # GDELT date format: YYYYMMDD
                try:
                    year = date_str[:4]
                    month = date_str[4:6]
                    day = date_str[6:8]
                    published_at = f"{year}-{month}-{day}"
                except:
                    pass
            
            cards.append({
                "title": title,
                "url": url,
                "snippet": e.get("excerpt", ""),
                "source_domain": domain or "gdeltproject.org",
                "published_at": published_at,
                "metadata": {
                    "provider": "gdelt",
                    "tone": e.get("tone"),
                    "goldstein": e.get("goldstein"),
                    "mentions": e.get("mentions", 0)
                }
            })
        except Exception as e:
            logger.debug(f"Failed to process GDELT event: {e}")
            continue
    
    return cards