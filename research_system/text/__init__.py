"""
Text processing utilities module.
"""

from .similarity import (
    jaccard,
    text_jaccard,
    calculate_claim_similarity,
    word_overlap_ratio,
    token_overlap_count
)

__all__ = [
    'jaccard',
    'text_jaccard', 
    'calculate_claim_similarity',
    'word_overlap_ratio',
    'token_overlap_count'
]