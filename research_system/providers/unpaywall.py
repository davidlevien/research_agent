"""Unpaywall provider for finding free full-text versions of papers."""

from typing import Optional, Dict, Any
from .http import http_json_with_policy as http_json
import logging

logger = logging.getLogger(__name__)

BASE = "https://api.unpaywall.org/v2/"
MAILTO = "research@example.com"  # Polite crawling

def lookup_fulltext(doi: str) -> Optional[Dict[str, Any]]:
    """Look up free full-text for a DOI."""
    if not doi:
        return None
    
    try:
        # Clean DOI (remove https://doi.org/ prefix if present)
        if doi.startswith("http"):
            doi = doi.split("doi.org/")[-1]
        
        url = BASE + doi
        data = http_json("unpaywall", "GET", url, params={"email": MAILTO})
        
        # Extract best OA location
        best_oa = data.get("best_oa_location")
        if best_oa:
            return {
                "url": best_oa.get("url"),
                "url_for_pdf": best_oa.get("url_for_pdf"),
                "host_type": best_oa.get("host_type"),
                "version": best_oa.get("version"),
                "license": best_oa.get("license"),
                "is_oa": data.get("is_oa", False)
            }
        
        return None
    except Exception as e:
        logger.debug(f"Unpaywall lookup failed for {doi}: {e}")
        return None