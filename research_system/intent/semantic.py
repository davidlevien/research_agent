"""Semantic intent classification using SentenceTransformers."""

from typing import Dict, List, Tuple, Optional
import os
import yaml
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Lazy imports to avoid loading models until needed
_MODEL = None
_LBL_EMB = None
_EX_EMB = None
_LABELS: Dict[str, str] = {}
_EXAMPLES: Dict[str, List[str]] = {}


def _load_labels(path: str) -> None:
    """Load label definitions and examples from YAML file."""
    global _LABELS, _EXAMPLES
    try:
        with open(path, "r") as f:
            y = yaml.safe_load(f)
        _LABELS = y.get("labels", {})
        _EXAMPLES = y.get("examples", {})
        logger.info(f"Loaded {len(_LABELS)} intent labels from {path}")
    except Exception as e:
        logger.error(f"Failed to load labels from {path}: {e}")
        # Provide fallback labels if file doesn't exist
        _LABELS = {
            "encyclopedia": "General knowledge and definitions",
            "product": "Shopping and product comparisons",
            "local": "Local places and services",
            "news": "Current events and news",
            "academic": "Scholarly research and papers",
            "stats": "Statistics and datasets",
            "travel": "Travel and tourism",
            "regulatory": "Regulatory filings and compliance",
            "howto": "Instructions and tutorials",
            "medical": "Medical and health information",
            "generic": "General uncategorized questions"
        }
        _EXAMPLES = {}


def _embed_texts(texts: List[str]) -> np.ndarray:
    """Embed texts using the SentenceTransformer model."""
    if not texts:
        return np.array([])
    
    try:
        from sentence_transformers import SentenceTransformer
        
        # Import here to match existing pattern in codebase
        if not hasattr(_embed_texts, '_warned'):
            logger.debug(f"Encoding {len(texts)} texts with SentenceTransformer")
            _embed_texts._warned = True
            
        emb = _MODEL.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return emb if isinstance(emb, np.ndarray) else np.asarray(emb)
    except Exception as e:
        logger.error(f"Failed to embed texts: {e}")
        # Return random embeddings as fallback
        return np.random.randn(len(texts), 384) if texts else np.array([])


def _prep_embeddings() -> None:
    """Prepare embeddings for labels and examples."""
    global _LBL_EMB, _EX_EMB
    
    try:
        # Embed label descriptions
        label_texts = [f"{k}: {_LABELS[k]}" for k in _LABELS.keys()]
        _LBL_EMB = _embed_texts(label_texts)
        
        # Embed examples for each label
        _EX_EMB = {}
        for k, exs in _EXAMPLES.items():
            if exs:
                _EX_EMB[k] = _embed_texts(exs)
            else:
                _EX_EMB[k] = None
                
        logger.info(f"Prepared embeddings for {len(_LABELS)} labels")
    except Exception as e:
        logger.error(f"Failed to prepare embeddings: {e}")
        # Provide fallback embeddings
        _LBL_EMB = np.random.randn(len(_LABELS), 384)
        _EX_EMB = {k: None for k in _LABELS.keys()}


def init(
    model_name: str = None,
    labels_path: str = None
) -> None:
    """Initialize the semantic classifier.
    
    Args:
        model_name: SentenceTransformer model name (defaults to env var or all-MiniLM-L6-v2)
        labels_path: Path to labels YAML file (defaults to env var or intent/labels.yaml)
    """
    global _MODEL
    
    if _MODEL is not None:
        return  # Already initialized
    
    # Get configuration from environment or defaults
    if model_name is None:
        model_name = os.getenv("INTENT_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    if labels_path is None:
        labels_path = os.getenv("INTENT_LABELS_FILE", "research_system/intent/labels.yaml")
    
    try:
        # Try to import and load the model
        from sentence_transformers import SentenceTransformer
        
        logger.info(f"Initializing semantic classifier with model: {model_name}")
        _MODEL = SentenceTransformer(model_name)
        
        # Load labels and prepare embeddings
        _load_labels(labels_path)
        _prep_embeddings()
        
    except ImportError:
        logger.warning("SentenceTransformers not available, semantic classification disabled")
        _MODEL = None
    except Exception as e:
        logger.error(f"Failed to initialize semantic classifier: {e}")
        _MODEL = None


def score(query: str) -> List[Tuple[str, float]]:
    """Score query against all intent labels.
    
    Args:
        query: The query to classify
        
    Returns:
        List of (label, score) tuples sorted by score descending
    """
    if _MODEL is None or not _LABELS:
        # Return equal scores if not initialized
        labels = list(_LABELS.keys()) if _LABELS else ["generic"]
        return [(label, 0.5) for label in labels]
    
    try:
        # Embed the query
        q_emb = _embed_texts([query])
        if q_emb.shape[0] == 0:
            return [(label, 0.5) for label in _LABELS.keys()]
        
        # Calculate cosine similarity with label descriptions
        from sentence_transformers import util
        
        sim_lbl = util.cos_sim(q_emb, _LBL_EMB).cpu().numpy().ravel()
        
        # Calculate example boosts (max similarity across examples)
        boosts = []
        keys = list(_LABELS.keys())
        for k in keys:
            ex_emb = _EX_EMB.get(k)
            if ex_emb is not None and ex_emb.shape[0] > 0:
                sim_ex = util.cos_sim(q_emb, ex_emb).cpu().numpy().ravel()
                boosts.append(float(np.max(sim_ex)))
            else:
                boosts.append(0.0)
        
        boosts = np.asarray(boosts)
        
        # Weighted blend: 70% description, 30% examples
        blended = 0.7 * sim_lbl + 0.3 * boosts
        
        # Normalize to 0..1 range
        blended = (blended + 1) / 2.0
        
        # Create sorted list
        ranked = sorted(zip(keys, blended.tolist()), key=lambda x: x[1], reverse=True)
        return ranked
        
    except Exception as e:
        logger.error(f"Failed to score query: {e}")
        # Return equal scores as fallback
        return [(label, 0.5) for label in _LABELS.keys()]


def predict(
    query: str,
    min_score: float = None
) -> Tuple[str, float, List[Tuple[str, float]]]:
    """Predict the intent label for a query.
    
    Args:
        query: The query to classify
        min_score: Minimum confidence score (defaults to env var or 0.42)
        
    Returns:
        Tuple of (predicted_label, confidence, all_scores)
    """
    if min_score is None:
        min_score = float(os.getenv("INTENT_MIN_SCORE", "0.42"))
    
    # Get scored labels
    ranked = score(query)
    
    if not ranked:
        return "generic", 0.0, []
    
    # Get top prediction
    label, confidence = ranked[0]
    
    # Return generic if confidence too low
    if confidence < min_score:
        logger.debug(f"Low confidence {confidence:.3f} < {min_score}, returning generic")
        return "generic", confidence, ranked
    
    return label, confidence, ranked