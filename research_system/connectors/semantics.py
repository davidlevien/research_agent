"""Semantic Scholar connector for secondary metadata fallback."""

import httpx
from typing import Dict, Any, Optional


def s2_by_doi(doi: str) -> Dict[str, Any]:
    """
    Fetch metadata from Semantic Scholar by DOI.
    
    Args:
        doi: DOI identifier
        
    Returns:
        Dictionary with title, abstract, year, venue, openAccessPdf
    """
    try:
        r = httpx.get(
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}",
            params={"fields": "title,abstract,year,venue,openAccessPdf"},
            timeout=20
        )
        
        if r.status_code != 200:
            return {}
            
        return r.json()
        
    except Exception:
        return {}


def s2_by_title(title: str, limit: int = 3) -> list[Dict[str, Any]]:
    """
    Search Semantic Scholar by title.
    
    Args:
        title: Paper title to search
        limit: Maximum results
        
    Returns:
        List of paper metadata dictionaries
    """
    try:
        r = httpx.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={
                "query": title,
                "fields": "title,abstract,year,venue,openAccessPdf,doi",
                "limit": limit
            },
            timeout=20
        )
        
        if r.status_code != 200:
            return []
            
        data = r.json()
        return data.get("data", [])
        
    except Exception:
        return []


def get_oa_pdf_from_s2(doi: str) -> Optional[str]:
    """
    Get Open Access PDF URL from Semantic Scholar.
    
    Args:
        doi: DOI identifier
        
    Returns:
        URL to OA PDF if available
    """
    metadata = s2_by_doi(doi)
    
    if not metadata:
        return None
        
    oa_pdf = metadata.get("openAccessPdf")
    if oa_pdf and isinstance(oa_pdf, dict):
        return oa_pdf.get("url")
        
    return None