"""
Unified similarity calculations for text comparison.
Replaces duplicate implementations in ContentProcessor and QualityAssurance.
"""

from typing import Set, Optional


def jaccard(tokens1: Set[str], tokens2: Set[str]) -> float:
    """Calculate Jaccard similarity between two token sets."""
    if not tokens1 or not tokens2:
        return 0.0
    
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    
    if not union:
        return 0.0
    
    return len(intersection) / len(union)


def text_jaccard(text1: str, text2: str, stopwords: Optional[Set[str]] = None) -> float:
    """
    Calculate Jaccard similarity between two text strings.
    
    Args:
        text1: First text to compare
        text2: Second text to compare
        stopwords: Optional set of stopwords to filter out
    
    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not text1 or not text2:
        return 0.0
    
    # Tokenize into word sets
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    # Remove stopwords if provided
    if stopwords:
        words1 = {w for w in words1 if w not in stopwords}
        words2 = {w for w in words2 if w not in stopwords}
    
    return jaccard(words1, words2)


def calculate_claim_similarity(claim1: str, claim2: str, stopwords: Optional[Set[str]] = None) -> float:
    """
    Calculate similarity between two claims.
    Wrapper for text_jaccard to maintain compatibility.
    
    Args:
        claim1: First claim text
        claim2: Second claim text
        stopwords: Optional stopwords to exclude
    
    Returns:
        Similarity score between 0.0 and 1.0
    """
    return text_jaccard(claim1, claim2, stopwords)


def word_overlap_ratio(text1: str, text2: str) -> float:
    """
    Calculate simple word overlap ratio without stopword filtering.
    Used for quick similarity checks.
    
    Args:
        text1: First text
        text2: Second text
    
    Returns:
        Overlap ratio between 0.0 and 1.0
    """
    if not text1 or not text2:
        return 0.0
    
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1 & words2
    union = words1 | words2
    
    return len(intersection) / len(union) if union else 0.0


def token_overlap_count(text1: str, text2: str) -> int:
    """
    Count the number of overlapping tokens between two texts.
    
    Args:
        text1: First text
        text2: Second text
    
    Returns:
        Number of overlapping tokens
    """
    if not text1 or not text2:
        return 0
    
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    return len(words1 & words2)