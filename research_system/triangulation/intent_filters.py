"""Intent-based filtering for clustering and representative selection."""

import logging
from urllib.parse import urlparse
from typing import List, Any, Optional, Set
from research_system.config_v2 import load_quality_config

logger = logging.getLogger(__name__)

# Intents that require primary sources only for Key Findings
PRIMARY_ONLY_INTENTS = {"stats", "factcheck", "regulatory"}

# Primary/official domains for scholarly evidence
PRIMARY_OK_DOMAINS = {
    # US Government
    "treasury.gov", "irs.gov", "bls.gov", "bea.gov", "census.gov",
    "cbo.gov", "gao.gov", "federalreserve.gov",
    # International Organizations
    "oecd.org", "imf.org", "worldbank.org", "un.org", "europa.eu",
    "ecb.europa.eu", "eurostat.ec.europa.eu", "bis.org",
    # Other National Statistics
    "statcan.gc.ca", "ons.gov.uk", "destatis.de", "insee.fr",
    # Academic/Peer-reviewed (detected by .edu or specific hosts)
    "nber.org", "ssrn.com", "arxiv.org",
}

def _extract_host(domain: str) -> str:
    """Extract clean hostname from domain string."""
    if not domain:
        return ""
    
    try:
        # Handle URLs or plain domains
        if "://" in domain:
            return urlparse(domain).netloc.lower()
        else:
            return domain.lower()
    except Exception:
        return domain.lower()

def _is_primary_like(domain: str) -> bool:
    """Check if domain is considered primary/authoritative."""
    host = _extract_host(domain)
    
    # Check exact matches
    if host in PRIMARY_OK_DOMAINS:
        return True
    
    # Check .gov domains (US government)
    if host.endswith('.gov') and not any(partisan in host for partisan in [
        'democrats', 'republicans', 'campaign', 'political'
    ]):
        return True
    
    # Check .edu domains (academic institutions)
    if host.endswith('.edu'):
        return True
    
    # Check international org patterns
    intl_patterns = ['.int', 'europa.eu', 'ec.europa.eu']
    if any(pattern in host for pattern in intl_patterns):
        return True
    
    return False

def _get_domain_priority(domain: str) -> float:
    """Get priority score for domain (0.0-1.0)."""
    host = _extract_host(domain)
    
    # Load domain priors from configuration
    try:
        cfg = load_quality_config()
        # Check if domain has explicit priority in tiers
        if hasattr(cfg, 'tiers') and cfg.tiers:
            # Map domain to tier based on detection logic
            if _is_primary_like(domain):
                return 1.0  # TIER1 equivalent
            elif any(pattern in host for pattern in ['nber.org', 'ssrn.com', 'arxiv.org']):
                return 0.75  # TIER2 equivalent 
            elif any(pattern in host for pattern in ['brookings.edu', 'urban.org']):
                return 0.6   # TIER3 equivalent
            else:
                return 0.3   # TIER4 equivalent
    except Exception as e:
        logger.debug(f"Error loading domain priorities: {e}")
    
    # Fallback priority calculation
    if _is_primary_like(domain):
        return 0.9
    elif any(think_tank in host for think_tank in [
        'brookings.edu', 'urban.org', 'cbpp.org', 'taxfoundation.org'
    ]):
        return 0.6
    elif any(media in host for media in [
        'nytimes.com', 'wsj.com', 'ft.com', 'economist.com'
    ]):
        return 0.4
    else:
        return 0.25

def filter_cards_by_intent(cards: List[Any], intent: str, min_priority: float = 0.65) -> List[Any]:
    """
    Filter cards based on intent requirements.
    
    For stats/factcheck intents, only keep high-authority sources.
    For other intents, keep all sources.
    
    Args:
        cards: List of evidence cards
        intent: Research intent (stats, travel, generic, etc.)
        min_priority: Minimum priority score for inclusion
        
    Returns:
        Filtered list of cards
    """
    if intent not in PRIMARY_ONLY_INTENTS:
        # For non-primary intents, keep all cards
        return cards
    
    # For primary-only intents, filter by source quality
    filtered_cards = []
    for card in cards:
        domain = getattr(card, 'source_domain', '') or getattr(card, 'domain', '')
        
        # Check if it's a primary source
        if _is_primary_like(domain):
            filtered_cards.append(card)
            continue
        
        # Check priority score
        priority = _get_domain_priority(domain)
        if priority >= min_priority:
            filtered_cards.append(card)
    
    removed_count = len(cards) - len(filtered_cards)
    if removed_count > 0:
        logger.info(f"Intent-based filtering ({intent}): removed {removed_count} non-authoritative sources")
    
    return filtered_cards

def validate_cluster_for_intent(cluster_cards: List[Any], intent: str) -> bool:
    """
    Validate that a cluster meets intent-specific requirements.
    
    Args:
        cluster_cards: Cards in the cluster
        intent: Research intent
        
    Returns:
        True if cluster is valid for this intent
    """
    if not cluster_cards:
        return False
    
    # For primary-only intents, require at least one primary source
    if intent in PRIMARY_ONLY_INTENTS:
        has_primary = any(_is_primary_like(getattr(card, 'source_domain', '')) 
                         for card in cluster_cards)
        if not has_primary:
            return False
    
    # Require at least 2 independent domains
    domains = set()
    for card in cluster_cards:
        domain = _extract_host(getattr(card, 'source_domain', '') or 
                             getattr(card, 'domain', ''))
        if domain:
            domains.add(domain)
    
    if len(domains) < 2:
        logger.debug(f"Cluster rejected: only {len(domains)} independent domain(s)")
        return False
    
    return True

def prioritize_cards_for_representative(cluster_cards: List[Any], intent: str) -> List[Any]:
    """
    Prioritize cards within a cluster for representative selection.
    
    Args:
        cluster_cards: Cards in the cluster
        intent: Research intent
        
    Returns:
        Cards sorted by priority (highest first)
    """
    def priority_score(card):
        domain = getattr(card, 'source_domain', '') or getattr(card, 'domain', '')
        
        # Base domain priority
        score = _get_domain_priority(domain)
        
        # Boost for primary sources in stats intent
        if intent in PRIMARY_ONLY_INTENTS and _is_primary_like(domain):
            score += 0.3
        
        # Boost for credibility score
        credibility = getattr(card, 'credibility_score', 0.5)
        score += 0.2 * credibility
        
        # Boost for recency (if available)
        year = getattr(card, 'year', None) or getattr(card, 'publication_year', None)
        if year:
            try:
                year_int = int(year)
                if year_int >= 2020:  # Recent sources
                    score += 0.1
            except (ValueError, TypeError):
                pass
        
        return score
    
    # Sort by priority score
    return sorted(cluster_cards, key=priority_score, reverse=True)

def get_filtered_clusters_for_intent(clusters: List[Any], intent: str) -> List[Any]:
    """
    Filter clusters based on intent requirements.
    
    Args:
        clusters: List of cluster objects/dicts
        intent: Research intent
        
    Returns:
        Filtered list of valid clusters
    """
    valid_clusters = []
    
    for cluster in clusters:
        # Extract cards from cluster (handle different formats)
        if isinstance(cluster, dict):
            cluster_cards = cluster.get('cards', [])
        else:
            cluster_cards = getattr(cluster, 'cards', [])
        
        if not cluster_cards:
            continue
        
        # Validate cluster for this intent
        if validate_cluster_for_intent(cluster_cards, intent):
            valid_clusters.append(cluster)
    
    logger.info(f"Intent filtering ({intent}): {len(valid_clusters)} valid clusters from {len(clusters)} total")
    
    return valid_clusters

def should_include_in_key_findings(card: Any, intent: str) -> bool:
    """
    Determine if a card should be included in Key Findings based on intent.
    
    Args:
        card: Evidence card
        intent: Research intent
        
    Returns:
        True if card should be included in Key Findings
    """
    domain = getattr(card, 'source_domain', '') or getattr(card, 'domain', '')
    
    # For primary-only intents, require authoritative sources
    if intent in PRIMARY_ONLY_INTENTS:
        if not _is_primary_like(domain):
            priority = _get_domain_priority(domain)
            if priority < 0.7:  # Strict threshold for Key Findings
                return False
    
    # Additional quality checks
    credibility = getattr(card, 'credibility_score', 0.5)
    if credibility < 0.6:  # Quality threshold
        return False
    
    return True