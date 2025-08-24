"""CORE Academic connector for secondary metadata fallback."""

import httpx
from typing import Dict, Any, Optional


def core_by_doi(doi: str) -> Dict[str, Any]:
    """
    Fetch metadata from CORE by DOI.
    
    Args:
        doi: DOI identifier
        
    Returns:
        Dictionary with paper metadata
    """
    try:
        r = httpx.get(
            "https://api.core.ac.uk/v3/search/works",
            params={"q": f"doi:{doi}", "limit": 1},
            timeout=20,
            headers={"Accept": "application/json"}
        )
        
        if r.status_code != 200:
            return {}
            
        data = r.json()
        hits = data.get("results", [])
        return hits[0] if hits else {}
        
    except Exception:
        return {}


def core_search(query: str, limit: int = 10) -> list[Dict[str, Any]]:
    """
    Search CORE for academic papers.
    
    Args:
        query: Search query
        limit: Maximum results
        
    Returns:
        List of paper metadata dictionaries
    """
    try:
        r = httpx.get(
            "https://api.core.ac.uk/v3/search/works",
            params={"q": query, "limit": limit},
            timeout=20,
            headers={"Accept": "application/json"}
        )
        
        if r.status_code != 200:
            return []
            
        data = r.json()
        return data.get("results", [])
        
    except Exception:
        return []


def get_oa_pdf_from_core(doi: str) -> Optional[str]:
    """
    Get Open Access PDF URL from CORE.
    
    Args:
        doi: DOI identifier
        
    Returns:
        URL to OA PDF if available
    """
    metadata = core_by_doi(doi)
    
    if not metadata:
        return None
    
    # CORE provides downloadUrl field
    download_url = metadata.get("downloadUrl")
    if download_url:
        return download_url
        
    # Alternative: check links array
    links = metadata.get("links", [])
    for link in links:
        if link.get("type") == "download":
            return link.get("url")
            
    return None