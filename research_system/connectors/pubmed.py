"""
PubMed connector for medical/biomedical research
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
import datetime as dt
import logging
import json

logger = logging.getLogger(__name__)


def search_pubmed(query: str, rows: int = 5) -> List[Dict[str, Any]]:
    """
    Search PubMed for medical/biomedical literature.
    Uses NCBI E-utilities API (no key required for basic usage).
    
    Args:
        query: Search query string
        rows: Number of results to return (max 20 for basic)
        
    Returns:
        List of evidence-like dicts with title, url, date, etc.
    """
    if not query:
        return []
    
    try:
        import httpx
        
        # E-utilities base URL
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        
        # Step 1: Search for PMIDs
        search_params = {
            "db": "pubmed",
            "retmode": "json",
            "retmax": min(rows, 20),  # Limit to 20 for polite usage
            "term": query,
            "sort": "relevance",
            "usehistory": "n"
        }
        
        logger.debug(f"Searching PubMed for: {query}")
        
        search_response = httpx.get(
            f"{base_url}/esearch.fcgi",
            params=search_params,
            timeout=25,
            headers={"User-Agent": "ResearchSystem/1.0"}
        )
        
        if search_response.status_code != 200:
            logger.warning(f"PubMed search returned status {search_response.status_code}")
            return []
        
        search_data = search_response.json()
        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        
        if not id_list:
            logger.info(f"No PubMed results found for '{query}'")
            return []
        
        # Step 2: Fetch summaries for PMIDs
        summary_params = {
            "db": "pubmed",
            "retmode": "json",
            "id": ",".join(id_list)
        }
        
        summary_response = httpx.get(
            f"{base_url}/esummary.fcgi",
            params=summary_params,
            timeout=25,
            headers={"User-Agent": "ResearchSystem/1.0"}
        )
        
        if summary_response.status_code != 200:
            logger.warning(f"PubMed summary returned status {summary_response.status_code}")
            return []
        
        summary_data = summary_response.json()
        summaries = summary_data.get("result", {})
        
        results = []
        for pmid in id_list:
            if pmid not in summaries:
                continue
            
            item = summaries[pmid]
            
            # Extract title
            title = item.get("title", "")
            if not title:
                continue
            
            # Build URL
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            
            # Extract date
            date = None
            pub_date = item.get("pubdate", "")
            if pub_date:
                # Try to parse year from pubdate (format varies)
                year_str = pub_date.split()[0] if pub_date else ""
                if year_str.isdigit() and len(year_str) == 4:
                    try:
                        year = int(year_str)
                        date = dt.datetime(year, 1, 1)
                    except:
                        pass
            
            # Extract authors
            authors = []
            author_list = item.get("authors", [])
            for author in author_list[:3]:  # First 3 authors
                if isinstance(author, dict):
                    name = author.get("name", "")
                    if name:
                        authors.append(name)
            
            author_str = ", ".join(authors) if authors else None
            
            # Extract journal/source
            source = item.get("source", "")
            fulljournalname = item.get("fulljournalname", "")
            journal = fulljournalname or source
            
            # Build snippet from available fields
            snippet_parts = []
            
            if journal:
                snippet_parts.append(f"Published in: {journal}")
            
            if item.get("pubtype"):
                pub_types = item["pubtype"]
                if isinstance(pub_types, list) and pub_types:
                    snippet_parts.append(f"Type: {', '.join(pub_types[:2])}")
            
            if item.get("volume"):
                snippet_parts.append(f"Volume: {item['volume']}")
            
            if item.get("pages"):
                snippet_parts.append(f"Pages: {item['pages']}")
            
            # Add DOI if available
            doi = None
            elocationid = item.get("elocationid", "")
            if elocationid and "doi:" in elocationid.lower():
                doi = elocationid.replace("doi:", "").strip()
                snippet_parts.append(f"DOI: {doi}")
            
            snippet = " | ".join(snippet_parts) if snippet_parts else f"PubMed ID: {pmid}"
            
            # Build result
            result = {
                "title": title,
                "url": url,
                "date": date,
                "provider": "connector/pubmed",
                "snippet": snippet,
                "author": author_str,
                "publisher": journal,
                "pmid": pmid,
                "doi": doi,
                "credibility_score": 0.92,  # High credibility for peer-reviewed medical
                "relevance_score": 0.70,
                "confidence": 0.80,
                "is_primary_source": True
            }
            
            results.append(result)
        
        logger.info(f"PubMed returned {len(results)} results for '{query}'")
        return results
        
    except ImportError:
        logger.warning("httpx not available for PubMed connector")
        return []
    except Exception as e:
        logger.error(f"PubMed search failed: {e}")
        return []


def get_pubmed_article(pmid: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific PubMed article.
    
    Args:
        pmid: PubMed ID
        
    Returns:
        Detailed article metadata or None
    """
    if not pmid:
        return None
    
    try:
        import httpx
        
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        
        # Fetch full record
        params = {
            "db": "pubmed",
            "retmode": "json",
            "rettype": "full",
            "id": pmid
        }
        
        response = httpx.get(
            f"{base_url}/efetch.fcgi",
            params=params,
            timeout=15,
            headers={"User-Agent": "ResearchSystem/1.0"}
        )
        
        if response.status_code == 200:
            # Note: efetch returns XML by default, JSON support is limited
            # For full implementation, would parse XML response
            return {"pmid": pmid, "status": "success"}
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to get PubMed article {pmid}: {e}")
        return None