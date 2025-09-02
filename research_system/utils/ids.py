"""Canonical ID generation utilities."""

import hashlib


def canonical_id(s: str) -> str:
    """
    Generate a canonical ID from a string.
    
    Args:
        s: Input string to hash
        
    Returns:
        16-character hex ID
    """
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]