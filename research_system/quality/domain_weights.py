"""Domain tier classification and scholarly weighting."""

import logging
from urllib.parse import urlparse
from typing import Any, Optional

from research_system.config.settings import settings as config_settings

logger = logging.getLogger(__name__)

# Tier 1: Official statistics and peer-reviewed journals
TIER1_HOSTS = (
    # US Government
    "treasury.gov", "irs.gov", "bea.gov", "bls.gov", "census.gov",
    "federalreserve.gov", "cbo.gov", "gao.gov",
    # International organizations
    "europa.eu", "ec.europa.eu", "eurostat.ec.europa.eu",
    "oecd.org", "imf.org", "worldbank.org", "un.org", "who.int",
    # Academic/peer-reviewed
    "doi.org", "pubmed.ncbi.nlm.nih.gov", "nature.com", "science.org",
    "pnas.org", "cell.com", "thelancet.com", "nejm.org", "bmj.com",
    "jstor.org", "sciencedirect.com", "springer.com", "wiley.com"
)

# Tier 2: Working papers, government reports
TIER2_HOSTS = (
    "nber.org", "congress.gov", "ssrn.com", "arxiv.org",
    "bis.org", "ecb.europa.eu", "bankofengland.co.uk",
    "stlouisfed.org", "newyorkfed.org", "chicagofed.org",
    "nap.edu", "rand.org/pubs"  # RAND research reports
)

# Tier 3: Think tanks and curated aggregators
TIER3_HOSTS = (
    "ourworldindata.org", "brookings.edu", "urban.org", 
    "piie.com", "cfr.org", "csis.org", "aei.org",
    "cbpp.org", "epi.org", "taxfoundation.org",
    "heritage.org", "cato.org", "hoover.org"
)

def tier_for(card: Any) -> str:
    """
    Determine the scholarly tier for a card.
    
    Args:
        card: Evidence card
        
    Returns:
        Tier string (TIER1, TIER2, TIER3, or TIER4)
    """
    url = getattr(card, "url", "") or ""
    host = urlparse(url).netloc.lower()
    
    # Check if peer-reviewed (highest priority)
    is_peer_reviewed = getattr(card, "peer_reviewed", False)
    
    # Check labels.peer_reviewed, but handle Mock objects properly
    labels = getattr(card, "labels", None)
    if labels is not None and hasattr(labels, "peer_reviewed"):
        labels_peer_reviewed = getattr(labels, "peer_reviewed", False)
        # Handle Mock objects - they should be explicitly True/False, not truthy
        if labels_peer_reviewed is True:
            is_peer_reviewed = True
    
    if is_peer_reviewed:
        return "TIER1"
    
    # Check host-based tiers
    if any(h in host for h in TIER1_HOSTS):
        return "TIER1"
    
    if any(h in host for h in TIER2_HOSTS):
        return "TIER2"
    
    if any(h in host for h in TIER3_HOSTS):
        return "TIER3"
    
    # Everything else is TIER4 (media, blogs, encyclopedias)
    return "TIER4"

def credibility_weight(card: Any) -> float:
    """
    Get the credibility weight for a card based on its tier.
    
    Args:
        card: Evidence card
        
    Returns:
        Weight between 0.0 and 1.0
    """
    # Tier weights - higher tier = higher credibility
    tier_weights = {
        "TIER1": 1.0,   # Official stats, peer-reviewed
        "TIER2": 0.8,   # Working papers, gov reports
        "TIER3": 0.6,   # Think tanks, curated aggregators
        "TIER4": 0.4    # General web sources
    }
    t = tier_for(card)
    return tier_weights.get(t, 0.20)

def mark_primary(card: Any) -> None:
    """
    Mark a card as primary source based on tier and special rules.
    
    Rules:
    - TIER1 sources are primary (except OWID without bound DOI)
    - TIER2 sources with .gov are primary
    - Everything else is secondary
    
    Args:
        card: Evidence card (modified in place)
    """
    url = getattr(card, "url", "") or ""
    host = urlparse(url).netloc.lower()
    
    # Special handling for Our World in Data
    if "ourworldindata.org" in host:
        # Only primary if it has a bound primary DOI
        bound_doi = getattr(card, "bound_primary_doi", None)
        is_primary = bool(bound_doi)
    else:
        # Check tier
        tier = tier_for(card)
        if tier == "TIER1":
            is_primary = True
        elif tier == "TIER2" and ".gov" in host:
            is_primary = True
        else:
            is_primary = False
    
    # Set the label (handle None labels from Mock objects)
    if not hasattr(card, "labels") or getattr(card, "labels", None) is None:
        card.labels = type("Labels", (object,), {})()
    
    card.labels.is_primary = is_primary
    card.is_primary_source = is_primary  # Backward compatibility
    
    if is_primary:
        logger.debug(f"Marked as primary: {host}")

def is_scholarly_source(card: Any) -> bool:
    """
    Check if a card is from a scholarly source (TIER1 or TIER2).
    
    Args:
        card: Evidence card
        
    Returns:
        True if scholarly source
    """
    tier = tier_for(card)
    return tier in ("TIER1", "TIER2")

def get_domain_trust_score(domain: str) -> float:
    """
    Get trust score for a domain based on tier.
    
    Args:
        domain: Domain name
        
    Returns:
        Trust score between 0.0 and 1.0
    """
    # Create a mock card to reuse tier logic
    class MockCard:
        def __init__(self, url):
            self.url = url
    
    mock = MockCard(f"https://{domain}/")
    return credibility_weight(mock)