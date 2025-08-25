"""Quote extraction and rescue for evidence cards, with primary source priority."""

from __future__ import annotations
from typing import Iterable, Optional, Any, Dict
import re
import logging
from research_system.tools.domain_norm import PRIMARY_CANONICALS, canonical_domain

logger = logging.getLogger(__name__)

# Pattern for sentences containing metrics/claims
METRIC_SENTENCE = re.compile(
    r'[^.!?]*\b(?:'
    r'\d{1,3}(?:\.\d+)?%|'  # Percentages
    r'Q[1-4]\s*\d{4}|'       # Quarters
    r'H[12]\s*\d{4}|'        # Halves
    r'\b20\d{2}\b|'          # Years
    r'\bmillion\b|'          # Millions
    r'\bbillion\b|'          # Billions
    r'\btrillion\b'          # Trillions
    r')[^.!?]*[.!?]',
    re.IGNORECASE
)


def sentence_window(text: str, max_chars: int = 280) -> Optional[str]:
    """
    Extract the first sentence containing a metric/claim.
    
    Args:
        text: Source text to extract from
        max_chars: Maximum characters to return
        
    Returns:
        Extracted sentence or None
    """
    if not text:
        return None
    
    # Find first sentence with a metric
    match = METRIC_SENTENCE.search(text)
    if not match:
        return None
    
    sentence = match.group(0).strip()
    
    # Clean up whitespace
    sentence = ' '.join(sentence.split())
    
    # Truncate if needed
    if len(sentence) > max_chars:
        sentence = sentence[:max_chars-3] + "..."
    
    return sentence


def ensure_quotes_for_primaries(
    cards: Iterable[Any],
    only: Optional[Iterable[Any]] = None,
    fetch_fn: Optional[Any] = None,
    extract_text_fn: Optional[Any] = None
) -> int:
    """
    Ensure primary source cards have quote spans.
    
    Fast, primary-first quote rescue that prioritizes cards from primary domains.
    
    Args:
        cards: All evidence cards
        only: Subset of cards to process (e.g., newly added)
        fetch_fn: Function to fetch HTML content (url, timeout) -> html
        extract_text_fn: Function to extract text from HTML -> text
        
    Returns:
        Number of quotes added
    """
    # Identify targets: primary source cards without quotes
    targets = []
    for c in (only or cards):
        # Check if it's a primary source
        domain = canonical_domain(getattr(c, "source_domain", ""))
        if domain not in PRIMARY_CANONICALS:
            continue
            
        # Check if it already has a quote
        if getattr(c, "quote_span", None):
            continue
            
        targets.append(c)
    
    if not targets:
        logger.info("All primary source cards already have quotes")
        return 0
    
    logger.info(f"Quote rescue: {len(targets)} primary cards need quotes")
    quotes_added = 0
    
    for card in targets:
        # Try to extract from existing text first
        existing_texts = [
            getattr(card, "extracted_text", None),
            getattr(card, "snippet", None),
            getattr(card, "supporting_text", None),
            getattr(card, "claim", None),
        ]
        
        for text in existing_texts:
            if not text:
                continue
                
            quote = sentence_window(text)
            if quote:
                card.quote_span = quote
                quotes_added += 1
                logger.debug(f"Found quote in existing text for {card.url[:80]}")
                break
        
        # If still no quote and we have fetch functions, try fetching
        if not getattr(card, "quote_span", None) and fetch_fn and extract_text_fn:
            try:
                logger.debug(f"Fetching content for quote extraction: {card.url[:80]}")
                
                # Fetch with short timeout
                html = fetch_fn(card.url, timeout=20)
                
                # Extract text
                text = extract_text_fn(html)
                
                # Find quote
                quote = sentence_window(text)
                if quote:
                    card.quote_span = quote
                    quotes_added += 1
                    logger.info(f"Extracted quote from fetched content: {card.url[:80]}")
                    
            except Exception as e:
                logger.warning(f"Failed to fetch/extract quote from {card.url[:80]}: {e}")
                continue
    
    logger.info(f"Quote rescue complete: added {quotes_added} quotes")
    return quotes_added


def needs_quote_rescue(metrics: Dict[str, float], threshold: float = 0.70) -> bool:
    """Check if quote rescue is needed based on metrics."""
    current = metrics.get("quote_coverage", 0.0)
    return current < threshold
