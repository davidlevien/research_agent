"""
Cross-Encoder Reranking - Lightweight Local Reranking

Uses sentence-transformers cross-encoder for relevance reranking.
Falls back gracefully if not available.
v8.18.0: Added 429 guard with graceful degradation for model download failures.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

# v8.18.0: Module-level cache for cross-encoder model
_CE_MODEL = None
_CE_LOAD_ATTEMPTED = False
_CE_LOAD_FAILED = False

def _load_cross_encoder():
    """
    v8.18.0: Safely load cross-encoder model with 429 protection.
    Returns None if loading fails (e.g., due to rate limits).
    """
    global _CE_MODEL, _CE_LOAD_ATTEMPTED, _CE_LOAD_FAILED
    
    # If we already tried and failed, don't retry
    if _CE_LOAD_FAILED:
        return None
    
    # If already loaded, return it
    if _CE_MODEL is not None:
        return _CE_MODEL
    
    # Mark that we're attempting to load
    _CE_LOAD_ATTEMPTED = True
    
    try:
        from sentence_transformers import CrossEncoder
        
        # Try to load the model (may fail with 429 from HuggingFace)
        logger.debug("Loading cross-encoder model...")
        model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        _CE_MODEL = model
        logger.debug("Cross-encoder model loaded successfully")
        return model
        
    except ImportError:
        logger.debug("sentence-transformers not available")
        _CE_LOAD_FAILED = True
        return None
        
    except Exception as e:
        # This catches 429s from HuggingFace model hub and other errors
        error_str = str(e).lower()
        if "429" in error_str or "rate" in error_str or "too many requests" in error_str:
            logger.warning(f"Cross-encoder model download rate-limited (429). Falling back to no-op reranker.")
        else:
            logger.warning(f"Cross-encoder unavailable ({e}). Falling back to no-op reranker.")
        _CE_LOAD_FAILED = True
        return None

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
    
    # v8.21.0: Always rank, even when candidates <= topk (still want ordering)
    # if len(candidates) <= topk:
    #     return candidates
    
    # Try LLM reranking first if requested
    if use_llm:
        try:
            from research_system.llm.llm_client import LLMClient
            from research_system.config.settings import Settings
            
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
    
    # v8.16.0: Helper to safely extract text from dict or object
    def _get_text(candidate, *keys):
        """Extract text from dict or dataclass/pydantic object."""
        if isinstance(candidate, dict):
            for key in keys:
                value = candidate.get(key)
                if value:
                    return str(value)
            return ""
        else:
            # Try attribute access for objects (dataclass, Pydantic, etc.)
            for key in keys:
                value = getattr(candidate, key, None)
                if value:
                    return str(value)
            return ""
    
    # Try cross-encoder reranking
    # v8.18.0: Use safe loader with 429 protection
    model = _load_cross_encoder()
    
    if model is not None:
        try:
            # Prepare pairs for scoring
            pairs = []
            for c in candidates:
                title = _get_text(c, 'title')
                snippet = _get_text(c, 'snippet', 'text')
                text = f"{title} {snippet}".strip()
                if not text:
                    text = _get_text(c, 'supporting_text', 'claim', 'url')
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
            
        except Exception as e:
            # v8.18.0: Downgrade to debug level to avoid noise
            logger.debug(f"Cross-encoder scoring failed: {e}")
            # Fall through to fallback below
    
    # v8.21.0: Enhanced lexical fallback when cross-encoder unavailable
    logger.debug("Using enhanced lexical fallback (cross-encoder unavailable)")
    
    def _get_score(c, *keys):
        if isinstance(c, dict):
            for key in keys:
                if key in c:
                    return c.get(key, 0)
        else:
            for key in keys:
                if hasattr(c, key):
                    return getattr(c, key, 0)
        return 0
    
    # Compute lexical similarity scores
    query_tokens = set(query.lower().split())
    scored_candidates = []
    
    for c in candidates:
        # Get text content
        title = _get_text(c, 'title')
        snippet = _get_text(c, 'snippet', 'text', 'supporting_text', 'claim')
        text = f"{title} {snippet}".lower()
        
        # Calculate lexical overlap
        text_tokens = set(text.split())
        overlap = len(query_tokens.intersection(text_tokens))
        lexical_score = overlap / max(1, len(query_tokens))
        
        # Bonus for year/percent co-occurrence
        if any(term in text for term in ["2023", "2024", "2025", "%", "percent", "growth", "increase", "decrease"]):
            lexical_score += 0.05
        
        # Combine with existing scores if available
        existing_score = _get_score(c, "confidence", "relevance_score", "credibility_score")
        combined_score = 0.7 * lexical_score + 0.3 * existing_score
        
        scored_candidates.append((combined_score, c))
    
    # Sort by combined score
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    
    # Return top-k
    return [c for _, c in scored_candidates[:topk]]

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
    
    # v8.18.0: Use safe loader with 429 protection
    model = _load_cross_encoder()
    
    if model is not None:
        try:
            # v8.16.0: Helper for safe extraction
            def _get_value(c, *keys):
                if isinstance(c, dict):
                    for key in keys:
                        if key in c:
                            return c.get(key)
                else:
                    for key in keys:
                        if hasattr(c, key):
                            return getattr(c, key, None)
                return None
            
            def _get_text_safe(c, *keys):
                for key in keys:
                    val = _get_value(c, key)
                    if val:
                        return str(val)
                return ""
            
            # Get original scores (normalize to 0-1)
            original_scores = []
            for c in candidates:
                score = _get_value(c, "confidence", "relevance_score", "credibility_score") or 0.5
                original_scores.append(float(score))
            
            # Normalize original scores
            max_orig = max(original_scores) if original_scores else 1.0
            if max_orig > 0:
                original_scores = [s / max_orig for s in original_scores]
            
            # Get reranker scores
            pairs = []
            for c in candidates:
                title = _get_text_safe(c, 'title')
                snippet = _get_text_safe(c, 'snippet', 'text', 'supporting_text')
                text = f"{title} {snippet}".strip()
                if not text:
                    text = _get_text_safe(c, 'claim', 'url')
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
            logger.debug(f"Hybrid reranking failed: {e}")
            # Fall through to fallback below
    
    # v8.18.0: Fallback when cross-encoder is unavailable
    logger.debug("Hybrid reranking unavailable, returning top candidates")
    return candidates[:topk]