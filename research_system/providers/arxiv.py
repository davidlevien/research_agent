"""arXiv provider for preprints and scientific papers."""

from __future__ import annotations
from typing import List, Dict
from urllib.parse import quote
import xml.etree.ElementTree as ET
import httpx
from .http import DEFAULT_TIMEOUT, RETRY_STATUSES
import logging
import time

logger = logging.getLogger(__name__)

_BASE = "https://export.arxiv.org/api/query"
_last_call = 0

def arxiv_search(query: str, max_results: int = 25) -> List[Dict]:
    """Search arXiv for papers. Respects 3-second rate limit."""
    global _last_call
    
    # Enforce 3-second minimum between requests
    now = time.time()
    if _last_call > 0:
        elapsed = now - _last_call
        if elapsed < 3:
            time.sleep(3 - elapsed)
    _last_call = time.time()
    
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results
    }
    
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT, headers={"User-Agent": "research-agent/1.0"}) as client:
            r = client.get(_BASE, params=params)
            # Retry on soft errors
            if r.status_code in RETRY_STATUSES:
                time.sleep(3)  # Respect rate limit on retry
                r = client.get(_BASE, params=params)
                _last_call = time.time()
            r.raise_for_status()
            root = ET.fromstring(r.text)
    except Exception as e:
        logger.warning(f"arXiv search failed: {e}")
        return []
    
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    
    for entry in root.findall("a:entry", ns):
        title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
        summary = (entry.findtext("a:summary", default="", namespaces=ns) or "").strip()
        
        # Find HTML link
        link = None
        for l in entry.findall("a:link", ns):
            if l.attrib.get("type") == "text/html":
                link = l.attrib.get("href")
                break
        
        if not link:
            idt = entry.findtext("a:id", default="", namespaces=ns) or ""
            link = idt
        
        # Extract arXiv ID from link
        arxiv_id = None
        if "arxiv.org/abs/" in link:
            arxiv_id = link.split("/abs/")[-1]
        
        out.append({
            "title": title,
            "url": link,
            "snippet": summary[:500],
            "source_domain": "arxiv.org",
            "arxiv_id": arxiv_id
        })
    
    return out

def to_cards(rows: List[Dict]) -> List[dict]:
    """Convert arXiv results to evidence cards."""
    return [
        {
            "title": r["title"],
            "url": r["url"],
            "snippet": r.get("snippet", ""),
            "source_domain": "arxiv.org",
            "metadata": {
                "provider": "arxiv",
                "arxiv_id": r.get("arxiv_id"),
                "license": "arXiv License"
            }
        }
        for r in rows
    ]