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

def filter_contradictory_clusters(clusters: List[Any]) -> List[Any]:
    """
    Remove clusters that contain contradictory evidence.
    
    Args:
        clusters: List of cluster objects/dicts
        
    Returns:
        Filtered list with contradictory clusters removed
    """
    if not clusters:
        return []
    
    filtered_clusters = []
    removed_count = 0
    
    for cluster in clusters:
        # Extract cards from cluster (handle different formats)
        if isinstance(cluster, dict):
            cluster_cards = cluster.get('cards', [])
        else:
            cluster_cards = getattr(cluster, 'cards', [])
        
        if not cluster_cards:
            continue
        
        # Check for contradictions
        if has_contradictions(cluster_cards):
            logger.debug(f"Filtered out cluster with {len(cluster_cards)} cards due to contradictions")
            removed_count += 1
            continue
        
        filtered_clusters.append(cluster)
    
    if removed_count > 0:
        logger.info(f"Filtered {removed_count} contradictory clusters from {len(clusters)} total")
    
    return filtered_clusters

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