"""
Light HTML enrichment for evidence cards.
Safe, time-bounded extraction of text from HTML pages only.
PDFs and non-HTML content are skipped (keeping original snippet).
"""

from __future__ import annotations
import httpx
from bs4 import BeautifulSoup
from typing import Optional
import logging

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ResearchAgent/1.0)"}
TIMEOUT = httpx.Timeout(10.0, connect=5.0)

def fetch_excerpt(url: str, max_chars: int = 800) -> Optional[str]:
    """
    Fetch and extract a short excerpt from HTML pages.
    PDFs and non-HTML return None (we keep snippet).
    Safe defaults: small timeouts, no streaming.
    
    Args:
        url: URL to fetch content from
        max_chars: Maximum characters to extract
        
    Returns:
        Extracted text excerpt or None if not HTML/failed
    """
    try:
        with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True, limits=httpx.Limits(max_redirects=3)) as client:
            r = client.get(url)
            ct = r.headers.get("content-type", "").lower()
            
            # Only process HTML content
            if "text/html" not in ct:
                return None
                
            # Parse HTML
            soup = BeautifulSoup(r.text, "html.parser")
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Prefer article content, fallback to body paragraphs
            article = soup.find("article")
            if article:
                paras = article.find_all("p")
            else:
                # Try main content areas
                for selector in ["main", "div.content", "div#content", "div.article"]:
                    content = soup.select_one(selector)
                    if content:
                        paras = content.find_all("p")
                        break
                else:
                    # Fallback to all paragraphs
                    paras = soup.find_all("p")
            
            # Extract and clean text
            text_parts = []
            for p in paras:
                text = p.get_text(" ", strip=True)
                if text and len(text) > 50:  # Skip very short paragraphs
                    text_parts.append(text)
                    
            # Join and normalize whitespace
            full_text = " ".join(text_parts)
            full_text = " ".join(full_text.split())  # normalize whitespace
            
            # Return truncated excerpt
            return full_text[:max_chars] if full_text else None
            
    except httpx.TimeoutException:
        logger.debug(f"Timeout fetching {url}")
        return None
    except Exception as e:
        logger.debug(f"Error fetching {url}: {e}")
        return None