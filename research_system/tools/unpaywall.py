"""Unpaywall Open Access resolver for gated DOIs."""

import httpx
import os
from typing import Optional

UA = {"User-Agent": "ResearchAgent/1.0 (mailto:research@example.com)"}
UNPAYWALL_EMAIL = os.getenv("UNPAYWALL_EMAIL", "research@example.com")


def doi_to_oa_url(doi: str) -> Optional[str]:
    """
    Find Open Access version of a DOI using Unpaywall.
    
    Args:
        doi: DOI identifier
        
    Returns:
        URL to OA PDF or landing page if available, None otherwise
    """
    try:
        url = f"https://api.unpaywall.org/v2/{doi}?email={UNPAYWALL_EMAIL}"
        r = httpx.get(url, headers=UA, timeout=20)
        
        if r.status_code != 200:
            return None
            
        data = r.json()
        
        # Get best OA location
        best = data.get("best_oa_location") or {}
        
        # Prefer PDF URL if available
        pdf_url = best.get("url_for_pdf")
        if pdf_url:
            return pdf_url
            
        # Fall back to landing page URL
        return best.get("url")
        
    except Exception:
        return None


def is_oa_available(doi: str) -> bool:
    """
    Check if an Open Access version exists for a DOI.
    
    Args:
        doi: DOI identifier
        
    Returns:
        True if OA version exists
    """
    try:
        url = f"https://api.unpaywall.org/v2/{doi}?email={UNPAYWALL_EMAIL}"
        r = httpx.get(url, headers=UA, timeout=10)
        
        if r.status_code != 200:
            return False
            
        data = r.json()
        return data.get("is_oa", False)
        
    except Exception:
        return False