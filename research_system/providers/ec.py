"""European Commission Open Data Portal provider."""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from .http import http_json
from urllib.parse import quote
import logging

logger = logging.getLogger(__name__)

_BASE = "https://data.europa.eu/api/hub/search/search"

def ec_search(query: str, limit: int = 25, publisher: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search EU Open Data Portal for datasets."""
    try:
        params = {
            "query": query,
            "limit": limit,
            "lang": "en"
        }
        
        if publisher:
            params["publisher"] = publisher
        
        data = http_json("GET", _BASE, params=params)
        items = (data.get("result") or {}).get("items") or []
        out = []
        
        for it in items[:limit]:
            # Extract title
            title_obj = it.get("title", {})
            if isinstance(title_obj, dict):
                title = title_obj.get("en") or title_obj.get("default", "")
            else:
                title = str(title_obj)
            
            # Extract URL
            landing_page = it.get("landingPage")
            if isinstance(landing_page, list) and landing_page:
                link = landing_page[0]
            else:
                link = landing_page or "https://data.europa.eu/"
            
            # Extract publisher
            prov = it.get("publisher", {})
            pub_name = None
            if isinstance(prov.get("name"), dict):
                pub_name = prov["name"].get("en") or prov["name"].get("default")
            elif prov.get("name"):
                pub_name = str(prov["name"])
            
            # Extract description
            desc_obj = it.get("description", {})
            if isinstance(desc_obj, dict):
                description = desc_obj.get("en") or desc_obj.get("default", "")
            else:
                description = str(desc_obj) if desc_obj else ""
            
            out.append({
                "title": title,
                "url": link,
                "snippet": description[:500],
                "source_domain": "data.europa.eu",
                "metadata": {
                    "provider": "ec",
                    "publisher": pub_name,
                    "keywords": it.get("keywords", [])
                }
            })
        
        return out
    except Exception as e:
        logger.warning(f"EC search failed: {e}")
        return []

def to_cards(rows: List[Dict[str, Any]]) -> List[dict]:
    """Convert EC results to evidence cards."""
    return [
        {
            "title": r["title"],
            "url": r["url"],
            "snippet": r.get("snippet", ""),
            "source_domain": "data.europa.eu",
            "metadata": {
                **r.get("metadata", {}),
                "license": "EU Open Data"
            }
        }
        for r in rows
    ]