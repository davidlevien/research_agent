"""Zero-shot NLI classification fallback using transformers."""

import os
import logging
from typing import List, Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)

# Lazy loading of NLI pipeline
_NLI_PIPELINE = None
_NLI_LABELS = None


def _load_nli_labels() -> List[str]:
    """Load NLI classification labels.
    
    Returns:
        List of intent labels for zero-shot classification
    """
    # Match the labels from labels.yaml
    return [
        "encyclopedia knowledge definition",
        "news current events breaking",
        "product shopping comparison",
        "local places nearby",
        "academic research papers",
        "statistics data metrics",
        "travel tourism destinations",
        "regulatory compliance filings",
        "howto instructions tutorial",
        "medical health symptoms",
        "general uncategorized"
    ]


def init(model_name: str = None) -> None:
    """Initialize the NLI classifier.
    
    Args:
        model_name: Model name for zero-shot classification
                   (defaults to env var or facebook/bart-large-mnli)
    """
    global _NLI_PIPELINE, _NLI_LABELS
    
    if _NLI_PIPELINE is not None:
        return  # Already initialized
    
    # Get model from environment or use default
    if model_name is None:
        model_name = os.getenv("INTENT_NLI_MODEL", "facebook/bart-large-mnli")
    
    try:
        # Try to import and initialize pipeline
        from transformers import pipeline
        
        logger.info(f"Initializing NLI classifier with model: {model_name}")
        _NLI_PIPELINE = pipeline(
            "zero-shot-classification",
            model=model_name,
            device=-1  # Use CPU
        )
        
        # Load labels
        _NLI_LABELS = _load_nli_labels()
        
    except ImportError:
        logger.warning("Transformers not available, NLI classification disabled")
        _NLI_PIPELINE = None
        _NLI_LABELS = None
    except Exception as e:
        logger.error(f"Failed to initialize NLI classifier: {e}")
        _NLI_PIPELINE = None
        _NLI_LABELS = None


def classify(
    query: str,
    multi_label: bool = False,
    hypothesis_template: str = None
) -> List[Tuple[str, float]]:
    """Classify query using zero-shot NLI.
    
    Args:
        query: The query to classify
        multi_label: Whether to allow multiple labels (default False)
        hypothesis_template: Custom hypothesis template (optional)
        
    Returns:
        List of (label, score) tuples sorted by score descending
    """
    if _NLI_PIPELINE is None or _NLI_LABELS is None:
        # Return equal scores if not initialized
        default_labels = [
            "encyclopedia", "news", "product", "local", "academic",
            "stats", "travel", "regulatory", "howto", "medical", "generic"
        ]
        return [(label, 0.5) for label in default_labels]
    
    try:
        # Set hypothesis template if provided
        kwargs = {"multi_label": multi_label}
        if hypothesis_template:
            kwargs["hypothesis_template"] = hypothesis_template
        else:
            # Use a template optimized for intent classification
            kwargs["hypothesis_template"] = "This query is about {}"
        
        # Run zero-shot classification
        result = _NLI_PIPELINE(
            query,
            candidate_labels=_NLI_LABELS,
            **kwargs
        )
        
        # Map NLI labels back to intent labels
        label_map = {
            "encyclopedia knowledge definition": "encyclopedia",
            "news current events breaking": "news",
            "product shopping comparison": "product",
            "local places nearby": "local",
            "academic research papers": "academic",
            "statistics data metrics": "stats",
            "travel tourism destinations": "travel",
            "regulatory compliance filings": "regulatory",
            "howto instructions tutorial": "howto",
            "medical health symptoms": "medical",
            "general uncategorized": "generic"
        }
        
        # Create ranked list
        ranked = []
        for label, score in zip(result["labels"], result["scores"]):
            intent_label = label_map.get(label, "generic")
            ranked.append((intent_label, float(score)))
        
        return ranked
        
    except Exception as e:
        logger.error(f"Failed to classify with NLI: {e}")
        # Return equal scores as fallback
        default_labels = [
            "encyclopedia", "news", "product", "local", "academic",
            "stats", "travel", "regulatory", "howto", "medical", "generic"
        ]
        return [(label, 0.5) for label in default_labels]


def predict(
    query: str,
    min_score: float = None
) -> Tuple[str, float, List[Tuple[str, float]]]:
    """Predict the intent label using NLI.
    
    Args:
        query: The query to classify
        min_score: Minimum confidence score (defaults to env var or 0.3)
        
    Returns:
        Tuple of (predicted_label, confidence, all_scores)
    """
    if min_score is None:
        min_score = float(os.getenv("INTENT_NLI_MIN_SCORE", "0.3"))
    
    # Get NLI scores
    ranked = classify(query)
    
    if not ranked:
        return "generic", 0.0, []
    
    # Get top prediction
    label, score = ranked[0]
    
    # Return generic if confidence too low
    if score < min_score:
        logger.debug(f"NLI low confidence {score:.3f} < {min_score}, returning generic")
        return "generic", score, ranked
    
    return label, score, ranked