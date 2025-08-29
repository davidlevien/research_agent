"""OpenAlex client with robust error handling and Crossref fallback."""

import httpx
import urllib.parse
import time
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

BASE = "https://api.openalex.org/works"
CROSSREF_BASE = "https://api.crossref.org/works"

def _get(client: httpx.Client, url: str) -> Dict[str, Any]:
    """Make HTTP GET request with error handling."""
    r = client.get(url, timeout=20)
    r.raise_for_status()
    return r.json()

def search_works(query: str, per_page: int = 10) -> List[Dict[str, Any]]:
    """
    Search OpenAlex for academic works.
    
    Uses 'search=' parameter for free text search.
    If 400 error, sanitizes query and retries.
    
    Args:
        query: Search query
        per_page: Number of results to return
        
    Returns:
        List of work dictionaries
    """
    # Clean and encode query
    q = urllib.parse.quote_plus(query.strip())
    
    # Build URL with proper parameters
    url = f"{BASE}?search={q}&per_page={per_page}&select=id,title,doi,authorships,host_venue,publication_year,cited_by_count"
    
    with httpx.Client(headers={"User-Agent": "research-agent/1.0"}) as client:
        try:
            data = _get(client, url)
            results = data.get("results", data.get("data", []))
            logger.info(f"OpenAlex returned {len(results)} results for '{query}'")
            return results
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                logger.warning(f"OpenAlex 400 error for query '{query}', trying simplified query")
                
                # Simplify query: remove special characters, quotes
                simplified = " ".join(query.replace('"', '').replace(':', ' ').split())
                q = urllib.parse.quote_plus(simplified)
                url = f"{BASE}?search={q}&per_page={per_page}&select=id,title,doi,authorships,host_venue,publication_year"
                
                try:
                    data = _get(client, url)
                    results = data.get("results", data.get("data", []))
                    logger.info(f"OpenAlex retry successful: {len(results)} results")
                    return results
                except Exception as e2:
                    logger.error(f"OpenAlex retry failed: {e2}")
                    raise
            else:
                logger.error(f"OpenAlex HTTP error {e.response.status_code}")
                raise

def crossref_fallback(query: str, per_page: int = 10) -> List[Dict[str, Any]]:
    """
    Fallback to Crossref API when OpenAlex fails.
    
    Args:
        query: Search query
        per_page: Number of results
        
    Returns:
        List of work dictionaries (OpenAlex-compatible format)
    """
    url = f"{CROSSREF_BASE}?query={urllib.parse.quote_plus(query)}&rows={per_page}"
    
    try:
        with httpx.Client(timeout=20) as client:
            r = client.get(url)
            r.raise_for_status()
            j = r.json()
            
            items = j.get("message", {}).get("items", [])
            
            # Convert Crossref format to OpenAlex-compatible format
            out = []
            for item in items:
                # Extract first author if available
                authors = item.get("author", [])
                first_author = authors[0] if authors else {}
                
                # Build OpenAlex-like structure
                work = {
                    "id": f"crossref:{item.get('DOI', '')}",
                    "title": " ".join(item.get("title", ["Untitled"])),
                    "doi": item.get("DOI"),
                    "host_venue": {
                        "display_name": " ".join(item.get("container-title", [""])),
                        "issn": item.get("ISSN", [""])[0] if item.get("ISSN") else None
                    },
                    "publication_year": None,
                    "cited_by_count": item.get("is-referenced-by-count", 0),
                    "authorships": []
                }
                
                # Extract year from date-parts
                date_parts = item.get("issued", {}).get("date-parts", [[]])
                if date_parts and date_parts[0]:
                    work["publication_year"] = date_parts[0][0]
                
                # Add author info
                if first_author:
                    work["authorships"].append({
                        "author": {
                            "display_name": f"{first_author.get('given', '')} {first_author.get('family', '')}".strip()
                        }
                    })
                
                out.append(work)
            
            logger.info(f"Crossref returned {len(out)} results for '{query}'")
            return out
            
    except Exception as e:
        logger.error(f"Crossref fallback failed: {e}")
        return []

def robust_lookup(query: str, per_page: int = 10) -> List[Dict[str, Any]]:
    """
    Robust academic search with automatic fallback.
    
    Tries OpenAlex first, falls back to Crossref if needed.
    
    Args:
        query: Search query
        per_page: Number of results
        
    Returns:
        List of work dictionaries
    """
    try:
        # Try OpenAlex first
        results = search_works(query, per_page)
        if results:
            return results
            
    except Exception as e:
        logger.warning(f"OpenAlex failed ({e}), trying Crossref fallback")
    
    # Fallback to Crossref
    try:
        return crossref_fallback(query, per_page)
    except Exception as e:
        logger.error(f"Both OpenAlex and Crossref failed: {e}")
        return []

def get_work_by_doi(doi: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific work by DOI.
    
    Args:
        doi: DOI identifier
        
    Returns:
        Work dictionary or None
    """
    # Clean DOI
    doi = doi.strip()
    if doi.startswith("doi:"):
        doi = doi[4:]
    if doi.startswith("10."):
        # Valid DOI format
        pass
    else:
        logger.warning(f"Invalid DOI format: {doi}")
        return None
    
    # Try OpenAlex
    try:
        url = f"https://api.openalex.org/works/doi:{doi}"
        with httpx.Client(headers={"User-Agent": "research-agent/1.0"}) as client:
            r = client.get(url, timeout=10)
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        logger.debug(f"OpenAlex DOI lookup failed: {e}")
    
    # Try Crossref
    try:
        url = f"https://api.crossref.org/works/{doi}"
        with httpx.Client() as client:
            r = client.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()["message"]
                # Convert to OpenAlex format
                return {
                    "id": f"crossref:{doi}",
                    "doi": doi,
                    "title": " ".join(data.get("title", [""])),
                    "publication_year": data.get("published-print", {}).get("date-parts", [[None]])[0][0],
                    "host_venue": {
                        "display_name": " ".join(data.get("container-title", [""]))
                    }
                }
    except Exception as e:
        logger.debug(f"Crossref DOI lookup failed: {e}")
    
    return None

def enrich_with_citations(works: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enrich works with citation information.
    
    Args:
        works: List of work dictionaries
        
    Returns:
        Enriched list with peer_reviewed flags
    """
    for work in works:
        # Mark as peer-reviewed if from known journal
        venue = work.get("host_venue", {}).get("display_name", "").lower()
        
        peer_reviewed_venues = [
            "nature", "science", "cell", "pnas", "lancet",
            "new england journal", "jama", "bmj", "plos",
            "proceedings", "journal", "review"
        ]
        
        is_peer_reviewed = any(v in venue for v in peer_reviewed_venues)
        work["peer_reviewed"] = is_peer_reviewed
        
        # Add credibility score based on citations
        citations = work.get("cited_by_count", 0)
        if citations > 100:
            work["credibility_score"] = 0.9
        elif citations > 10:
            work["credibility_score"] = 0.7
        else:
            work["credibility_score"] = 0.5
    
    return works