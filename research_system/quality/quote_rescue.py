"""Quote rescue with strict numeric and primary source requirements."""

import re
import logging
from typing import List, Any, Optional, Dict

# Quote rescue configuration

logger = logging.getLogger(__name__)

# Pattern for finding numbers in text
_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?%?)")

# Pattern for finding monetary values
_MONEY = re.compile(r"\$[\d,]+(?:\.\d+)?(?:\s*(?:billion|million|trillion))?", re.I)

# Pattern for statistical terms
_STATS_TERMS = re.compile(
    r"\b(rate|percent|percentage|ratio|average|mean|median|"
    r"growth|decline|increase|decrease|rose|fell|"
    r"gdp|tax|income|revenue|deficit|surplus)\b", 
    re.I
)

def has_number(text: str) -> bool:
    """Check if text contains numeric values."""
    return bool(_NUM.search(text) or _MONEY.search(text))

def numeric_density(text: str) -> float:
    """
    Calculate the density of numeric content in text.
    
    Args:
        text: Text to analyze
        
    Returns:
        Ratio of numeric tokens to total tokens
    """
    if not text:
        return 0.0
    
    tokens = text.split()
    if not tokens:
        return 0.0
    
    # Count numeric tokens
    num_count = len(_NUM.findall(text))
    money_count = len(_MONEY.findall(text))
    
    total_numeric = num_count + money_count
    return total_numeric / len(tokens)

def is_statistical_claim(text: str) -> bool:
    """
    Check if text appears to be a statistical claim.
    
    Args:
        text: Text to analyze
        
    Returns:
        True if text contains statistical language
    """
    # Must have a number
    if not has_number(text):
        return False
    
    # Should have statistical terms
    if not _STATS_TERMS.search(text):
        return False
    
    return True

def allow_quote(card: Any, quote: str) -> bool:
    """
    Determine if a quote should be rescued/included.
    
    Requirements for stats:
    - Must be from a primary source
    - Must contain numbers with sufficient density OR
    - Must be explicitly marked as claim-like with high confidence
    
    Args:
        card: Evidence card
        quote: Quote text
        
    Returns:
        True if quote should be included
    """
    # Use constant for numeric quote minimum density
    NUMERIC_QUOTE_MIN_DENSITY = 0.1
    
    # Check if card is from a primary source
    is_primary = (
        getattr(card, "is_primary_source", False) or
        getattr(getattr(card, "labels", None), "is_primary", False)
    )
    
    if not is_primary:
        logger.debug("Quote rejected: not from primary source")
        return False
    
    # Check numeric density
    density = numeric_density(quote)
    if density >= NUMERIC_QUOTE_MIN_DENSITY:
        logger.debug(f"Quote accepted: numeric density {density:.3f} >= {NUMERIC_QUOTE_MIN_DENSITY}")
        return True
    
    # Check if it's a statistical claim
    if is_statistical_claim(quote):
        logger.debug("Quote accepted: statistical claim detected")
        return True
    
    # Allow non-numeric only if explicitly marked as high-confidence claim
    if getattr(card, "claim_like_high_conf", False):
        logger.debug("Quote accepted: high-confidence claim flag")
        return True
    
    logger.debug(f"Quote rejected: density={density:.3f}, not statistical, not high-conf claim")
    return False

def rescue_quotes(cards: List[Any], max_quotes: int = 200) -> List[str]:
    """
    Rescue high-quality quotes from evidence cards.
    
    Args:
        cards: List of evidence cards
        max_quotes: Maximum number of quotes to rescue
        
    Returns:
        List of rescued quote strings
    """
    rescued = []
    
    for card in cards:
        # Try different text fields
        text_fields = [
            getattr(card, "quote_span", ""),
            getattr(card, "snippet", ""),
            getattr(card, "text", "")
        ]
        
        for text in text_fields:
            if not text:
                continue
            
            # Split into sentences
            sentences = re.split(r'[.!?]+', text)
            
            for sent in sentences:
                sent = sent.strip()
                if len(sent) < 20:  # Too short
                    continue
                
                if len(sent) > 500:  # Too long
                    continue
                
                if allow_quote(card, sent):
                    # Add card ID for traceability
                    quote_with_id = f"{sent} [card:{getattr(card, 'id', 'unknown')}]"
                    rescued.append(quote_with_id)
                    
                    if len(rescued) >= max_quotes:
                        break
            
            if len(rescued) >= max_quotes:
                break
        
        if len(rescued) >= max_quotes:
            break
    
    logger.info(f"Rescued {len(rescued)} high-quality quotes from {len(cards)} cards")
    return rescued

def extract_key_numbers(cards: List[Any]) -> List[Dict[str, Any]]:
    """
    Extract key numbers from evidence cards.
    
    Only extracts numbers that:
    - Come from primary sources
    - Have clear numeric values
    - Include context
    
    Args:
        cards: List of evidence cards
        
    Returns:
        List of extracted number dicts
    """
    numbers = []
    
    for card in cards:
        # Only process primary sources
        is_primary = (
            getattr(card, "is_primary_source", False) or
            getattr(getattr(card, "labels", None), "is_primary", False)
        )
        
        if not is_primary:
            continue
        
        # Get text to analyze
        text = (
            getattr(card, "snippet", "") or
            getattr(card, "text", "") or
            getattr(card, "quote_span", "")
        )[:1000]
        
        if not text:
            continue
        
        # Find all numbers with context
        for match in _NUM.finditer(text):
            # Get surrounding context (±30 chars)
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()
            
            # Clean up context
            context = re.sub(r'\s+', ' ', context)
            
            # Skip if no statistical terms nearby
            if not _STATS_TERMS.search(context):
                continue
            
            numbers.append({
                "value": match.group(1),
                "context": context,
                "card_id": getattr(card, "id", "unknown"),
                "source": getattr(card, "source_domain", "unknown")
            })
            
            # Limit numbers per card
            if len([n for n in numbers if n["card_id"] == getattr(card, "id", "unknown")]) >= 3:
                break
    
    logger.info(f"Extracted {len(numbers)} key numbers from primary sources")
    return numbers