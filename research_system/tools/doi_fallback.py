"""DOI metadata fallback using Crossref and Unpaywall APIs."""

from __future__ import annotations
import httpx
import html
import re
import logging
from typing import Optional, Dict, Any

log = logging.getLogger(__name__)

# API endpoints
CR_BASE = "https://api.crossref.org/works/"
UPW_BASE = "https://api.unpaywall.org/v2/"

def crossref_meta(doi: str, email: str = "ci@example.org") -> Optional[Dict[str, Any]]:
    """
    Fetch metadata from Crossref API for a given DOI.
    
    Args:
        doi: The DOI identifier (without https://doi.org/ prefix)
        email: Contact email for API politeness
        
    Returns:
        Dict with title, abstract, date if successful, None otherwise
    """
    try:
        headers = {"User-Agent": f"research-agent/1.0 (+mailto:{email})"}
        r = httpx.get(CR_BASE + doi, headers=headers, timeout=20)
        
        if r.status_code != 200:
            return None
            
        j = r.json().get("message", {})
        
        # Extract title
        title = " ".join(j.get("title", [])[:1]).strip()
        
        # Extract and clean abstract
        abst = j.get("abstract") or ""
        # Remove HTML tags
        abst = re.sub(r"<[^>]+>", " ", abst)
        # Unescape HTML entities and normalize whitespace
        abst = html.unescape(re.sub(r"\s+", " ", abst)).strip()
        
        # Extract date
        date = None
        if j.get("issued", {}).get("date-parts"):
            parts = j["issued"]["date-parts"][0]
            if parts:
                yy = parts[0]
                mm = parts[1] if len(parts) > 1 else 1
                dd = parts[2] if len(parts) > 2 else 1
                date = f"{yy:04d}-{mm:02d}-{dd:02d}"
        
        # Also check for publisher
        publisher = j.get("publisher")
        
        return {
            "title": title,
            "abstract": abst[:5000],
            "date": date,
            "publisher": publisher,
            "source": "crossref"
        }
        
    except Exception as e:
        log.debug(f"Crossref lookup failed for {doi}: {e}")
        return None

def unpaywall_meta(doi: str, email: str = "ci@example.org") -> Optional[Dict[str, Any]]:
    """
    Fetch metadata from Unpaywall API for a given DOI.
    
    Args:
        doi: The DOI identifier (without https://doi.org/ prefix)
        email: Contact email (required by Unpaywall)
        
    Returns:
        Dict with title and OA URL if successful, None otherwise
    """
    try:
        params = {"email": email}
        headers = {"User-Agent": f"research-agent/1.0 (+mailto:{email})"}
        r = httpx.get(UPW_BASE + doi, params=params, headers=headers, timeout=20)
        
        if r.status_code != 200:
            return None
            
        j = r.json()
        
        title = j.get("title") or ""
        
        # Try to get OA URL
        oa_url = None
        oa_locations = j.get("oa_locations", [])
        if oa_locations:
            # Prefer repository URLs over publisher URLs
            for loc in oa_locations:
                if loc.get("host_type") == "repository":
                    oa_url = loc.get("url")
                    break
            if not oa_url and oa_locations:
                oa_url = oa_locations[0].get("url")
        
        # Extract year from publication
        year = j.get("year")
        date = f"{year}-01-01" if year else None
        
        return {
            "title": title,
            "abstract": "",  # Unpaywall doesn't provide abstracts
            "date": date,
            "oa_url": oa_url,
            "source": "unpaywall"
        }
        
    except Exception as e:
        log.debug(f"Unpaywall lookup failed for {doi}: {e}")
        return None

def doi_rescue(doi: str, email: str = "ci@example.org", fetch_pdf: bool = True) -> Optional[Dict[str, Any]]:
    """
    Try to rescue DOI metadata from Crossref first, then Unpaywall.
    If Unpaywall provides an OA URL and fetch_pdf is True, try to get full text.
    
    Args:
        doi: The DOI identifier (without https://doi.org/ prefix)
        email: Contact email for API politeness
        fetch_pdf: Whether to attempt fetching PDF from OA URL
        
    Returns:
        Combined metadata dict if successful, None otherwise
    """
    # Try Crossref first (has abstracts)
    meta = crossref_meta(doi, email=email)
    
    # Always try Unpaywall for OA URL
    upw = unpaywall_meta(doi, email=email)
    
    # Combine metadata
    combined = {}
    if meta:
        combined.update(meta)
    if upw:
        combined.update({k: v for k, v in upw.items() if v})
    
    # If we have OA URL and no abstract yet, try to fetch PDF
    if fetch_pdf and combined.get("oa_url") and not combined.get("abstract"):
        try:
            from research_system.net.pdf_fetch import download_pdf
            import pypdf
            from io import BytesIO
            
            log.info(f"Attempting to fetch PDF from Unpaywall OA URL: {combined['oa_url']}")
            
            with httpx.Client() as client:
                pdf_content = download_pdf(client, combined["oa_url"])
                
            if pdf_content:
                # Extract text from first few pages
                reader = pypdf.PdfReader(BytesIO(pdf_content))
                text_parts = []
                max_pages = min(3, len(reader.pages))  # First 3 pages
                
                for page_num in range(max_pages):
                    page_text = reader.pages[page_num].extract_text()
                    if page_text:
                        text_parts.append(page_text)
                
                full_text = "\n".join(text_parts)
                # Take first 5000 chars as abstract
                if full_text:
                    combined["abstract"] = full_text[:5000]
                    combined["pdf_fetched"] = True
                    log.info(f"Successfully extracted text from OA PDF for DOI {doi}")
                    
        except Exception as e:
            log.debug(f"Failed to fetch/extract PDF from OA URL: {e}")
    
    # Return combined metadata if we have at least title
    if combined.get("title"):
        return combined
    
    return None

def extract_doi_from_url(url: str) -> Optional[str]:
    """
    Extract DOI from a URL (handles various DOI URL formats).
    
    Args:
        url: URL that might contain a DOI
        
    Returns:
        The DOI string if found, None otherwise
    """
    # Match doi.org URLs
    m = re.search(r"doi\.org/(10\.\S+?)(?:\?|#|$)", url)
    if m:
        return m.group(1)
    
    # Match dx.doi.org URLs
    m = re.search(r"dx\.doi\.org/(10\.\S+?)(?:\?|#|$)", url)
    if m:
        return m.group(1)
    
    # Match DOI pattern in path
    m = re.search(r"/(10\.\d{4,}/[-._;()/:a-zA-Z0-9]+)", url)
    if m:
        return m.group(1)
    
    return None