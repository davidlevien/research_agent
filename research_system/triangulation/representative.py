"""Credibility-weighted representative selection with topic similarity."""

import numpy as np
import logging
from typing import List, Tuple, Any, Optional
from sentence_transformers import SentenceTransformer

from research_system.quality.domain_weights import credibility_weight
from research_system.config_v2 import load_quality_config

logger = logging.getLogger(__name__)

_model: Optional[SentenceTransformer] = None

def _get_embedding_model() -> SentenceTransformer:
    """Get or initialize the embedding model."""
    global _model
    if _model is None:
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        logger.info("Loaded embedding model for representative selection")
    return _model

def pick_representative(cluster: List[Tuple[Any, str]], query_text: str) -> str:
    """
    Choose the best representative sentence from a cluster.
    
    Uses credibility-weighted medoid selection with topic similarity floor.
    
    Args:
        cluster: List of (card, sentence_str) tuples
        query_text: Original query for topic similarity
        
    Returns:
        Best representative sentence
    """
    if not cluster:
        return ""
    
    if len(cluster) == 1:
        return cluster[0][1]
    
    cfg = load_quality_config()
    
    # Extract sentences and cards
    cards = [c for (c, _) in cluster]
    sents = [s for (_, s) in cluster]
    
    # Get embeddings
    try:
        emb = _get_embedding_model()
        E = emb.encode([query_text] + sents, normalize_embeddings=True)
        qv, Sv = E[0], E[1:]
    except Exception as e:
        logger.warning(f"Embedding failed: {e}, using first sentence")
        return sents[0]
    
    # Calculate topic similarity
    topic_sim = Sv @ qv
    
    # Apply topic similarity floor
    mask = topic_sim >= cfg.topic_similarity_floor
    if not mask.any():
        # If nothing passes the floor, take the most similar
        mask = topic_sim == topic_sim.max()
        logger.debug(f"No sentences passed topic floor {cfg.topic_similarity_floor}, using max similarity")
    
    # Get credibility weights
    weights = np.array([credibility_weight(c) for c in cards])
    
    # Apply numeric density bonus (prefer sentences with numbers for stats)
    numeric_bonuses = []
    for sent in sents:
        import re
        numbers = re.findall(r'\d+(?:[.,]\d+)?%?', sent)
        # Bonus based on number count
        bonus = min(1.2, 1.0 + 0.1 * len(numbers))
        numeric_bonuses.append(bonus)
    
    weights = weights * np.array(numeric_bonuses)
    
    # Normalize weights
    weights = weights / (weights.sum() or 1.0)
    
    # Calculate pairwise distances among masked sentences
    M = np.where(mask)[0]
    if len(M) == 0:
        return sents[0]
    
    sub = Sv[M]
    
    # Pairwise distances (1 - cosine similarity)
    D = 1 - (sub @ sub.T)
    
    # Weighted medoid: minimize sum of weighted distances
    w = weights[M][:, None]
    scores = (D * w.T).sum(axis=1)
    
    # Get the index with minimum score
    best_idx = M[scores.argmin()]
    
    logger.debug(
        f"Selected representative with credibility={weights[best_idx]:.2f}, "
        f"topic_sim={topic_sim[best_idx]:.2f}"
    )
    
    return sents[best_idx]

def pick_cluster_representative_card(cluster: List[Any], query_text: str) -> Any:
    """
    Choose the best representative card from a cluster.
    
    Args:
        cluster: List of cards
        query_text: Original query
        
    Returns:
        Best representative card
    """
    if not cluster:
        return None
    
    if len(cluster) == 1:
        return cluster[0]
    
    # Create sentence pairs from cards
    pairs = []
    for card in cluster:
        # Get the most informative text from the card
        text = (
            getattr(card, "claim", "") or
            getattr(card, "snippet", "") or
            getattr(card, "quote_span", "") or
            getattr(card, "title", "")
        )[:500]  # Limit length
        
        if text:
            pairs.append((card, text))
    
    if not pairs:
        return cluster[0]
    
    # Pick the best sentence
    best_sent = pick_representative(pairs, query_text)
    
    # Find the card with that sentence
    for card, sent in pairs:
        if sent == best_sent:
            return card
    
    return cluster[0]

def rank_by_credibility_and_relevance(
    cards: List[Any], 
    query_text: str,
    max_results: Optional[int] = None
) -> List[Any]:
    """
    Rank cards by combined credibility and relevance score.
    
    Args:
        cards: List of evidence cards
        query_text: Original query
        max_results: Optional limit on results
        
    Returns:
        Ranked list of cards
    """
    if not cards:
        return []
    
    # Get text representations
    texts = []
    for card in cards:
        text = (
            getattr(card, "snippet", "") or
            getattr(card, "text", "") or
            getattr(card, "title", "")
        )[:500]
        texts.append(text)
    
    # Calculate relevance scores
    try:
        emb = _get_embedding_model()
        E = emb.encode([query_text] + texts, normalize_embeddings=True)
        qv = E[0]
        relevance_scores = E[1:] @ qv
    except Exception as e:
        logger.warning(f"Failed to compute relevance: {e}")
        relevance_scores = np.ones(len(cards))
    
    # Get credibility weights
    cred_scores = np.array([credibility_weight(c) for c in cards])
    
    # Combined score (weighted average)
    # 60% credibility, 40% relevance
    combined_scores = 0.6 * cred_scores + 0.4 * relevance_scores
    
    # Sort by combined score (descending)
    ranked_indices = np.argsort(combined_scores)[::-1]
    
    ranked_cards = [cards[i] for i in ranked_indices]
    
    if max_results:
        ranked_cards = ranked_cards[:max_results]
    
    return ranked_cards