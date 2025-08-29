"""Canonicalization and mirror deduplication for evidence cards."""

import re
import logging
from urllib.parse import urlparse
from typing import List, Any, Optional, Dict

logger = logging.getLogger(__name__)

# CRS Report ID patterns
CRS_ID = re.compile(r"/(R\d{5,}|RL\d{4,}|RS\d{4,})", re.I)

# Known DOI patterns
DOI_PATTERN = re.compile(r"10\.\d{4,}/[-._;()/:a-zA-Z0-9]+", re.I)

def canonical_id(card: Any) -> str:
    """
    Returns canonical work ID for dedup counters/metrics.
    
    Priority:
    1. DOI if present
    2. CRS report number if present
    3. arXiv ID if present
    4. PubMed ID if present
    5. Normalized URL (with mirror collapsing)
    
    Args:
        card: Evidence card object
        
    Returns:
        Canonical identifier string
    """
    # Check for DOI
    doi = getattr(card, "doi", None)
    if doi:
        # Normalize DOI
        doi = doi.lower().strip()
        if not doi.startswith("10."):
            # Try to extract DOI from string like "doi:10.1234/..."
            match = DOI_PATTERN.search(doi)
            if match:
                doi = match.group(0)
        return f"doi:{doi}"
    
    # Check URL for DOI
    url = getattr(card, "url", "") or ""
    doi_match = DOI_PATTERN.search(url)
    if doi_match:
        return f"doi:{doi_match.group(0).lower()}"
    
    # Check for CRS report number
    crs_match = CRS_ID.search(url)
    if crs_match:
        return f"crs:{crs_match.group(1).upper()}"
    
    # Check for arXiv ID
    if "arxiv.org" in url.lower():
        # Extract arXiv ID like 2301.12345
        arxiv_match = re.search(r"(\d{4}\.\d{4,5})", url)
        if arxiv_match:
            return f"arxiv:{arxiv_match.group(1)}"
    
    # Check for PubMed ID
    if "pubmed.ncbi.nlm.nih.gov" in url.lower():
        pmid_match = re.search(r"/(\d{7,8})", url)
        if pmid_match:
            return f"pmid:{pmid_match.group(1)}"
    
    # Fallback to normalized URL
    u = urlparse(url)
    host = u.netloc.lower()
    
    # Collapse known mirrors to canonical hosts
    mirror_mappings = {
        "sgp.fas.org": "www.congress.gov",  # CRS mirror
        "www.everycrsreport.com": "www.congress.gov",  # CRS mirror
        "papers.ssrn.com": "ssrn.com",
        "dx.doi.org": "doi.org",
        "europepmc.org": "pubmed.ncbi.nlm.nih.gov"
    }
    
    if host in mirror_mappings:
        host = mirror_mappings[host]
        logger.debug(f"Collapsed mirror {u.netloc} -> {host}")
    
    # Clean up path
    path = u.path.rstrip("/")
    if path.endswith(".pdf"):
        path = path[:-4]  # Remove .pdf extension for consistency
    
    return f"url:{host}{path}".lower()

def dedup_by_canonical(cards: List[Any]) -> List[Any]:
    """
    Deduplicate cards by canonical ID.
    
    Args:
        cards: List of evidence cards
        
    Returns:
        Deduplicated list with canonical_id attribute added
    """
    seen = set()
    out = []
    duplicates = 0
    
    for c in cards:
        cid = canonical_id(c)
        if cid in seen:
            duplicates += 1
            logger.debug(f"Dropping duplicate with canonical ID: {cid}")
            continue
        
        seen.add(cid)
        c.canonical_id = cid
        out.append(c)
    
    if duplicates > 0:
        logger.info(f"Removed {duplicates} duplicate cards via canonicalization")
    
    return out

def get_canonical_domain(card: Any) -> str:
    """
    Get the canonical domain for a card (after mirror collapsing).
    
    Args:
        card: Evidence card
        
    Returns:
        Canonical domain string
    """
    url = getattr(card, "url", "") or ""
    u = urlparse(url)
    host = u.netloc.lower()
    
    # Apply mirror mappings
    mirror_mappings = {
        "sgp.fas.org": "congress.gov",
        "www.everycrsreport.com": "congress.gov",
        "papers.ssrn.com": "ssrn.com",
        "dx.doi.org": "doi.org",
        "europepmc.org": "pubmed.ncbi.nlm.nih.gov"
    }
    
    for mirror, canonical in mirror_mappings.items():
        if mirror in host:
            return canonical
    
    # Remove www. prefix for consistency
    if host.startswith("www."):
        host = host[4:]
    
    return host

def group_by_canonical_work(cards: List[Any]) -> Dict[str, List[Any]]:
    """
    Group cards by canonical work ID.
    
    Useful for understanding which cards are about the same underlying work.
    
    Args:
        cards: List of evidence cards
        
    Returns:
        Dict mapping canonical ID to list of cards
    """
    from collections import defaultdict
    groups = defaultdict(list)
    
    for card in cards:
        cid = canonical_id(card)
        groups[cid].append(card)
    
    return dict(groups)