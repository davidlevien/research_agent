"""FRED (Federal Reserve Economic Data) provider."""

import os
from typing import Dict, Any, List, Optional
from .http import http_json_with_policy as http_json
import logging

logger = logging.getLogger(__name__)

def fred_series(
    series_id: str, 
    api_key: Optional[str] = None, 
    obs_start: Optional[str] = None
) -> Dict[str, Any]:
    """Fetch FRED economic series data."""
    key = api_key or os.getenv("FRED_API_KEY")
    if not key:
        logger.debug("FRED_API_KEY not set, skipping FRED search")
        return {"observations": []}
    
    try:
        params = {
            "series_id": series_id,
            "api_key": key,
            "file_type": "json"
        }
        if obs_start:
            params["observation_start"] = obs_start
        
        return http_json("fred", 
            "GET", 
            "https://api.stlouisfed.org/fred/series/observations", 
            params=params
        )
    except Exception as e:
        logger.warning(f"FRED series fetch failed: {e}")
        return {"observations": []}

def to_cards(resp: Dict[str, Any], series_id: Optional[str] = None) -> List[Dict]:
    """Convert FRED data to evidence card format."""
    cards = []
    series = series_id or resp.get("seriess", [{}])[0].get("id", "")
    
    observations = resp.get("observations", [])
    if not observations:
        return cards
    
    # Create one card for the series with latest data
    latest = observations[-1] if observations else {}
    
    if latest:
        url = f"https://fred.stlouisfed.org/series/{series}" if series else "https://fred.stlouisfed.org/"
        
        cards.append({
            "title": f"FRED {series}: {latest.get('value')} ({latest.get('date')})",
            "url": url,
            "snippet": f"Federal Reserve Economic Data series {series}",
            "source_domain": "stlouisfed.org",
            "published_at": latest.get("date"),
            "metadata": {
                "provider": "fred",
                "series_id": series,
                "value": latest.get("value"),
                "date": latest.get("date"),
                "observation_count": len(observations)
            }
        })
    
    return cards

def search_series(keywords: str, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search for FRED series by keywords."""
    key = api_key or os.getenv("FRED_API_KEY")
    if not key:
        return []
    
    try:
        params = {
            "search_text": keywords,
            "api_key": key,
            "file_type": "json",
            "limit": 10
        }
        
        data = http_json("fred", 
            "GET",
            "https://api.stlouisfed.org/fred/series/search",
            params=params
        )
        return data.get("seriess", [])
    except Exception as e:
        logger.debug(f"FRED series search failed: {e}")
        return []