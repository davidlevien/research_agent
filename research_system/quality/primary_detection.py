"""Enhanced primary source detection for authoritative evidence.

v8.24.0: Adds detection for authoritative PDFs with numeric content.
"""

import re
from urllib.parse import urlparse
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

# Import from unified config
from research_system.config.settings import PRIMARY_ORGS, SEMI_AUTHORITATIVE_ORGS

# Pattern to detect numeric content (years, percentages, large numbers)
NUMERIC_PATTERN = re.compile(
    r"\b(?:"
    r"\d{4}"  # Years
    r"|\d+(?:\.\d+)?\s?%"  # Percentages
    r"|\d{1,3}(?:,\d{3})+(?:\.\d+)?"  # Large numbers with commas
    r"|\$\d+(?:\.\d+)?(?:\s?(?:billion|million|thousand))?"  # Currency amounts
    r")\b",
    re.IGNORECASE
)


def is_primary_source(card: Any) -> bool:
    """
    Determine if an evidence card is from a primary/authoritative source.
    
    v8.24.0: Enhanced to recognize:
    - Authoritative organizations
    - PDFs from trusted sources with numeric content
    - Government and academic domains
    - Official statistics and reports
    
    Args:
        card: Evidence card object
        
    Returns:
        True if the card is from a primary source
    """
    # Check if already marked as primary
    if getattr(card, 'is_primary_source', False):
        return True
    
    # Get the source domain
    url = getattr(card, 'url', '') or ''
    if not url:
        return False
    
    try:
        parsed = urlparse(url.lower())
        hostname = parsed.hostname or ''
    except Exception:
        hostname = ''
    
    if not hostname:
        return False
    
    # Check against primary organizations
    for primary_domain in PRIMARY_ORGS:
        if primary_domain.startswith('.'):
            # Check suffix for academic domains
            if hostname.endswith(primary_domain):
                _set_primary_metadata(card, f"academic domain ({primary_domain})")
                return True
        elif primary_domain in hostname:
            _set_primary_metadata(card, f"authoritative org ({primary_domain})")
            return True
    
    # v8.24.0: Check for authoritative PDFs with numeric content
    is_pdf = url.lower().endswith('.pdf')
    
    if is_pdf:
        # Get text content from various fields
        text_content = _get_card_text(card)
        
        # Check for numeric content
        has_numeric = bool(NUMERIC_PATTERN.search(text_content))
        
        if has_numeric:
            # PDFs with numeric content from semi-authoritative sources
            
            for org in SEMI_AUTHORITATIVE_ORGS:
                if org in hostname:
                    _set_primary_metadata(card, f"authoritative PDF with metrics ({org})")
                    return True
            
            # Any .gov/.edu PDF with numbers is primary
            if hostname.endswith('.gov') or hostname.endswith('.edu'):
                _set_primary_metadata(card, "government/academic PDF with metrics")
                return True
    
    # Check for specific URL patterns indicating official data
    url_lower = url.lower()
    if any(pattern in url_lower for pattern in [
        '/statistics/', '/stats/', '/data/', '/reports/',
        '/publications/', '/research/', '/analysis/',
        '/indicators/', '/metrics/', '/dashboard/'
    ]):
        # These paths from .gov/.org sites are likely primary
        if hostname.endswith('.gov') or hostname.endswith('.org'):
            _set_primary_metadata(card, "official data/report path")
            return True
    
    return False


def _get_card_text(card: Any) -> str:
    """Extract all available text from a card for analysis."""
    text_parts = []
    
    for field in ['title', 'snippet', 'text', 'supporting_text', 'claim', 'best_quote']:
        value = getattr(card, field, None)
        if value:
            text_parts.append(str(value))
    
    # Also check quotes list if available
    quotes = getattr(card, 'quotes', None)
    if quotes and isinstance(quotes, list):
        text_parts.extend(str(q) for q in quotes if q)
    
    return ' '.join(text_parts).lower()


def _set_primary_metadata(card: Any, reason: str) -> None:
    """Set metadata on card indicating it's a primary source."""
    # Set the primary flag
    card.is_primary_source = True
    
    # Add metadata if the card supports it
    if not hasattr(card, 'meta'):
        card.meta = {}
    
    if isinstance(card.meta, dict):
        card.meta['primary_reason'] = reason
        card.meta['primary_detection'] = 'v8.24.0'
    
    logger.debug(f"Marked as primary source: {reason}")


def enhance_primary_detection(cards: list) -> int:
    """
    Apply enhanced primary detection to a list of cards.
    
    Args:
        cards: List of evidence cards
        
    Returns:
        Number of cards newly marked as primary
    """
    newly_marked = 0
    
    for card in cards:
        # Skip if already marked
        if getattr(card, 'is_primary_source', False):
            continue
        
        # Apply enhanced detection
        if is_primary_source(card):
            newly_marked += 1
    
    if newly_marked > 0:
        logger.info(f"Enhanced primary detection marked {newly_marked} additional cards as primary sources")
    
    return newly_marked