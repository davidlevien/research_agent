"""Retrieval filters for partisan content, jurisdiction, and stats requirements."""

import re
import logging
from urllib.parse import urlparse
from typing import Any, Optional, List

from research_system.config_v2 import load_quality_config

logger = logging.getLogger(__name__)

# Patterns for detecting numeric content
NUMBER_PATTERN = re.compile(r'\d+(?:[.,]\d+)?%?')
TABLE_INDICATORS = re.compile(r'<table|<tr>|<td>|\|.*\|.*\|', re.I)

def is_partisan(url: str) -> bool:
    """
    Check if a URL is from a known partisan source.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL is from a partisan source
    """
    if not url:
        return False
    
    cfg = load_quality_config()
    u = urlparse(url)
    full = f"{u.scheme}://{u.netloc}{u.path}".lower()
    
    # Check against partisan exclusion list
    for pattern in cfg.sources.get("partisan_exclude_default", []):
        if pattern.lower() in full:
            logger.debug(f"Filtered partisan source: {u.netloc}")
            return True
    
    # Additional partisan indicators
    partisan_keywords = [
        "campaign", "democrat", "republican", "progressive", "conservative",
        "liberal", "right-wing", "left-wing", "politics"
    ]
    
    path_lower = u.path.lower()
    for keyword in partisan_keywords:
        if keyword in path_lower:
            logger.debug(f"Detected partisan keyword '{keyword}' in URL: {url}")
            return True
    
    return False

def is_jurisdiction_mismatch(card: Any, target: str = "US") -> bool:
    """
    Check if a card is from a mismatched jurisdiction.
    
    Args:
        card: Evidence card
        target: Target jurisdiction (default "US")
        
    Returns:
        True if jurisdiction doesn't match target
    """
    # Allow international organizations
    if getattr(card, "is_international_org", False):
        return False
    
    url = getattr(card, "url", "") or ""
    host = urlparse(url).netloc.lower()
    
    # Allow domains that are explicitly international
    international_domains = [
        "oecd.org", "imf.org", "worldbank.org", "un.org", 
        "who.int", "europa.eu", "bis.org"
    ]
    if any(d in host for d in international_domains):
        return False
    
    if target == "US":
        # Check for non-US domains (both exact matches and suffixes)
        non_us_suffixes = [".co.uk", ".ca", ".au", ".nz", ".in", ".za"]
        non_us_hosts = ["gov.uk", "gov.ca", "gov.au", "govt.nz", "gov.in", "gov.za"]
        non_us_substrings = ["aviva.co", "lloyds", "barclays", "hsbc.co"]
        
        # Check suffixes
        for suffix in non_us_suffixes:
            if host.endswith(suffix):
                logger.debug(f"Filtered non-US source for US query (suffix): {host}")
                return True
        
        # Check exact host matches
        if host in non_us_hosts:
            logger.debug(f"Filtered non-US source for US query (host): {host}")
            return True
            
        # Check substrings
        for substring in non_us_substrings:
            if substring in host:
                logger.debug(f"Filtered non-US source for US query (substring): {host}")
                return True
        
        # Check content for non-US references
        content = getattr(card, "snippet", "") or getattr(card, "text", "") or ""
        if content:
            non_us_terms = ["£", "€", "NHS", "Parliament", "Prime Minister", "Brexit"]
            for term in non_us_terms:
                if term in content:
                    logger.debug(f"Filtered card with non-US term '{term}'")
                    return True
    
    return False

def has_numeric_content(card: Any) -> bool:
    """
    Check if a card has numeric content (required for stats).
    
    Args:
        card: Evidence card
        
    Returns:
        True if card contains numbers or data tables
    """
    # Check various text fields (handle Mock objects properly)
    text_fields = [
        getattr(card, "snippet", "") or "",
        getattr(card, "text", "") or "", 
        getattr(card, "quote_span", "") or "",
        getattr(card, "title", "") or ""
    ]
    
    # Convert to strings and filter out empty/Mock objects
    string_fields = []
    for field in text_fields:
        if field and isinstance(field, str):
            string_fields.append(field)
        # Skip Mock objects and other non-string types to avoid false positives
    
    combined_text = " ".join(string_fields)
    
    # Check for numbers
    if NUMBER_PATTERN.search(combined_text):
        return True
    
    # Check for tables
    if TABLE_INDICATORS.search(combined_text):
        return True
    
    # Check metadata flags (handle Mock objects properly)  
    has_table_flag = getattr(card, "has_table_or_number", False)
    if has_table_flag is True:  # Explicit True check to avoid Mock objects
        return True
    
    contains_stats_flag = getattr(card, "contains_statistics", False) 
    if contains_stats_flag is True:  # Explicit True check to avoid Mock objects
        return True
    
    return False

def admit_for_stats(card: Any) -> bool:
    """
    Check if a card should be admitted for stats intent.
    
    Requirements:
    - Must have numeric content or data tables
    - Must not be from partisan sources
    - Must match jurisdiction (if query is US-focused)
    
    Args:
        card: Evidence card
        
    Returns:
        True if card should be admitted
    """
    url = getattr(card, "url", "") or ""
    
    # Require numeric content for stats
    if not has_numeric_content(card):
        logger.debug(f"Filtered non-numeric card for stats: {url}")
        return False
    
    # Filter partisan sources
    if is_partisan(url):
        return False
    
    # Check jurisdiction (assuming US for now)
    if is_jurisdiction_mismatch(card, target="US"):
        return False
    
    # Mark card for stats processing (handle Mock objects)
    try:
        if not hasattr(card, "flags"):
            card.flags = {}
        card.flags["stats_admitted"] = True
    except (TypeError, AttributeError):
        # Skip flag setting for Mock objects or read-only cards
        pass
    
    return True

def filter_for_intent(cards: List[Any], intent: str, query: str = "") -> List[Any]:
    """
    Filter cards based on intent-specific requirements.
    
    Args:
        cards: List of evidence cards
        intent: Research intent
        query: Original query (for jurisdiction detection)
        
    Returns:
        Filtered list of cards
    """
    if intent == "stats":
        filtered = [c for c in cards if admit_for_stats(c)]
        removed = len(cards) - len(filtered)
        if removed > 0:
            logger.info(f"Filtered {removed} cards for stats intent requirements")
        return filtered
    
    # For other intents, just filter partisan content
    filtered = []
    for card in cards:
        url = getattr(card, "url", "") or ""
        if not is_partisan(url):
            filtered.append(card)
    
    removed = len(cards) - len(filtered)
    if removed > 0:
        logger.info(f"Filtered {removed} partisan cards")
    
    return filtered

def detect_jurisdiction_from_query(query: str) -> str:
    """
    Detect the target jurisdiction from the query.
    
    Args:
        query: Search query
        
    Returns:
        Jurisdiction code (e.g., "US", "UK", "EU")
    """
    query_lower = query.lower()
    
    # US indicators
    us_terms = ["irs", "federal", "united states", "u.s.", "usa", "america", "treasury", "congress"]
    if any(term in query_lower for term in us_terms):
        return "US"
    
    # UK indicators
    uk_terms = ["uk", "united kingdom", "britain", "british", "hmrc", "parliament"]
    if any(term in query_lower for term in uk_terms):
        return "UK"
    
    # EU indicators
    eu_terms = ["eu", "european union", "eurozone", "brussels"]
    if any(term in query_lower for term in eu_terms):
        return "EU"
    
    # Default to US for tax/economic queries
    if any(term in query_lower for term in ["tax", "gdp", "economy"]):
        return "US"
    
    return "GLOBAL"