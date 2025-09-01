"""Contradiction filtering for clusters before representative selection."""

import logging
import os
from typing import List, Any, Tuple
import re
from statistics import median

logger = logging.getLogger(__name__)

# v8.18.0: Check strict mode
STRICT_MODE = os.getenv("STRICT_MODE", "0") == "1"

# v8.22.0: Configurable numeric tolerance for contradiction detection
TRI_CONTRA_TOL_PCT = float(os.getenv("TRI_CONTRA_TOL_PCT", "0.35"))  # v8.24.0: 35% default tolerance for relative disagreement

# Direction indicators for contradiction detection
INCREASE_WORDS = ("increase", "increased", "up", "rise", "grew", "growth", "higher")
DECREASE_WORDS = ("decrease", "decreased", "down", "decline", "fell", "lower")

HTML_TAG = re.compile(r"<[^>]+>")
NUMBER_PATTERN = re.compile(r'\b\d+(?:\.\d+)?(?:[%$€£¥]|\s*(?:billion|million|thousand|percent|%))?\b')

def _clean_text(s: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    s = HTML_TAG.sub("", s or "")
    s = " ".join(s.split())
    return s

def _get_best_text(card) -> str:
    """Get best available text from card with HTML cleaning."""
    # Try best_quote first if it exists
    if getattr(card, "best_quote", None):
        return _clean_text(card.best_quote)
    
    # Try quotes list if available
    if getattr(card, "quotes", None):
        for q in card.quotes:
            cleaned = _clean_text(q)
            if cleaned and len(cleaned) >= 40:
                return cleaned
    
    # Fall back to other text fields
    text = (
        getattr(card, "snippet", "") or 
        getattr(card, "supporting_text", "") or 
        getattr(card, "claim", "") or 
        getattr(card, "title", "")
    )
    return _clean_text(text)

def _extract_numbers(text: str) -> List[float]:
    """Extract numeric values from text for comparison."""
    numbers = []
    matches = NUMBER_PATTERN.findall(text)
    
    for match in matches:
        # Clean and extract numeric value
        clean = match.replace(',', '').replace('$', '').replace('€', '').replace('£', '').replace('¥', '').replace('%', '')
        
        # Handle multipliers
        multiplier = 1
        if 'billion' in match.lower():
            multiplier = 1_000_000_000
        elif 'million' in match.lower():
            multiplier = 1_000_000
        elif 'thousand' in match.lower() or 'k' in match.lower():
            multiplier = 1_000
        
        try:
            value = float(clean.split()[0]) * multiplier
            numbers.append(value)
        except (ValueError, IndexError):
            continue
    
    return numbers

def _is_numeric_contradiction(cards: List[Any], tol_pct: float = None, min_domains: int = 3) -> bool:
    """
    v8.24.0: Enhanced numeric contradiction detection with more lenient criteria.
    Only flag as contradiction when:
    - Same subject/metric being discussed
    - Same unit and period (e.g., both Q1 2024, both annual)
    - Large relative disagreement (≥35% by default)
    - Support from >= min_domains to consider contradiction meaningful
    
    Args:
        cards: List of evidence cards
        tol_pct: Tolerance percentage (default 0.35 for 35% disagreement)
        min_domains: Minimum unique domains required to consider contradiction
        
    Returns:
        True if numeric contradiction is detected
    """
    if tol_pct is None:
        # v8.24.0: Increase tolerance to 35% relative disagreement
        tol_pct = 0.35
    
    # Count unique domains
    domains = set()
    for card in cards:
        domain = getattr(card, 'source_domain', '') or getattr(card, 'domain', '')
        if domain:
            domains.add(domain)
    
    # Only evaluate contradiction if we have enough domain diversity
    if len(domains) < min_domains:
        return False
    
    # v8.24.0: Extract numbers with context (unit, period) for better comparison
    # For now, use simplified logic with higher tolerance
    all_numbers = []
    for card in cards:
        text = _get_best_text(card)
        numbers = _extract_numbers(text)
        all_numbers.extend(numbers)
    
    if len(all_numbers) < 2:
        return False
    
    # v8.24.0: Use pairwise comparison instead of median-based approach
    # Only flag contradiction if we find clear opposing pairs with large differences
    contradictions = 0
    comparisons = 0
    
    for i in range(len(all_numbers)):
        for j in range(i + 1, len(all_numbers)):
            comparisons += 1
            # Calculate relative difference
            max_val = max(all_numbers[i], all_numbers[j])
            min_val = min(all_numbers[i], all_numbers[j])
            if max_val > 0:
                rel_diff = (max_val - min_val) / max_val
                if rel_diff >= tol_pct:
                    contradictions += 1
    
    # Only treat as contradictory if a significant fraction of pairs disagree
    # v8.24.0: Require at least 10% of pairs to show contradiction (was 50%)
    if comparisons > 0:
        frac_contradictory = contradictions / comparisons
        return frac_contradictory > 0.10
    
    return False

def detect_contradictions(cards: List[Any]) -> List[Tuple[str, List[Any], List[Any]]]:
    """
    Detect directional contradictions within a cluster.
    
    Args:
        cards: List of evidence cards in a cluster
        
    Returns:
        List of (contradiction_type, positive_cards, negative_cards) tuples
    """
    if not cards:
        return []
    
    # Categorize cards by directional indicators
    increase_cards = []
    decrease_cards = []
    
    for card in cards:
        text = _get_best_text(card).lower()
        
        has_increase = any(word in text for word in INCREASE_WORDS)
        has_decrease = any(word in text for word in DECREASE_WORDS)
        
        if has_increase:
            increase_cards.append(card)
        if has_decrease:
            decrease_cards.append(card)
    
    contradictions = []
    
    # Check for directional contradictions
    if increase_cards and decrease_cards:
        contradictions.append((
            "increase vs decrease",
            increase_cards[:3],  # Limit to top 3 for clarity
            decrease_cards[:3]
        ))
    
    return contradictions

def has_contradictions(cards: List[Any]) -> bool:
    """
    Check if a cluster has contradictory evidence.
    
    Args:
        cards: List of evidence cards in a cluster
        
    Returns:
        True if contradictions are detected
    """
    return len(detect_contradictions(cards)) > 0

def filter_contradictory_clusters(clusters: List[Any], confidence_threshold: float = 0.6) -> List[Any]:
    """
    Remove clusters that contain strongly contradictory evidence.
    v8.23.0: Less aggressive filtering - preserve clusters with trusted domains.
    v8.22.0: Enhanced with numeric tolerance checking and domain diversity requirements.
    v8.16.0: Only drop clusters with confident opposing stances (2+ members each side, avg confidence >= 0.6).
    
    Args:
        clusters: List of cluster objects/dicts
        confidence_threshold: Minimum average confidence to consider contradictions strong
        
    Returns:
        Filtered list with strongly contradictory clusters removed
    """
    if not clusters:
        return []
    
    # v8.23.0: Import trusted domains from unified config
    from research_system.config.settings import PRIMARY_ORGS as TRUSTED_DOMAINS
    
    filtered_clusters = []
    removed_count = 0
    flagged_count = 0
    
    for cluster in clusters:
        # Extract cards from cluster (handle different formats)
        if isinstance(cluster, dict):
            cluster_cards = cluster.get('cards', [])
            cluster_meta = cluster.get('meta', {})
        else:
            cluster_cards = getattr(cluster, 'cards', [])
            cluster_meta = getattr(cluster, 'meta', {})
        
        if not cluster_cards:
            continue
        
        # v8.23.0: Count trusted domains in this cluster
        trusted_domain_count = 0
        for card in cluster_cards:
            domain = getattr(card, 'source_domain', '') or getattr(card, 'domain', '')
            if domain and any(trusted in domain for trusted in TRUSTED_DOMAINS):
                trusted_domain_count += 1
        
        # v8.23.0: Preserve clusters with 3+ trusted domains regardless of contradictions
        if trusted_domain_count >= 3:
            filtered_clusters.append(cluster)
            continue
        
        # v8.24.0: Check numeric contradictions with more lenient criteria
        has_numeric_contradiction = _is_numeric_contradiction(cluster_cards, min_domains=3)
        
        # Detect directional contradictions
        contradictions = detect_contradictions(cluster_cards)
        
        # v8.24.0: Allow up to 1 conflict, or up to 10% of pairs in larger clusters
        total_conflicts = len(contradictions) + (1 if has_numeric_contradiction else 0)
        
        # Calculate total possible pairs for percentage calculation
        from itertools import combinations
        total_pairs = len(list(combinations(cluster_cards, 2))) if len(cluster_cards) > 1 else 1
        
        # Allow clusters with minimal conflicts
        if total_conflicts <= 1:
            # Single conflict is acceptable
            filtered_clusters.append(cluster)
            continue
        elif total_pairs > 0 and total_conflicts / total_pairs <= 0.10:
            # Up to 10% conflict rate is acceptable for larger clusters
            filtered_clusters.append(cluster)
            continue
        
        # Check if we should drop based on contradiction strength
        should_drop = False
        
        # v8.24.0: Only consider dropping if no trusted domains and conflicts are severe
        if trusted_domain_count == 0:
            if has_numeric_contradiction:
                logger.debug(f"Cluster has numeric contradiction beyond {TRI_CONTRA_TOL_PCT*100}% tolerance")
                # Don't automatically drop - let confidence check decide
                if isinstance(cluster, dict):
                    cluster['meta'] = cluster.get('meta', {})
                    cluster['meta']['numeric_contradiction'] = True
            
            for contradiction_type, pos_cards, neg_cards in contradictions:
                # Check if we have strong opposition (2+ on each side)
                if len(pos_cards) >= 2 and len(neg_cards) >= 2:
                    # Calculate average confidence (using credibility_score as proxy)
                    pos_confidence = _calculate_avg_confidence(pos_cards)
                    neg_confidence = _calculate_avg_confidence(neg_cards)
                    
                    if pos_confidence >= confidence_threshold and neg_confidence >= confidence_threshold:
                        # Strong, confident contradiction with no trusted sources - drop this cluster
                        should_drop = True
                        if isinstance(cluster, dict):
                            cluster['meta'] = cluster.get('meta', {})
                            cluster['meta']['dropped_reason'] = 'confident_contradiction'
                            cluster['meta']['pos_confidence'] = pos_confidence
                            cluster['meta']['neg_confidence'] = neg_confidence
                        logger.debug(f"Dropping cluster with confident contradiction: {len(pos_cards)} vs {len(neg_cards)} cards, confidence {pos_confidence:.2f} vs {neg_confidence:.2f}")
                        break
        
        if should_drop:
            removed_count += 1
            continue
        else:
            # Keep cluster but flag if it has any contradictions
            if total_conflicts > 0:
                if isinstance(cluster, dict):
                    cluster['meta'] = cluster.get('meta', {})
                    cluster['meta']['needs_review'] = True
                    cluster['meta']['conflict_count'] = total_conflicts
                else:
                    if not hasattr(cluster, 'meta'):
                        cluster.meta = {}
                    cluster.meta['needs_review'] = True
                    cluster.meta['conflict_count'] = total_conflicts
                flagged_count += 1
                logger.debug(f"Keeping cluster with {total_conflicts} conflicts: {len(cluster_cards)} cards")
        
        filtered_clusters.append(cluster)
    
    if removed_count > 0:
        logger.info(f"Filtered {removed_count} strongly contradictory clusters from {len(clusters)} total")
    if flagged_count > 0:
        logger.info(f"Flagged {flagged_count} clusters with weak contradictions for review")
    
    # v8.18.0: In strict mode, avoid returning zero clusters if at least one was multi-domain
    # before contradiction checks. Keep the strongest single remaining cluster.
    if STRICT_MODE and not filtered_clusters and clusters:
        logger.info("Strict mode: preserving best multi-domain cluster to avoid empty result")
        
        # Find the best cluster based on domain diversity and size
        best_cluster = None
        best_score = -1
        
        for cluster in clusters:
            # Extract cards and calculate metrics
            if isinstance(cluster, dict):
                cluster_cards = cluster.get('cards', [])
            else:
                cluster_cards = getattr(cluster, 'cards', [])
            
            if not cluster_cards:
                continue
            
            # Count unique domains
            domains = set()
            for card in cluster_cards:
                domain = getattr(card, 'source_domain', '') or getattr(card, 'domain', '')
                if domain:
                    domains.add(domain)
            
            # Calculate score: prioritize multi-domain, then size
            domain_count = len(domains)
            size = len(cluster_cards)
            
            # Only consider multi-domain clusters
            if domain_count >= 2:
                score = (domain_count * 100) + size  # Heavily weight domain diversity
                
                if score > best_score:
                    best_score = score
                    best_cluster = cluster
        
        # If we found a multi-domain cluster, keep it
        if best_cluster:
            logger.info(f"Preserving best multi-domain cluster with score {best_score}")
            if isinstance(best_cluster, dict):
                best_cluster['meta'] = best_cluster.get('meta', {})
                best_cluster['meta']['preserved_in_strict'] = True
            return [best_cluster]
    
    return filtered_clusters

def _calculate_avg_confidence(cards: List[Any]) -> float:
    """
    Calculate average confidence/credibility score for a set of cards.
    
    Args:
        cards: List of evidence cards
        
    Returns:
        Average confidence score (0.0 to 1.0)
    """
    if not cards:
        return 0.0
    
    scores = []
    for card in cards:
        # Try to get confidence/credibility score
        score = None
        for attr in ['confidence', 'credibility_score', 'relevance_score']:
            val = getattr(card, attr, None)
            if val is not None:
                try:
                    # Try to convert to float, skip if it's a Mock or other non-numeric
                    score = float(val)
                    break
                except (TypeError, ValueError):
                    continue
        
        if score is None:
            score = 0.5  # Default medium confidence if no score available
        
        scores.append(score)
    
    return sum(scores) / len(scores) if scores else 0.5

def validate_cluster_consistency(cluster_cards: List[Any], topic: str = "") -> bool:
    """
    Validate that a cluster has consistent directional evidence.
    
    Args:
        cluster_cards: Cards in the cluster
        topic: Optional topic for context-aware validation
        
    Returns:
        True if cluster is consistent (no contradictions)
    """
    if not cluster_cards:
        return False
    
    # Check for basic contradictions
    contradictions = detect_contradictions(cluster_cards)
    if contradictions:
        logger.debug(f"Cluster validation failed: {len(contradictions)} contradictions detected")
        return False
    
    return True

def get_contradiction_summary(clusters: List[Any]) -> List[str]:
    """
    Generate a summary of contradictions found across clusters.
    
    Args:
        clusters: List of cluster objects/dicts
        
    Returns:
        List of contradiction summary strings
    """
    all_contradictions = []
    
    for cluster in clusters:
        # Extract cards from cluster
        if isinstance(cluster, dict):
            cluster_cards = cluster.get('cards', [])
        else:
            cluster_cards = getattr(cluster, 'cards', [])
        
        if not cluster_cards:
            continue
        
        contradictions = detect_contradictions(cluster_cards)
        for contradiction_type, pos_cards, neg_cards in contradictions:
            summary = f"- **{contradiction_type}:** {len(pos_cards)} positive vs {len(neg_cards)} negative sources"
            all_contradictions.append(summary)
    
    if not all_contradictions:
        return ["- No directional contradictions detected in evidence clusters"]
    
    return all_contradictions