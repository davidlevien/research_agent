"""AREX result reranking with semantic similarity filtering to reduce drift."""

from __future__ import annotations
from typing import List, Tuple, Optional
import re
import logging

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    text = (text or "").lower()
    # Remove non-alphanumeric characters
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    # Collapse whitespace
    return " ".join(text.split())


def jaccard_similarity(text1: str, text2: str) -> float:
    """
    Calculate Jaccard similarity between two texts.
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        Jaccard similarity score (0-1)
    """
    set1 = set(_normalize_text(text1).split())
    set2 = set(_normalize_text(text2).split())
    
    if not set1 or not set2:
        return 0.0
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    return intersection / union if union > 0 else 0.0


def rerank_and_filter(
    key: str,
    candidates: List[Tuple[str, str]],
    min_sim: float = 0.32
) -> List[Tuple[str, str, float]]:
    """
    Rerank and filter candidates by similarity to key.
    
    Uses SBERT if available, falls back to Jaccard similarity.
    
    Args:
        key: Target key text to match against
        candidates: List of (title_or_snippet, url) tuples
        min_sim: Minimum similarity threshold
        
    Returns:
        List of (title_or_snippet, url, similarity_score) tuples,
        sorted by similarity descending, filtered by threshold
    """
    if not candidates:
        return []
    
    try:
        # Try to use SBERT for better semantic similarity
        from sentence_transformers import SentenceTransformer, util
        
        logger.debug(f"Using SBERT to rerank {len(candidates)} candidates")
        
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        
        # Encode key and candidates
        key_embedding = model.encode([key], normalize_embeddings=True)
        candidate_texts = [text for text, _ in candidates]
        candidate_embeddings = model.encode(candidate_texts, normalize_embeddings=True)
        
        # Calculate cosine similarities
        similarities = util.cos_sim(key_embedding, candidate_embeddings).cpu().tolist()[0]
        
        # Create scored results
        scored = [
            (candidates[i][0], candidates[i][1], similarities[i])
            for i in range(len(candidates))
        ]
        
        # Filter by higher threshold for SBERT (cosine similarity)
        min_sbert_sim = 0.42  # Higher threshold for cosine similarity
        filtered = [s for s in scored if s[2] >= min_sbert_sim]
        
        # Sort by similarity descending
        return sorted(filtered, key=lambda x: x[2], reverse=True)
        
    except ImportError:
        # Fallback to Jaccard similarity
        logger.debug(f"SBERT not available, using Jaccard to rerank {len(candidates)} candidates")
        
        scored = [
            (text, url, jaccard_similarity(key, text))
            for text, url in candidates
        ]
        
        # Filter by threshold
        filtered = [s for s in scored if s[2] >= min_sim]
        
        # Sort by similarity descending
        return sorted(filtered, key=lambda x: x[2], reverse=True)
    except Exception as e:
        logger.warning(f"Error in SBERT reranking: {e}, falling back to Jaccard")
        
        # Fallback to Jaccard on any error
        scored = [
            (text, url, jaccard_similarity(key, text))
            for text, url in candidates
        ]
        
        filtered = [s for s in scored if s[2] >= min_sim]
        return sorted(filtered, key=lambda x: x[2], reverse=True)


def filter_tangential_results(
    key_entity: Optional[str],
    key_metric: Optional[str], 
    key_period: Optional[str],
    search_results: List[dict],
    max_results: int = 3
) -> List[dict]:
    """
    Filter search results to keep only those relevant to the key.
    
    Args:
        key_entity: Entity from the structured key
        key_metric: Metric from the structured key
        key_period: Period from the structured key
        search_results: List of search result dictionaries
        max_results: Maximum number of results to return
        
    Returns:
        Filtered list of search results
    """
    if not search_results:
        return []
    
    # Build key text for comparison
    key_parts = []
    if key_entity:
        key_parts.append(key_entity)
    if key_metric:
        key_parts.append(key_metric)
    if key_period:
        key_parts.append(key_period)
    
    if not key_parts:
        # No key to filter by, return top results
        return search_results[:max_results]
    
    key_text = " ".join(key_parts)
    
    # Extract text from search results for comparison
    candidates = []
    for result in search_results:
        # Combine title and snippet for better matching
        text_parts = []
        if result.get("title"):
            text_parts.append(result["title"])
        if result.get("snippet"):
            text_parts.append(result["snippet"])
        if result.get("source_title"):
            text_parts.append(result["source_title"])
        
        combined_text = " ".join(text_parts)
        url = result.get("url") or result.get("source_url", "")
        candidates.append((combined_text, url))
    
    # Rerank and filter
    ranked = rerank_and_filter(key_text, candidates)
    
    # Keep only URLs that passed the threshold
    keep_urls = {url for _, url, _ in ranked[:max_results]}
    
    # Filter original results
    filtered = [r for r in search_results if (r.get("url") or r.get("source_url", "")) in keep_urls]
    
    logger.debug(f"Filtered {len(search_results)} results to {len(filtered)} based on key: {key_text}")
    
    return filtered