"""Cached embedding model for triangulation.

v8.26.0: Implements cached SentenceTransformer model to prevent reloading.
"""

from functools import lru_cache
import logging
from typing import List, Optional
import numpy as np

logger = logging.getLogger(__name__)

# Global model instance - cached via lru_cache
_model_instance = None


@lru_cache(maxsize=1)
def get_model():
    """Get or initialize the cached embedding model.
    
    Returns:
        SentenceTransformer model instance
    """
    global _model_instance
    if _model_instance is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model_instance = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            logger.info("Loaded cached embedding model: all-MiniLM-L6-v2")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    return _model_instance


def encode(texts: List[str], normalize: bool = True) -> np.ndarray:
    """Encode texts using the cached model.
    
    Args:
        texts: List of text strings to encode
        normalize: Whether to normalize embeddings (default True)
        
    Returns:
        Numpy array of embeddings
    """
    if not texts:
        return np.array([])
    
    model = get_model()
    
    try:
        embeddings = model.encode(texts, normalize_embeddings=normalize)
        return embeddings
    except Exception as e:
        logger.error(f"Failed to encode texts: {e}")
        raise


def encode_single(text: str, normalize: bool = True) -> np.ndarray:
    """Encode a single text using the cached model.
    
    Args:
        text: Text string to encode
        normalize: Whether to normalize embedding (default True)
        
    Returns:
        Numpy array of embedding
    """
    return encode([text], normalize=normalize)[0]


def similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
    """Calculate cosine similarity between two embeddings.
    
    Args:
        emb1: First embedding
        emb2: Second embedding
        
    Returns:
        Cosine similarity score
    """
    # If already normalized, dot product equals cosine similarity
    return float(np.dot(emb1, emb2))


def batch_similarity(query_emb: np.ndarray, doc_embs: np.ndarray) -> np.ndarray:
    """Calculate similarity between query and multiple documents.
    
    Args:
        query_emb: Query embedding (1D)
        doc_embs: Document embeddings (2D)
        
    Returns:
        Array of similarity scores
    """
    if len(doc_embs) == 0:
        return np.array([])
    
    # Batch dot product for efficiency
    return doc_embs @ query_emb


def reset_cache():
    """Reset the model cache (mainly for testing)."""
    global _model_instance
    _model_instance = None
    get_model.cache_clear()
    logger.info("Embedding model cache reset")