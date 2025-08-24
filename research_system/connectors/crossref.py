"""
Crossref API connector for academic papers and research
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
import datetime as dt
import logging

logger = logging.getLogger(__name__)


def search_crossref(query: str, rows: int = 5, filter_type: str = None) -> List[Dict[str, Any]]:
    """
    Search Crossref for academic papers and research.
    
    Args:
        query: Search query string
        rows: Number of results to return (max 1000)
        filter_type: Optional filter for work type (e.g., 'journal-article', 'book-chapter')
    
    Returns:
        List of evidence-like dicts with title, url, date, etc.
    """
    if not query:
        return []
    
    try:
        import httpx
        
        # Build API URL
        base_url = "https://api.crossref.org/works"
        params = {
            "query": query,
            "rows": min(rows, 1000),
            "select": "DOI,title,published-print,published-online,URL,author,publisher,subject,type,abstract"
        }
        
        if filter_type:
            params["filter"] = f"type:{filter_type}"
        
        # Make request with proper User-Agent
        headers = {
            "User-Agent": "ResearchSystem/1.0 (mailto:research@example.com)"
        }
        
        logger.debug(f"Searching Crossref for: {query}")
        response = httpx.get(base_url, params=params, headers=headers, timeout=25)
        
        if response.status_code != 200:
            logger.warning(f"Crossref API returned status {response.status_code}")
            return []
        
        data = response.json()
        items = data.get("message", {}).get("items", [])
        
        results = []
        for item in items:
            # Extract title
            title_list = item.get("title", [])
            title = title_list[0] if title_list else None
            
            if not title:
                continue
            
            # Extract date
            date = None
            date_parts = None
            
            # Try published-print first, then published-online
            for date_field in ["published-print", "published-online", "created"]:
                if date_field in item:
                    date_info = item[date_field]
                    if "date-parts" in date_info and date_info["date-parts"]:
                        date_parts = date_info["date-parts"][0]
                        break
            
            if date_parts and len(date_parts) > 0:
                year = date_parts[0] if len(date_parts) > 0 else None
                month = date_parts[1] if len(date_parts) > 1 else 1
                day = date_parts[2] if len(date_parts) > 2 else 1
                
                if year:
                    try:
                        date = dt.datetime(year, month, day)
                    except:
                        date = dt.datetime(year, 1, 1)
            
            # Extract URL
            url = item.get("URL")
            if not url and item.get("DOI"):
                url = f"https://doi.org/{item['DOI']}"
            
            # Extract authors
            authors = []
            for author in item.get("author", [])[:3]:  # Limit to first 3 authors
                name_parts = []
                if author.get("given"):
                    name_parts.append(author["given"])
                if author.get("family"):
                    name_parts.append(author["family"])
                if name_parts:
                    authors.append(" ".join(name_parts))
            
            author_str = ", ".join(authors) if authors else None
            
            # Extract publisher
            publisher = item.get("publisher")
            
            # Extract abstract or create snippet
            abstract = item.get("abstract", "")
            if abstract:
                # Clean abstract HTML tags if present
                import re
                abstract = re.sub(r'<[^>]+>', '', abstract)
                snippet = abstract[:500] + "..." if len(abstract) > 500 else abstract
            else:
                snippet = f"DOI: {item.get('DOI', 'N/A')}"
                if author_str:
                    snippet += f" | Authors: {author_str}"
            
            # Build result
            result = {
                "title": title,
                "url": url,
                "date": date,
                "provider": "connector/crossref",
                "snippet": snippet,
                "author": author_str,
                "publisher": publisher,
                "doi": item.get("DOI"),
                "type": item.get("type", "article"),
                "credibility_score": 0.85,  # Academic sources are generally credible
                "relevance_score": 0.6,
                "confidence": 0.75,
                "is_primary_source": True
            }
            
            results.append(result)
        
        logger.info(f"Crossref returned {len(results)} results for '{query}'")
        return results
        
    except ImportError:
        logger.warning("httpx not available for Crossref connector")
        return []
    except Exception as e:
        logger.error(f"Crossref search failed: {e}")
        return []


def get_crossref_metadata(doi: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed metadata for a specific DOI from Crossref.
    
    Args:
        doi: The DOI to look up
    
    Returns:
        Detailed metadata dict or None if not found
    """
    if not doi:
        return None
    
    try:
        import httpx
        
        # Clean DOI
        doi = doi.replace("https://doi.org/", "").replace("http://dx.doi.org/", "")
        
        url = f"https://api.crossref.org/works/{doi}"
        headers = {
            "User-Agent": "ResearchSystem/1.0 (mailto:research@example.com)"
        }
        
        response = httpx.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("message", {})
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to get Crossref metadata for {doi}: {e}")
        return None