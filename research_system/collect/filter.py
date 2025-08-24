"""
Domain filtering and quality control for evidence collection
"""

from typing import Set

# Banned low-quality domains
BAN = {
    "allacronyms.com", "cartoonstock.com", "giphy.com", "tenor.com",
    "wikipedia.org", "wikimedia.org", "pinterest.com", "instagram.com",
    "facebook.com", "twitter.com", "x.com", "reddit.com",
    "buzzfeed.com", "tumblr.com", "quora.com", "answers.com"
}

# High-quality primary sources
PRIMARY = {
    "unwto.org", "e-unwto.org", "iata.org", "wttc.org", 
    "oecd.org", "worldbank.org", "imf.org", "ec.europa.eu",
    "who.int", "un.org", "unesco.org", "ilo.org",
    "federalreserve.gov", "ecb.europa.eu", "bis.org",
    "nature.com", "science.org", "nejm.org", "thelancet.com",
    "ieee.org", "acm.org", "arxiv.org", "pubmed.gov"
}

def allowed_domain(domain: str) -> bool:
    """
    Check if a domain is allowed for collection.
    Returns False for banned domains.
    """
    if not domain:
        return False
    return domain.lower() not in BAN

def is_primary_source(domain: str) -> bool:
    """Check if domain is a primary source"""
    return domain and domain.lower() in PRIMARY

def domain_quality_score(domain: str) -> float:
    """
    Calculate domain quality score.
    Primary sources get 1.0, banned get 0.0, others based on TLD.
    """
    if not domain:
        return 0.3
    
    d = domain.lower()
    
    if d in BAN:
        return 0.0
    
    if d in PRIMARY:
        return 1.0
    
    # TLD-based scoring
    if d.endswith(".gov"):
        return 0.9
    elif d.endswith(".edu") or d.endswith(".ac.uk"):
        return 0.85
    elif d.endswith(".org"):
        return 0.7
    elif d.endswith(".com"):
        return 0.5
    else:
        return 0.4