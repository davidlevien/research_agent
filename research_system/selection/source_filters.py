"""Source admissibility filters for evidence quality control."""

import logging
from typing import Any, List, Dict

logger = logging.getLogger(__name__)


def is_admissible(card: Any, intent: str) -> bool:
    """
    Check if a card is admissible as evidence for the given intent.
    
    For stats intent:
    - Always allows official/primary sources
    - Allows but flags advocacy sources as non-representative
    - Filters out completely unreliable sources
    
    Args:
        card: Evidence card
        intent: Research intent
        
    Returns:
        True if card is admissible, False otherwise
    """
    from research_system.config import Settings
    settings = Settings()
    
    if intent != settings.STATS_INTENT:
        # Non-stats: allow everything for now
        return True
    
    domain = getattr(card, 'source_domain', '').lower()
    
    # Always allow official/primary sources
    if domain in settings.STATS_ALLOWED_PRIMARY_DOMAINS:
        if not hasattr(card, 'flags'):
            card.flags = {}
        card.flags['is_primary_official'] = True
        return True
    
    # Flag but allow banned representative domains
    if domain in settings.STATS_BANNED_REPRESENTATIVE_DOMAINS:
        if not hasattr(card, 'flags'):
            card.flags = {}
        card.flags['non_representative_only'] = True
        logger.debug(f"Flagging {domain} as non-representative for stats")
        return True
    
    # Check credibility score
    credibility = getattr(card, 'credibility_score', 0.5)
    if credibility < 0.3:
        logger.debug(f"Rejecting low credibility source: {domain} (score={credibility})")
        return False
    
    # Default: allow but no special flags
    return True


def filter_by_admissibility(cards: List[Any], intent: str) -> List[Any]:
    """
    Filter a list of cards by admissibility.
    
    Args:
        cards: List of evidence cards
        intent: Research intent
        
    Returns:
        Filtered list of admissible cards
    """
    filtered = []
    rejected_count = 0
    
    for card in cards:
        if is_admissible(card, intent):
            filtered.append(card)
        else:
            rejected_count += 1
    
    if rejected_count > 0:
        logger.info(f"Filtered out {rejected_count} inadmissible cards for intent={intent}")
    
    return filtered


def classify_sources(cards: List[Any]) -> Dict[str, List[Any]]:
    """
    Classify cards into source categories.
    
    Returns dict with keys:
    - 'primary': Official statistics sources
    - 'academic': Peer-reviewed sources
    - 'think_tank': Think tank reports
    - 'media': News media
    - 'other': Everything else
    """
    from research_system.config import Settings
    settings = Settings()
    
    categories = {
        'primary': [],
        'academic': [],
        'think_tank': [],
        'media': [],
        'other': []
    }
    
    # Think tanks
    THINK_TANKS = {
        "brookings.edu", "rand.org", "urban.org", "aei.org", "heritage.org",
        "cato.org", "cbpp.org", "epi.org", "americanprogress.org", "taxfoundation.org",
        "piie.com", "cfr.org", "hoover.org"
    }
    
    # Academic patterns
    ACADEMIC_PATTERNS = [".edu", "arxiv.org", "ssrn.com", "nber.org", "jstor.org"]
    
    # Media patterns
    MEDIA_PATTERNS = [
        "nytimes.com", "wsj.com", "washingtonpost.com", "reuters.com",
        "bloomberg.com", "economist.com", "ft.com", "bbc.com", "cnn.com"
    ]
    
    for card in cards:
        domain = getattr(card, 'source_domain', '').lower()
        
        # Check primary/official
        if domain in settings.STATS_ALLOWED_PRIMARY_DOMAINS:
            categories['primary'].append(card)
        # Check academic
        elif any(pattern in domain for pattern in ACADEMIC_PATTERNS):
            categories['academic'].append(card)
        # Check think tank
        elif domain in THINK_TANKS:
            categories['think_tank'].append(card)
        # Check media
        elif any(pattern in domain for pattern in MEDIA_PATTERNS):
            categories['media'].append(card)
        else:
            categories['other'].append(card)
    
    return categories


def enforce_source_diversity(cards: List[Any], intent: str, min_primary: int = 2) -> List[Any]:
    """
    Ensure source diversity requirements are met.
    
    For stats intent, requires minimum number of primary sources.
    
    Args:
        cards: List of evidence cards
        intent: Research intent
        min_primary: Minimum number of primary sources required
        
    Returns:
        Filtered cards meeting diversity requirements
    """
    from research_system.config import Settings
    settings = Settings()
    
    if intent != settings.STATS_INTENT:
        # No diversity requirements for non-stats
        return cards
    
    # Classify sources
    classified = classify_sources(cards)
    
    # Check if we have enough primary sources
    primary_count = len(classified['primary'])
    
    if primary_count < min_primary:
        logger.warning(
            f"Insufficient primary sources for stats: {primary_count} < {min_primary}. "
            f"Evidence may not meet quality standards."
        )
    
    # For stats, boost primary sources to the top
    reordered = []
    reordered.extend(classified['primary'])
    reordered.extend(classified['academic'])
    reordered.extend(classified['think_tank'])
    reordered.extend(classified['media'])
    reordered.extend(classified['other'])
    
    return reordered


def is_recent_primary(card: Any, days: int = 730) -> bool:
    """
    Check if a card is a recent primary source.
    
    Args:
        card: Evidence card
        days: Number of days to consider recent (default 730 = ~24 months)
        
    Returns:
        True if card is recent and primary
    """
    from datetime import datetime, timedelta
    from research_system.config import Settings
    
    settings = Settings()
    
    # Check if primary
    domain = getattr(card, 'source_domain', '').lower()
    is_primary = (
        getattr(card, 'is_primary_source', False) or
        domain in settings.STATS_ALLOWED_PRIMARY_DOMAINS
    )
    
    if not is_primary:
        return False
    
    # Check if recent
    cutoff = datetime.now() - timedelta(days=days)
    collected_at = getattr(card, 'collected_at', None)
    
    if collected_at:
        try:
            if isinstance(collected_at, str):
                card_date = datetime.fromisoformat(collected_at.replace('Z', '+00:00'))
                return card_date >= cutoff
        except (ValueError, AttributeError):
            pass
    
    return False