"""
Cross-Encoder Reranking - Lightweight Local Reranking

Uses sentence-transformers cross-encoder for relevance reranking.
Falls back gracefully if not available.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

def rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    topk: int = 10,
    use_llm: bool = False
) -> List[Dict[str, Any]]:
    """
    Rerank candidates based on relevance to query.
    
    Args:
        query: The search query
        candidates: List of candidate documents with 'title' and 'snippet' fields
        topk: Number of top results to return
        use_llm: Whether to use LLM reranking (if available)
    
    Returns:
        Top-k reranked candidates
    """
    if not candidates:
        return []
    
    if len(candidates) <= topk:
        return candidates
    
    # Try LLM reranking first if requested
    if use_llm:
        try:
            from research_system.llm.llm_client import LLMClient
            from research_system.config import Settings
            
            settings = Settings()
            if settings.LLM_PROVIDER != "disabled":
                client = LLMClient(settings)
                
                # Prepare candidate texts
                candidate_texts = []
                for c in candidates:
                    text = f"{c.get('title', '')} {c.get('snippet', '')}"
                    candidate_texts.append(text)
                
                # Get scores from LLM
                scored = client.rerank(query, candidate_texts, topk)
                
                # Map back to original candidates
                reranked = []
                for score, text in scored:
                    # Find matching candidate
                    for c in candidates:
                        if f"{c.get('title', '')} {c.get('snippet', '')}" == text:
                            reranked.append(c)
                            break
                
                if reranked:
                    logger.debug(f"LLM reranking selected {len(reranked)} from {len(candidates)}")
                    return reranked[:topk]
                    
        except Exception as e:
            logger.debug(f"LLM reranking not available: {e}")
    
    # Try cross-encoder reranking
    try:
        from sentence_transformers import CrossEncoder
        
        # Load model (cached after first load)
        model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        
        # Prepare pairs for scoring
        pairs = []
        for c in candidates:
            text = f"{c.get('title', '')} {c.get('snippet', '')}"
            pairs.append([query, text])
        
        # Get scores
        scores = model.predict(pairs)
        
        # Sort by score
        scored_candidates = list(zip(scores, candidates))
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        # Return top-k
        reranked = [c for _, c in scored_candidates[:topk]]
        logger.debug(f"Cross-encoder reranking selected {len(reranked)} from {len(candidates)}")
        
        return reranked
        
    except ImportError:
        logger.debug("sentence-transformers not available, using score-based ranking")
        
        # Fallback: rank by existing scores if available
        if candidates and "confidence" in candidates[0]:
            candidates.sort(key=lambda c: c.get("confidence", 0), reverse=True)
        elif candidates and "relevance_score" in candidates[0]:
            candidates.sort(key=lambda c: c.get("relevance_score", 0), reverse=True)
        
        return candidates[:topk]
    
    except Exception as e:
        logger.warning(f"Cross-encoder reranking failed: {e}")
        return candidates[:topk]

def batch_rerank(
    queries: List[str],
    candidates_per_query: List[List[Dict[str, Any]]],
    topk: int = 10
) -> List[List[Dict[str, Any]]]:
    """
    Rerank multiple queries in batch for efficiency.
    
    Args:
        queries: List of search queries
        candidates_per_query: List of candidate lists, one per query
        topk: Number of top results per query
    
    Returns:
        List of reranked candidate lists
    """
    results = []
    
    for query, candidates in zip(queries, candidates_per_query):
        reranked = rerank(query, candidates, topk)
        results.append(reranked)
    
    return results

def hybrid_rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    topk: int = 10,
    original_weight: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Hybrid reranking combining original scores with reranker scores.
    
    Args:
        query: The search query
        candidates: Candidates with original scores
        topk: Number of results to return
        original_weight: Weight for original scores (0-1)
    
    Returns:
        Reranked candidates with hybrid scoring
    """
    if not candidates or len(candidates) <= topk:
        return candidates
    
    try:
        from sentence_transformers import CrossEncoder
        
        model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        
        # Get original scores (normalize to 0-1)
        original_scores = []
        for c in candidates:
            score = c.get("confidence", c.get("relevance_score", 0.5))
            original_scores.append(score)
        
        # Normalize original scores
        max_orig = max(original_scores) if original_scores else 1.0
        if max_orig > 0:
            original_scores = [s / max_orig for s in original_scores]
        
        # Get reranker scores
        pairs = []
        for c in candidates:
            text = f"{c.get('title', '')} {c.get('snippet', '')}"
            pairs.append([query, text])
        
        reranker_scores = model.predict(pairs)
        
        # Normalize reranker scores to 0-1
        min_score = min(reranker_scores)
        max_score = max(reranker_scores)
        if max_score > min_score:
            reranker_scores = [(s - min_score) / (max_score - min_score) for s in reranker_scores]
        else:
            reranker_scores = [0.5] * len(reranker_scores)
        
        # Combine scores
        hybrid_scores = []
        for orig, rerank in zip(original_scores, reranker_scores):
            hybrid = original_weight * orig + (1 - original_weight) * rerank
            hybrid_scores.append(hybrid)
        
        # Sort by hybrid score
        scored_candidates = list(zip(hybrid_scores, candidates))
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        # Add hybrid score to results
        results = []
        for score, candidate in scored_candidates[:topk]:
            candidate_copy = candidate.copy()
            candidate_copy["hybrid_score"] = score
            results.append(candidate_copy)
        
        return results
        
    except Exception as e:
        logger.debug(f"Hybrid reranking not available: {e}")
        return candidates[:topk]