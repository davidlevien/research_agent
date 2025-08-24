"""
GDELT API connector for global news and events data
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
import datetime as dt
import logging

logger = logging.getLogger(__name__)


def search_gdelt(query: str, max_items: int = 10, mode: str = "artlist") -> List[Dict[str, Any]]:
    """
    Search GDELT for global news articles and events.
    GDELT monitors worldwide news in real-time.
    
    Args:
        query: Search query string
        max_items: Maximum number of articles to return (max 250)
        mode: Search mode ('artlist' for articles, 'timelinevol' for timeline)
    
    Returns:
        List of evidence-like dicts with title, url, date, etc.
    """
    if not query:
        return []
    
    try:
        import httpx
        
        # Build API URL
        base_url = "https://api.gdeltproject.org/api/v2/doc/doc"
        params = {
            "query": query,
            "mode": mode,
            "maxrecords": str(min(max_items, 250)),
            "format": "json",
            "sort": "hybridrel"  # Hybrid relevance sorting
        }
        
        logger.debug(f"Searching GDELT for: {query}")
        response = httpx.get(base_url, params=params, timeout=30)
        
        if response.status_code != 200:
            logger.warning(f"GDELT API returned status {response.status_code}")
            return []
        
        data = response.json()
        articles = data.get("articles", [])
        
        results = []
        for article in articles:
            # Extract title
            title = article.get("title")
            if not title:
                continue
            
            # Extract URL
            url = article.get("url")
            if not url:
                continue
            
            # Extract date
            date = None
            seendate = article.get("seendate")
            if seendate:
                try:
                    # GDELT date format: YYYYMMDDTHHmmSS
                    date = dt.datetime.strptime(seendate, "%Y%m%dT%H%M%S")
                except:
                    logger.debug(f"Could not parse GDELT date: {seendate}")
            
            # Extract domain/source
            domain = article.get("domain", "unknown")
            source_country = article.get("sourcecountry", "")
            
            # Extract language
            language = article.get("language", "")
            
            # Build snippet from available fields
            snippet_parts = []
            
            # Add tone if available (sentiment indicator)
            if "tone" in article:
                tone = article["tone"]
                if tone < -5:
                    snippet_parts.append("Tone: Very Negative")
                elif tone < -1:
                    snippet_parts.append("Tone: Negative")
                elif tone > 5:
                    snippet_parts.append("Tone: Very Positive")
                elif tone > 1:
                    snippet_parts.append("Tone: Positive")
                else:
                    snippet_parts.append("Tone: Neutral")
            
            # Add source country if available
            if source_country:
                snippet_parts.append(f"Source: {source_country}")
            
            # Add social media share count if available
            if "socialimage" in article:
                snippet_parts.append("Has social media presence")
            
            # Add article excerpt if available
            if "excerpt" in article:
                excerpt = article["excerpt"][:200]
                if len(article["excerpt"]) > 200:
                    excerpt += "..."
                snippet_parts.append(excerpt)
            
            snippet = " | ".join(snippet_parts) if snippet_parts else f"News from {domain}"
            
            # Calculate credibility based on GDELT metadata
            credibility = 0.6  # Base credibility for news
            
            # Adjust based on language (English sources often more verifiable)
            if language.lower() in ["english", "en"]:
                credibility += 0.05
            
            # Adjust based on domain reputation (simplified)
            reputable_domains = [
                "reuters.com", "apnews.com", "bloomberg.com", 
                "wsj.com", "ft.com", "economist.com", "bbc.com",
                "nytimes.com", "washingtonpost.com", "guardian.com"
            ]
            if any(rep in domain.lower() for rep in reputable_domains):
                credibility += 0.15
            
            # Build result
            result = {
                "title": title,
                "url": url,
                "date": date,
                "provider": "connector/gdelt",
                "snippet": snippet,
                "source_domain": domain,
                "source_country": source_country,
                "language": language,
                "tone": article.get("tone"),
                "credibility_score": min(0.85, credibility),
                "relevance_score": 0.65,
                "confidence": 0.60,
                "is_primary_source": False  # News is typically secondary
            }
            
            results.append(result)
        
        logger.info(f"GDELT returned {len(results)} results for '{query}'")
        return results
        
    except ImportError:
        logger.warning("httpx not available for GDELT connector")
        return []
    except Exception as e:
        logger.error(f"GDELT search failed: {e}")
        return []


def get_gdelt_timeline(query: str, start_date: dt.datetime = None, end_date: dt.datetime = None) -> Dict[str, Any]:
    """
    Get timeline data for a query from GDELT.
    Shows volume of coverage over time.
    
    Args:
        query: Search query
        start_date: Start date for timeline
        end_date: End date for timeline
    
    Returns:
        Timeline data with dates and volumes
    """
    if not query:
        return {}
    
    try:
        import httpx
        
        params = {
            "query": query,
            "mode": "timelinevol",
            "format": "json"
        }
        
        # Add date filters if provided
        if start_date:
            params["startdatetime"] = start_date.strftime("%Y%m%d%H%M%S")
        if end_date:
            params["enddatetime"] = end_date.strftime("%Y%m%d%H%M%S")
        
        response = httpx.get(
            "https://api.gdeltproject.org/api/v2/doc/doc",
            params=params,
            timeout=20
        )
        
        if response.status_code == 200:
            return response.json()
        
        return {}
        
    except Exception as e:
        logger.error(f"GDELT timeline fetch failed: {e}")
        return {}


def get_gdelt_trending(timespan: str = "1d") -> List[Dict[str, Any]]:
    """
    Get trending topics from GDELT.
    
    Args:
        timespan: Time span for trends ('1d', '7d', etc.)
    
    Returns:
        List of trending topics with metadata
    """
    try:
        import httpx
        
        # GDELT trending topics endpoint
        url = f"https://api.gdeltproject.org/api/v2/context/trending/{timespan}"
        
        response = httpx.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("topics", [])
        
        return []
        
    except Exception as e:
        logger.error(f"GDELT trending fetch failed: {e}")
        return []