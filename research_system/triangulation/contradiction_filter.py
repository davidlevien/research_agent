"""Contradiction filtering for clusters before representative selection."""

import logging
from typing import List, Any, Tuple
import re

logger = logging.getLogger(__name__)

# Direction indicators for contradiction detection
INCREASE_WORDS = ("increase", "increased", "up", "rise", "grew", "growth", "higher")
DECREASE_WORDS = ("decrease", "decreased", "down", "decline", "fell", "lower")

HTML_TAG = re.compile(r"<[^>]+>")

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
    v8.16.0: Only drop clusters with confident opposing stances (2+ members each side, avg confidence >= 0.6).
    
    Args:
        clusters: List of cluster objects/dicts
        confidence_threshold: Minimum average confidence to consider contradictions strong
        
    Returns:
        Filtered list with strongly contradictory clusters removed
    """
    if not clusters:
        return []
    
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
        
        # Detect contradictions
        contradictions = detect_contradictions(cluster_cards)
        
        if contradictions:
            # Analyze contradiction strength
            should_drop = False
            
            for contradiction_type, pos_cards, neg_cards in contradictions:
                # Check if we have strong opposition (2+ on each side)
                if len(pos_cards) >= 2 and len(neg_cards) >= 2:
                    # Calculate average confidence (using credibility_score as proxy)
                    pos_confidence = _calculate_avg_confidence(pos_cards)
                    neg_confidence = _calculate_avg_confidence(neg_cards)
                    
                    if pos_confidence >= confidence_threshold and neg_confidence >= confidence_threshold:
                        # Strong, confident contradiction - drop this cluster
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
                # Weak contradiction - keep but flag for review
                if isinstance(cluster, dict):
                    cluster['meta'] = cluster.get('meta', {})
                    cluster['meta']['needs_review'] = True
                    cluster['meta']['weak_contradiction'] = True
                else:
                    if not hasattr(cluster, 'meta'):
                        cluster.meta = {}
                    cluster.meta['needs_review'] = True
                    cluster.meta['weak_contradiction'] = True
                flagged_count += 1
                logger.debug(f"Keeping cluster with weak contradiction for review: {len(cluster_cards)} cards")
        
        filtered_clusters.append(cluster)
    
    if removed_count > 0:
        logger.info(f"Filtered {removed_count} strongly contradictory clusters from {len(clusters)} total")
    if flagged_count > 0:
        logger.info(f"Flagged {flagged_count} clusters with weak contradictions for review")
    
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