"""PubMed provider for biomedical literature."""

from __future__ import annotations
from typing import List, Dict, Any
from .http import http_json_with_policy as http_json
import os
import logging

logger = logging.getLogger(__name__)

_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

def pubmed_search(query: str, retmax: int = 25) -> List[Dict[str, Any]]:
    """Search PubMed for biomedical literature. Requires email for NCBI compliance."""
    contact_email = os.getenv("CONTACT_EMAIL", "research@example.com")
    
    try:
        # Search for PMIDs
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": retmax,
            "tool": "research-agent",
            "email": contact_email
        }
        
        s = http_json("pubmed", "GET", _ESEARCH, params=search_params)
        ids = (s.get("esearchresult", {}).get("idlist")) or []
        
        if not ids:
            return []
        
        # Fetch summaries for PMIDs
        summary_params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "json",
            "tool": "research-agent",
            "email": contact_email
        }
        
        sumry = http_json("pubmed", "GET", _ESUMMARY, params=summary_params)
        res = sumry.get("result", {})
        items = []
        
        for pmid in ids:
            it = res.get(pmid) or {}
            title = it.get("title", "")
            
            # Extract authors
            authors = it.get("authors", [])
            author_names = [a.get("name", "") for a in authors[:3]]
            
            # Extract publication info
            pub_date = it.get("pubdate", "")
            journal = it.get("source", "")
            
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            
            items.append({
                "title": title,
                "url": url,
                "snippet": f"{journal}. {pub_date}. {', '.join(author_names)}",
                "source_domain": "nih.gov",
                "pmid": pmid,
                "authors": author_names,
                "journal": journal,
                "pub_date": pub_date
            })
        
        return items
    except Exception as e:
        logger.warning(f"PubMed search failed: {e}")
        return []

def to_cards(rows: List[Dict[str, Any]]) -> List[dict]:
    """Convert PubMed results to evidence cards."""
    return [
        {
            "title": r["title"],
            "url": r["url"],
            "snippet": r.get("snippet", ""),
            "source_domain": "nih.gov",
            "metadata": {
                "provider": "pubmed",
                "pmid": r.get("pmid"),
                "authors": r.get("authors", []),
                "journal": r.get("journal"),
                "pub_date": r.get("pub_date"),
                "license": "Public Domain/NLM"
            }
        }
        for r in rows
    ]