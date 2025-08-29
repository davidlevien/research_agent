"""Stats-specific orchestrator pipeline for v8.13.0."""

import logging
from typing import List, Tuple, Any, Optional

from research_system.config_v2 import load_quality_config
from research_system.retrieval.filters import admit_for_stats
from research_system.evidence.canonicalize import dedup_by_canonical
from research_system.quality.domain_weights import mark_primary

logger = logging.getLogger(__name__)

def run_stats_pipeline(
    query: str,
    all_providers: List[str],
    collect_function: Any
) -> Tuple[List[Any], List[Any]]:
    """
    Run specialized pipeline for stats intent queries.
    
    Process:
    1. Try official statistics providers first
    2. If insufficient, try data fallback providers
    3. Add general providers for context only (not counted in metrics)
    
    Args:
        query: Search query
        all_providers: Full list of available providers
        collect_function: Function to collect cards from providers
        
    Returns:
        Tuple of (primary_cards, context_cards)
    """
    cfg = load_quality_config()
    stats_config = cfg.intents.get("stats", {})
    
    logger.info("Running stats-specific pipeline")
    
    # Phase 1: Try official statistics providers
    official_providers = stats_config.get("providers_hard_prefer", [])
    logger.info(f"Phase 1: Querying official providers: {official_providers}")
    
    cards = []
    if official_providers:
        try:
            cards = collect_function(providers=official_providers, query=query)
            logger.info(f"Collected {len(cards)} cards from official providers")
        except Exception as e:
            logger.warning(f"Official providers failed: {e}")
    
    # Filter for stats requirements
    cards = [c for c in cards if admit_for_stats(c)]
    logger.info(f"After stats filtering: {len(cards)} cards")
    
    # Phase 2: If insufficient, try data fallback
    if len(cards) < 10:
        fallback_providers = stats_config.get("data_fallback", [])
        logger.info(f"Phase 2: Insufficient evidence, trying fallback providers: {fallback_providers}")
        
        if fallback_providers:
            try:
                fallback_cards = collect_function(providers=fallback_providers, query=query)
                logger.info(f"Collected {len(fallback_cards)} cards from fallback providers")
                
                # Filter and add to main cards
                fallback_cards = [c for c in fallback_cards if admit_for_stats(c)]
                cards.extend(fallback_cards)
            except Exception as e:
                logger.warning(f"Fallback providers failed: {e}")
    
    # Mark primary sources
    for card in cards:
        mark_primary(card)
    
    # Deduplicate by canonical ID
    cards = dedup_by_canonical(cards)
    logger.info(f"After deduplication: {len(cards)} primary cards")
    
    # Phase 3: Add context-only cards from general providers
    context_cards = []
    if stats_config.get("demote_general_to_context", True):
        # Filter out providers we've already used
        used_providers = set(official_providers + stats_config.get("data_fallback", []))
        general_providers = [p for p in all_providers if p not in used_providers]
        
        if general_providers and len(cards) < 20:
            logger.info(f"Phase 3: Adding context from general providers: {general_providers[:5]}")
            
            try:
                context_cards = collect_function(providers=general_providers[:5], query=query)
                logger.info(f"Collected {len(context_cards)} context cards")
                
                # Mark as context-only (not counted in primary metrics)
                for c in context_cards:
                    if not hasattr(c, "labels"):
                        c.labels = type("Labels", (object,), {})()
                    c.labels.context_only = True
                    c.labels.is_primary = False
                
                # Still deduplicate context cards
                context_cards = dedup_by_canonical(context_cards)
            except Exception as e:
                logger.warning(f"Context providers failed: {e}")
    
    return cards, context_cards

def prioritize_stats_sources(cards: List[Any]) -> List[Any]:
    """
    Prioritize cards for stats intent.
    
    Ranking order:
    1. Official statistics (TIER1 .gov)
    2. International organizations (OECD, IMF, World Bank)
    3. Academic/peer-reviewed
    4. Think tanks with data focus
    5. Everything else
    
    Args:
        cards: List of evidence cards
        
    Returns:
        Reordered list with best sources first
    """
    # Create priority buckets
    official_stats = []
    intl_orgs = []
    academic = []
    think_tanks = []
    other = []
    
    for card in cards:
        url = getattr(card, "url", "") or ""
        domain = getattr(card, "source_domain", "").lower()
        
        # Check categories
        if any(d in domain for d in ["bls.gov", "bea.gov", "census.gov", "cbo.gov", "treasury.gov", "irs.gov"]):
            official_stats.append(card)
        elif any(d in domain for d in ["oecd.org", "imf.org", "worldbank.org", "un.org", "europa.eu"]):
            intl_orgs.append(card)
        elif getattr(card, "peer_reviewed", False) or any(d in domain for d in [".edu", "nber.org", "arxiv.org"]):
            academic.append(card)
        elif any(d in domain for d in ["brookings.edu", "urban.org", "taxfoundation.org", "cbpp.org"]):
            think_tanks.append(card)
        else:
            other.append(card)
    
    # Combine in priority order
    prioritized = []
    prioritized.extend(official_stats)
    prioritized.extend(intl_orgs)
    prioritized.extend(academic)
    prioritized.extend(think_tanks)
    prioritized.extend(other)
    
    logger.info(
        f"Prioritized {len(cards)} cards: official={len(official_stats)}, "
        f"intl={len(intl_orgs)}, academic={len(academic)}, "
        f"think_tanks={len(think_tanks)}, other={len(other)}"
    )
    
    return prioritized

def validate_stats_evidence(cards: List[Any]) -> Tuple[bool, str]:
    """
    Validate that evidence meets stats intent requirements.
    
    Args:
        cards: List of evidence cards
        
    Returns:
        Tuple of (is_valid, reason_if_invalid)
    """
    if not cards:
        return False, "No evidence cards"
    
    # Count primary sources
    primary_count = sum(1 for c in cards if getattr(getattr(c, "labels", None), "is_primary", False))
    
    if primary_count < 3:
        return False, f"Insufficient primary sources: {primary_count} < 3"
    
    # Check for numeric content
    numeric_cards = sum(1 for c in cards if has_numeric_content(c))
    
    if numeric_cards < len(cards) * 0.5:
        return False, f"Insufficient numeric content: {numeric_cards}/{len(cards)}"
    
    return True, "Valid"

def has_numeric_content(card: Any) -> bool:
    """Check if card has numeric content."""
    import re
    
    text = (
        getattr(card, "snippet", "") or
        getattr(card, "text", "") or
        getattr(card, "quote_span", "")
    )
    
    # Look for numbers
    if re.search(r'\d+(?:[.,]\d+)?%?', text):
        return True
    
    # Check metadata
    if getattr(card, "has_table_or_number", False):
        return True
    
    return False