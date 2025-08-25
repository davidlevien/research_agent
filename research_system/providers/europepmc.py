"""Europe PMC provider for biomedical literature."""

from __future__ import annotations
from typing import List, Dict, Any
from .http import http_json
import logging

logger = logging.getLogger(__name__)

_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

def europepmc_search(query: str, page_size: int = 25) -> List[Dict[str, Any]]:
    """Search Europe PMC for biomedical literature."""
    try:
        data = http_json(
            "GET", 
            _BASE, 
            params={
                "query": query,
                "format": "json",
                "pageSize": page_size
            }
        )
        
        hits = (data.get("resultList", {}) or {}).get("result") or []
        out = []
        
        for h in hits:
            title = h.get("title", "")
            doi = h.get("doi")
            pmid = h.get("pmid")
            pmcid = h.get("pmcid")
            
            # Try to get best available URL
            url = None
            full_text_urls = h.get("fullTextUrlList", {}).get("fullTextUrl", [])
            for ft in full_text_urls:
                if ft.get("documentStyle") == "html" or ft.get("documentStyle") == "pdf":
                    url = ft.get("url")
                    break
            
            if not url and doi:
                url = f"https://doi.org/{doi}"
            elif not url and pmid:
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            elif not url:
                url = f"https://europepmc.org/article/{h.get('source', 'MED')}/{h.get('id', '')}"
            
            # Extract metadata
            authors = h.get("authorString", "")
            journal = h.get("journalTitle", "")
            pub_year = h.get("pubYear", "")
            
            abstract = h.get("abstractText", "")
            snippet = abstract[:500] if abstract else f"{journal}. {pub_year}. {authors[:200]}"
            
            out.append({
                "title": title,
                "url": url,
                "snippet": snippet,
                "source_domain": "europepmc.org",
                "doi": doi,
                "pmid": pmid,
                "pmcid": pmcid,
                "authors": authors,
                "journal": journal,
                "pub_year": pub_year
            })
        
        return out
    except Exception as e:
        logger.warning(f"Europe PMC search failed: {e}")
        return []

def to_cards(rows: List[Dict[str, Any]]) -> List[dict]:
    """Convert Europe PMC results to evidence cards."""
    return [
        {
            "title": r["title"],
            "url": r["url"],
            "snippet": r.get("snippet", ""),
            "source_domain": "europepmc.org",
            "metadata": {
                "provider": "europepmc",
                "doi": r.get("doi"),
                "pmid": r.get("pmid"),
                "pmcid": r.get("pmcid"),
                "authors": r.get("authors"),
                "journal": r.get("journal"),
                "pub_year": r.get("pub_year"),
                "license": "Open Access/CC-BY where applicable"
            }
        }
        for r in rows
    ]