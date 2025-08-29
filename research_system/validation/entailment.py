"""Entailment validation for claims against evidence."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Threshold for fuzzy matching (0-100 scale)
HARD_MIN = 65


def entails(premise: str, hypothesis: str) -> bool:
    """
    Check if premise entails hypothesis.
    
    This is a conservative proxy using lexical overlap.
    In production, replace with a proper NLI model like:
    - CrossEncoder from sentence-transformers
    - Hugging Face NLI models
    
    Args:
        premise: The evidence text
        hypothesis: The claim to validate
        
    Returns:
        True if premise entails hypothesis
    """
    if not premise or not hypothesis:
        return False
    
    # Try rapidfuzz for fuzzy matching
    try:
        from rapidfuzz.fuzz import partial_ratio
        score = partial_ratio(hypothesis.lower(), premise.lower())
        
        if score >= HARD_MIN:
            logger.debug(f"Entailment check passed: score={score} for '{hypothesis[:50]}...'")
            return True
        else:
            logger.debug(f"Entailment check failed: score={score} for '{hypothesis[:50]}...'")
            return False
            
    except ImportError:
        # Fallback to simple containment check
        logger.warning("rapidfuzz not available, using simple containment check")
        return simple_entails(premise, hypothesis)


def simple_entails(premise: str, hypothesis: str) -> bool:
    """
    Simple fallback entailment check using keyword overlap.
    
    Args:
        premise: The evidence text
        hypothesis: The claim to validate
        
    Returns:
        True if enough keywords from hypothesis appear in premise
    """
    premise_lower = premise.lower()
    hypothesis_lower = hypothesis.lower()
    
    # Extract key terms from hypothesis
    import re
    
    # Extract numbers
    numbers = re.findall(r'\d+(?:\.\d+)?', hypothesis)
    
    # Extract important words (exclude common words)
    stop_words = {'is', 'are', 'was', 'were', 'the', 'a', 'an', 'in', 'on', 'at', 'for', 'to', 'of'}
    words = [w for w in hypothesis_lower.split() if w not in stop_words and len(w) > 2]
    
    # Check if key elements appear in premise
    found_numbers = sum(1 for num in numbers if num in premise)
    found_words = sum(1 for word in words if word in premise_lower)
    
    # Require majority of numbers and significant portion of words
    numbers_ok = (found_numbers >= len(numbers) * 0.8) if numbers else True
    words_ok = (found_words >= len(words) * 0.5) if words else False
    
    return numbers_ok and words_ok


def validate_claim_grounding(claim: str, evidence: str, strict: bool = True) -> bool:
    """
    Validate that a claim is grounded in evidence.
    
    Args:
        claim: The claim text
        evidence: The evidence text
        strict: If True, require strong entailment; if False, allow weaker match
        
    Returns:
        True if claim is grounded in evidence
    """
    if strict:
        return entails(evidence, claim)
    else:
        # Relaxed: just check for key terms
        return simple_entails(evidence, claim)


def score_entailment(premise: str, hypothesis: str) -> float:
    """
    Score the strength of entailment (0.0 to 1.0).
    
    Args:
        premise: The evidence text
        hypothesis: The claim to validate
        
    Returns:
        Entailment score between 0 and 1
    """
    if not premise or not hypothesis:
        return 0.0
    
    try:
        from rapidfuzz.fuzz import partial_ratio, token_sort_ratio
        
        # Combine multiple similarity metrics
        partial = partial_ratio(hypothesis.lower(), premise.lower()) / 100.0
        token = token_sort_ratio(hypothesis.lower(), premise.lower()) / 100.0
        
        # Weighted average
        score = 0.7 * partial + 0.3 * token
        
        return score
        
    except ImportError:
        # Fallback scoring
        if simple_entails(premise, hypothesis):
            return 0.75  # Conservative score for simple match
        else:
            return 0.25  # Low score for no match