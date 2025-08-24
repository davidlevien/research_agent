"""
OpenAlex API connector for open academic data
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
import datetime as dt
import logging

logger = logging.getLogger(__name__)


def search_openalex(query: str, per_page: int = 5, filter_params: Dict = None) -> List[Dict[str, Any]]:
    """
    Search OpenAlex for academic papers and research.
    OpenAlex provides free, open access to academic metadata.
    
    Args:
        query: Search query string
        per_page: Number of results per page (max 200)
        filter_params: Optional filters (e.g., {'publication_year': '>2020'})
    
    Returns:
        List of evidence-like dicts with title, url, date, etc.
    """
    if not query:
        return []
    
    try:
        import httpx
        
        # Build API URL
        base_url = "https://api.openalex.org/works"
        params = {
            "search": query,
            "per-page": min(per_page, 200),
            "mailto": "research@example.com"  # Polite crawling
        }
        
        # Add filters if provided
        if filter_params:
            filter_parts = []
            for key, value in filter_params.items():
                filter_parts.append(f"{key}:{value}")
            if filter_parts:
                params["filter"] = ",".join(filter_parts)
        
        logger.debug(f"Searching OpenAlex for: {query}")
        response = httpx.get(base_url, params=params, timeout=25)
        
        if response.status_code != 200:
            logger.warning(f"OpenAlex API returned status {response.status_code}")
            return []
        
        data = response.json()
        items = data.get("results", [])
        
        results = []
        for item in items:
            # Extract title
            title = item.get("title")
            if not title:
                continue
            
            # Extract URL - prefer landing page, then DOI
            url = None
            primary_location = item.get("primary_location", {})
            if primary_location:
                url = primary_location.get("landing_page_url")
                if not url:
                    source = primary_location.get("source", {})
                    if source:
                        url = source.get("homepage_url")
            
            if not url and item.get("doi"):
                url = item["doi"]
            
            # Extract date
            date = None
            year = item.get("publication_year")
            if year:
                # Try to get more precise date
                pub_date = item.get("publication_date")
                if pub_date:
                    try:
                        date = dt.datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    except:
                        date = dt.datetime(year, 1, 1)
                else:
                    date = dt.datetime(year, 1, 1)
            
            # Extract authors
            authors = []
            for authorship in item.get("authorships", [])[:3]:  # First 3 authors
                author = authorship.get("author", {})
                if author.get("display_name"):
                    authors.append(author["display_name"])
            
            author_str = ", ".join(authors) if authors else None
            
            # Extract publisher/venue
            publisher = None
            if primary_location and primary_location.get("source"):
                publisher = primary_location["source"].get("display_name")
            
            # Create snippet from abstract or metadata
            snippet_parts = []
            
            # Try to get abstract from inverted index
            abstract_inverted = item.get("abstract_inverted_index")
            if abstract_inverted:
                # Reconstruct abstract from inverted index
                word_positions = []
                for word, positions in abstract_inverted.items():
                    for pos in positions:
                        word_positions.append((pos, word))
                word_positions.sort()
                abstract_words = [word for _, word in word_positions[:100]]  # First 100 words
                snippet = " ".join(abstract_words)
                if len(word_positions) > 100:
                    snippet += "..."
            else:
                # Build snippet from metadata
                if item.get("doi"):
                    snippet_parts.append(f"DOI: {item['doi']}")
                if item.get("cited_by_count"):
                    snippet_parts.append(f"Cited by: {item['cited_by_count']}")
                if publisher:
                    snippet_parts.append(f"Published in: {publisher}")
                snippet = " | ".join(snippet_parts) if snippet_parts else title[:200]
            
            # Get topics/concepts for better categorization
            topics = []
            for concept in item.get("concepts", [])[:3]:
                if concept.get("display_name"):
                    topics.append(concept["display_name"])
            
            # Build result
            result = {
                "title": title,
                "url": url,
                "date": date,
                "provider": "connector/openalex",
                "snippet": snippet,
                "author": author_str,
                "publisher": publisher,
                "doi": item.get("doi"),
                "cited_by_count": item.get("cited_by_count", 0),
                "topics": topics,
                "open_access": item.get("open_access", {}).get("is_oa", False),
                "credibility_score": 0.80,  # Academic sources
                "relevance_score": 0.65,
                "confidence": 0.70,
                "is_primary_source": True
            }
            
            # Boost credibility for highly cited papers
            if result["cited_by_count"] > 100:
                result["credibility_score"] = min(0.95, result["credibility_score"] + 0.1)
            
            results.append(result)
        
        logger.info(f"OpenAlex returned {len(results)} results for '{query}'")
        return results
        
    except ImportError:
        logger.warning("httpx not available for OpenAlex connector")
        return []
    except Exception as e:
        logger.error(f"OpenAlex search failed: {e}")
        return []


def get_openalex_work(work_id: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific work from OpenAlex.
    
    Args:
        work_id: OpenAlex work ID (e.g., 'W2741809807') or DOI
    
    Returns:
        Detailed work metadata or None
    """
    if not work_id:
        return None
    
    try:
        import httpx
        
        # Handle DOI format
        if work_id.startswith("10.") or "doi.org" in work_id:
            work_id = f"https://doi.org/{work_id.replace('https://doi.org/', '')}"
        
        url = f"https://api.openalex.org/works/{work_id}"
        params = {"mailto": "research@example.com"}
        
        response = httpx.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            return response.json()
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to get OpenAlex work {work_id}: {e}")
        return None


def search_openalex_authors(author_name: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search for authors in OpenAlex.
    
    Args:
        author_name: Author name to search for
        limit: Maximum number of results
    
    Returns:
        List of author metadata dicts
    """
    if not author_name:
        return []
    
    try:
        import httpx
        
        url = "https://api.openalex.org/authors"
        params = {
            "search": author_name,
            "per-page": limit,
            "mailto": "research@example.com"
        }
        
        response = httpx.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("results", [])
        
        return []
        
    except Exception as e:
        logger.error(f"OpenAlex author search failed: {e}")
        return []