"""Crossref provider for DOI resolution and scholarly metadata."""

from typing import List, Dict, Any, Optional
from .http import http_json_with_policy as http_json
import logging

logger = logging.getLogger(__name__)

BASE = "https://api.crossref.org/works"

def crossref_query(
    q: str, 
    from_date: Optional[str] = None, 
    until_date: Optional[str] = None, 
    rows: int = 25
) -> List[Dict[str, Any]]:
    """Query Crossref for scholarly works."""
    try:
        filt = []
        if from_date:
            filt.append(f"from-pub-date:{from_date}")
        if until_date:
            filt.append(f"until-pub-date:{until_date}")
        
        params = {"query": q, "rows": rows}
        if filt:
            params["filter"] = ",".join(filt)
        
        data = http_json("crossref", "GET", BASE, params=params)
        return data.get("message", {}).get("items", [])
    except Exception as e:
        logger.warning(f"Crossref query failed: {e}")
        return []

def to_cards(items: List[Dict[str, Any]]) -> List[Dict]:
    """Convert Crossref results to evidence card format."""
    cards = []
    for it in items:
        try:
            doi = it.get("DOI", "")
            url = it.get("URL") or (f"https://doi.org/{doi}" if doi else None)
            
            if not url:
                continue
            
            # Extract title (often in array format)
            title_arr = it.get("title", [])
            title = title_arr[0] if title_arr else ""
            
            # Extract publication date
            date_parts = it.get("issued", {}).get("date-parts", [[]])
            year = date_parts[0][0] if date_parts and date_parts[0] else None
            
            # Extract authors
            authors = it.get("author", [])
            author_names = []
            for a in authors[:3]:  # First 3 authors
                given = a.get("given", "")
                family = a.get("family", "")
                if family:
                    author_names.append(f"{given} {family}".strip())
            
            cards.append({
                "title": title,
                "url": url,
                "source_domain": "doi.org" if doi else "crossref.org",
                "published_at": f"{year}-01-01" if year else None,
                "metadata": {
                    "provider": "crossref",
                    "doi": doi,
                    "authors": ", ".join(author_names),
                    "publisher": it.get("publisher", ""),
                    "type": it.get("type", ""),
                    "citations": it.get("is-referenced-by-count", 0)
                }
            })
        except Exception as e:
            logger.debug(f"Failed to process Crossref result: {e}")
            continue
    
    return cards