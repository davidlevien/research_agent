"""World Bank API provider for development indicators."""

from __future__ import annotations
from typing import List, Dict, Any
from .http import http_json_with_policy as http_json
import logging

logger = logging.getLogger(__name__)

_INDICATORS = "https://api.worldbank.org/v2/indicator"

def _indicators_page(per_page: int = 1000, page: int = 1) -> List[Dict[str, Any]]:
    """Fetch a page of World Bank indicators."""
    try:
        data = http_json("worldbank", "GET", _INDICATORS, params={"format": "json", "per_page": per_page, "page": page})
        # data[0] is paging/meta, data[1] is list
        return (data[1] if isinstance(data, list) and len(data) > 1 else []) or []
    except Exception as e:
        logger.warning(f"World Bank indicators fetch failed: {e}")
        return []

def search_worldbank(query: str, limit: int = 25) -> List[Dict[str, Any]]:
    """Search World Bank indicators by relevance to query."""
    q = (query or "").lower()
    rows = _indicators_page(per_page=1000, page=1)
    
    # Simple relevance: token overlap on name/sourceNote/id
    toks = [t for t in q.replace("/", " ").split() if t]
    
    def score(r):
        hay = " ".join(str(r.get(k, "") or "") for k in ("name", "sourceNote", "id")).lower()
        return sum(hay.count(t) for t in toks)
    
    ranked = sorted(rows, key=score, reverse=True)
    return ranked[:limit]

def to_cards(rows: List[Dict[str, Any]]) -> List[dict]:
    """Convert World Bank indicators to evidence cards."""
    cards = []
    for r in rows:
        code = r.get("id")
        title = r.get("name") or code
        url = f"https://data.worldbank.org/indicator/{code}" if code else "https://data.worldbank.org/"
        
        cards.append({
            "title": title,
            "url": url,
            "snippet": r.get("sourceNote", "")[:500],
            "source_domain": "worldbank.org",
            "metadata": {
                "provider": "worldbank",
                "indicator": code,
                "source": r.get("source", {}).get("value"),
                "license": "CC BY-4.0"  # World Bank Open Data license
            }
        })
    return cards