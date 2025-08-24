"""DOI extraction and Crossref metadata fallback for gated primary sources."""

from __future__ import annotations
import re
import httpx
import datetime as dt
from typing import Optional, Dict, Any

# Pattern to extract DOI from URLs
_DOI_RE = re.compile(r"/doi/(?:abs/|pdf/|full/)?(?P<doi>10\.\d{4,9}/[^\s?#]+)", re.I)


def extract_doi(url: str) -> Optional[str]:
    """
    Extract DOI from a URL.
    
    Args:
        url: URL potentially containing a DOI
        
    Returns:
        DOI string if found, None otherwise
    """
    if not url:
        return None
    m = _DOI_RE.search(url)
    return m.group("doi") if m else None


def crossref_meta(doi: str) -> Dict[str, Any]:
    """
    Fetch metadata from Crossref for a given DOI.
    
    Args:
        doi: DOI identifier
        
    Returns:
        Dictionary with title, abstract, date fields (may be empty)
    """
    try:
        r = httpx.get(
            f"https://api.crossref.org/works/{doi}",
            timeout=20,
            headers={"User-Agent": "ResearchAgent/1.0"}
        )
        if r.status_code != 200:
            return {}
            
        item = r.json().get("message", {})
        
        # Extract title (first item in title array)
        title = (item.get("title") or [None])[0]
        
        # Extract abstract (may contain JATS markup)
        abstract = item.get("abstract")
        
        # Extract publication date
        date = None
        issued = item.get("issued", {}).get("date-parts", [[None]])[0]
        if issued and len(issued) > 0 and isinstance(issued[0], int):
            # Create datetime with year, defaulting to January 1st
            year = issued[0]
            month = issued[1] if len(issued) > 1 and issued[1] else 1
            day = issued[2] if len(issued) > 2 and issued[2] else 1
            try:
                date = dt.datetime(year, month, day)
            except (ValueError, TypeError):
                date = dt.datetime(year, 1, 1) if year else None
        
        return {
            "title": title,
            "abstract": abstract,
            "date": date
        }
    except Exception:
        return {}