"""Wikivoyage provider for travel and destination information."""

import logging
import requests
from typing import List, Dict, Any, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)


def search_destinations(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search Wikivoyage for travel destinations and information.
    
    Args:
        query: Search query (e.g., "beaches Portland", "hotels Paris")
        limit: Maximum number of results
        
    Returns:
        List of Wikivoyage articles
    """
    try:
        # Use Wikipedia API which includes Wikivoyage
        url = "https://en.wikivoyage.org/w/api.php"
        
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srnamespace": 0,  # Main namespace
            "srlimit": limit,
            "srinfo": "suggestion|totalhits",
            "srprop": "snippet|titlesnippet|size|wordcount|timestamp",
            "format": "json",
            "formatversion": 2
        }
        
        headers = {
            "User-Agent": "ResearchAgent/1.0"
        }
        
        logger.info(f"Wikivoyage search: {query}")
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("query", {}).get("search", [])
            logger.info(f"Wikivoyage found {len(results)} results")
            return results
        else:
            logger.warning(f"Wikivoyage error {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Wikivoyage search failed: {e}")
        return []


def get_page_content(title: str) -> Optional[Dict[str, Any]]:
    """
    Get full content of a Wikivoyage page.
    
    Args:
        title: Page title
        
    Returns:
        Page content dict or None
    """
    try:
        url = "https://en.wikivoyage.org/w/api.php"
        
        # Get page extract and sections
        params = {
            "action": "query",
            "titles": title,
            "prop": "extracts|sections|info",
            "exintro": True,
            "explaintext": True,
            "exsectionformat": "plain",
            "inprop": "url",
            "format": "json",
            "formatversion": 2
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            pages = data.get("query", {}).get("pages", [])
            return pages[0] if pages else None
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to get Wikivoyage page: {e}")
        return None


def extract_sections(title: str, sections: List[str] = None) -> Dict[str, str]:
    """
    Extract specific sections from a Wikivoyage article.
    
    Args:
        title: Article title
        sections: List of section names to extract (default: common travel sections)
        
    Returns:
        Dictionary mapping section names to content
    """
    if sections is None:
        sections = ["See", "Do", "Buy", "Eat", "Drink", "Sleep", "Stay safe", "Get in", "Get around"]
    
    try:
        url = "https://en.wikivoyage.org/w/api.php"
        
        # First get section structure
        params = {
            "action": "parse",
            "page": title,
            "prop": "sections",
            "format": "json"
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            return {}
            
        data = response.json()
        page_sections = data.get("parse", {}).get("sections", [])
        
        # Map section names to indices
        section_map = {}
        for sec in page_sections:
            if sec["line"] in sections:
                section_map[sec["line"]] = sec["index"]
        
        # Now get content for each section
        result = {}
        for section_name, section_idx in section_map.items():
            params = {
                "action": "parse",
                "page": title,
                "section": section_idx,
                "prop": "text",
                "format": "json",
                "disablelimitreport": True,
                "disableeditsection": True,
                "disabletoc": True
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                content = response.json().get("parse", {}).get("text", {}).get("*", "")
                # Clean HTML tags (basic cleaning)
                import re
                content = re.sub(r'<[^>]+>', '', content)
                content = re.sub(r'\s+', ' ', content).strip()
                if content:
                    result[section_name] = content[:1000]  # Limit length
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to extract sections: {e}")
        return {}


def to_cards(results: List[Dict[str, Any]], query: str = "") -> List[Dict[str, Any]]:
    """
    Convert Wikivoyage results to evidence cards.
    
    Args:
        results: Wikivoyage search results
        query: Original query
        
    Returns:
        List of evidence card dictionaries
    """
    cards = []
    
    for r in results:
        title = r.get("title", "")
        
        # Clean snippet HTML
        import re
        snippet = r.get("snippet", "")
        snippet = re.sub(r'<[^>]+>', '', snippet)
        snippet = re.sub(r'\s+', ' ', snippet).strip()
        
        # Build URL
        url_title = title.replace(" ", "_")
        url = f"https://en.wikivoyage.org/wiki/{quote(url_title)}"
        
        # Try to extract key sections for travel queries
        if any(word in query.lower() for word in ["beach", "hotel", "restaurant", "attraction", "things to do"]):
            sections = extract_sections(title, ["See", "Do", "Eat", "Sleep"])
            if sections:
                snippet_parts = [snippet]
                for sec_name, sec_content in sections.items():
                    if sec_content:
                        snippet_parts.append(f"{sec_name}: {sec_content[:200]}")
                snippet = ". ".join(snippet_parts)[:500]
        
        card = {
            "title": title,
            "url": url,
            "snippet": snippet if snippet else f"Travel guide for {title}",
            "source_domain": "wikivoyage.org",
            "provider": "wikivoyage",
            "credibility_score": 0.8,  # Community-edited but generally reliable
            "relevance_score": 0.75,
            "confidence": 0.6,
            "is_primary_source": False,
            "metadata": {
                "type": "travel_guide",
                "word_count": r.get("wordcount", 0),
                "last_updated": r.get("timestamp", "")
            }
        }
        
        cards.append(card)
    
    return cards


def get_destination_info(location: str) -> Optional[Dict[str, Any]]:
    """
    Get comprehensive travel information for a destination.
    
    Args:
        location: Destination name
        
    Returns:
        Travel information dict or None
    """
    # Search for the destination
    results = search_destinations(location, limit=1)
    if not results:
        return None
    
    title = results[0]["title"]
    
    # Get page content
    page = get_page_content(title)
    if not page:
        return None
    
    # Extract travel sections
    sections = extract_sections(title)
    
    return {
        "destination": title,
        "url": page.get("fullurl", ""),
        "summary": page.get("extract", "")[:500],
        "sections": sections,
        "metadata": {
            "page_id": page.get("pageid"),
            "last_modified": page.get("touched", "")
        }
    }