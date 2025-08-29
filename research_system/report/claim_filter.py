"""
Claim filtering for typed, numeric, on-topic claims.
Ensures Key Findings and Key Numbers contain relevant, quantified information.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Numeric patterns
NUMERIC_PATTERN = re.compile(
    r'\b(?:\d+(?:\.\d+)?%?|\$[\d,]+(?:\.\d+)?[BMK]?|€[\d,]+(?:\.\d+)?[BMK]?|£[\d,]+(?:\.\d+)?[BMK]?|'
    r'\d+(?:\.\d+)?\s*(?:percent|pp|basis points?|percentage points?|trillion|billion|million|thousand))\b',
    re.IGNORECASE
)

# Units that indicate numeric claims
NUMERIC_UNITS = {
    '%', 'percent', 'pp', 'percentage point', 'basis point',
    'dollar', 'euro', 'pound', 'yen', 'yuan',
    'rate', 'ratio', 'index', 'score',
    'bracket', 'quintile', 'decile', 'percentile',
    'trillion', 'billion', 'million', 'thousand',
    'gdp', 'growth', 'inflation', 'unemployment',
    'tax', 'income', 'wealth', 'earnings', 'wage'
}


def is_numeric_claim(text: str) -> bool:
    """
    Check if a claim contains numeric information.
    
    Args:
        text: The claim text to check
        
    Returns:
        True if the claim contains numbers with units/context
    """
    if not text:
        return False
    
    # Must contain at least one number
    if not NUMERIC_PATTERN.search(text):
        return False
    
    # Should have context (units or relevant terms)
    text_lower = text.lower()
    return any(unit in text_lower for unit in NUMERIC_UNITS)


def is_on_topic(text: str, topic: str, threshold: float = 0.2) -> bool:
    """
    Check if a claim is relevant to the research topic.
    
    Args:
        text: The claim text
        topic: The research topic
        threshold: Minimum overlap threshold
        
    Returns:
        True if the claim is on-topic
    """
    if not text or not topic:
        return False
    
    # Simple token overlap for now (can be enhanced with embeddings)
    topic_tokens = set(re.findall(r'\b\w+\b', topic.lower()))
    text_tokens = set(re.findall(r'\b\w+\b', text.lower()))
    
    # Remove common stop words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    topic_tokens -= stop_words
    text_tokens -= stop_words
    
    if not topic_tokens:
        return True  # Can't filter if no meaningful tokens
    
    overlap = len(topic_tokens & text_tokens)
    return (overlap / len(topic_tokens)) >= threshold


def has_sufficient_citations(claim: Dict[str, Any], min_sources: int = 2) -> bool:
    """
    Check if a claim has sufficient independent citations.
    
    Args:
        claim: Claim dict with 'sources' or 'cards' field
        min_sources: Minimum number of independent sources required
        
    Returns:
        True if sufficiently cited
    """
    sources = claim.get('sources', claim.get('cards', []))
    if not sources:
        return False
    
    # Count unique domains
    domains = set()
    for source in sources:
        if hasattr(source, 'source_domain'):
            domains.add(source.source_domain)
        elif isinstance(source, dict) and 'domain' in source:
            domains.add(source['domain'])
    
    return len(domains) >= min_sources


def filter_key_findings(
    claims: List[Any],
    topic: str,
    require_numeric: bool = True,
    require_on_topic: bool = True,
    min_sources: int = 2
) -> List[Any]:
    """
    Filter claims for Key Findings section.
    
    Args:
        claims: List of claim objects or tuples
        topic: Research topic for relevance checking
        require_numeric: Whether to require numeric content
        require_on_topic: Whether to require topic relevance
        min_sources: Minimum independent sources per claim
        
    Returns:
        Filtered list of claims suitable for Key Findings
    """
    filtered = []
    
    for claim in claims:
        # Extract text based on claim format
        if isinstance(claim, tuple):
            text = claim[0] if claim else ""
            claim_obj = {'text': text, 'sources': claim[1] if len(claim) > 1 else []}
        elif isinstance(claim, dict):
            text = claim.get('text', claim.get('claim', ''))
            claim_obj = claim
        elif hasattr(claim, 'claim'):
            text = claim.claim
            claim_obj = {'text': text, 'sources': [claim]}
        else:
            text = str(claim)
            claim_obj = {'text': text}
        
        # Apply filters
        if require_numeric and not is_numeric_claim(text):
            logger.debug(f"Filtered non-numeric claim: {text[:100]}")
            continue
        
        if require_on_topic and not is_on_topic(text, topic):
            logger.debug(f"Filtered off-topic claim: {text[:100]}")
            continue
        
        if min_sources > 0 and not has_sufficient_citations(claim_obj, min_sources):
            logger.debug(f"Filtered under-cited claim: {text[:100]}")
            continue
        
        # Exclude nonsensical patterns
        if any(pattern in text.lower() for pattern in [
            'other titles in this series',
            '© 2001',
            'isbn',
            'doi:',
            'retrieved from',
            'accessed on'
        ]):
            logger.debug(f"Filtered metadata/citation text: {text[:100]}")
            continue
        
        filtered.append(claim)
    
    return filtered


def extract_key_numbers(cards: List[Any], topic: str, max_numbers: int = 10) -> List[str]:
    """
    Extract key numeric facts from evidence cards.
    
    Args:
        cards: List of evidence cards
        topic: Research topic for relevance
        max_numbers: Maximum number of key numbers to extract
        
    Returns:
        List of formatted key numbers with citations
    """
    numeric_claims = []
    
    for card in cards:
        # Get text content
        if hasattr(card, 'claim'):
            text = card.claim
        elif hasattr(card, 'snippet'):
            text = card.snippet
        elif isinstance(card, dict):
            text = card.get('claim', card.get('snippet', ''))
        else:
            continue
        
        if not text:
            continue
        
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        for sent in sentences:
            if is_numeric_claim(sent) and is_on_topic(sent, topic):
                # Count numbers in sentence for ranking
                num_count = len(NUMERIC_PATTERN.findall(sent))
                numeric_claims.append((num_count, sent.strip(), card))
    
    # Sort by number count (more numbers = likely more specific)
    numeric_claims.sort(reverse=True, key=lambda x: x[0])
    
    # Format top claims
    results = []
    seen = set()
    
    for _, sent, card in numeric_claims:
        # Deduplicate
        sent_key = sent[:100].lower()
        if sent_key in seen:
            continue
        seen.add(sent_key)
        
        results.append((sent, card))
        
        if len(results) >= max_numbers:
            break
    
    return results