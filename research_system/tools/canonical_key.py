"""Canonical claim key generation for consistent deduplication."""

import re


def canonical_claim_key(text: str) -> str:
    """
    Generate a canonical key for claim deduplication.
    
    Normalizes verbs, percentages, periods, and numbers to create
    consistent keys that will match semantically similar claims.
    
    Args:
        text: Raw claim text
        
    Returns:
        Normalized canonical key (max 120 chars)
    """
    if not text:
        return ""
    
    t = text.lower()
    
    # Normalize increase/growth verbs
    t = re.sub(r"\b(increase|increased|grew|growth|rise|rose|up|surge|surged|jump|jumped)\b", "inc", t)
    
    # Normalize decrease verbs
    t = re.sub(r"\b(decrease|decreased|declined|fell|down|drop|dropped|plunge|plunged)\b", "dec", t)
    
    # Normalize quarters
    t = re.sub(r"\b(first|1st)\s+quarter\b", "q1", t)
    t = re.sub(r"\b(second|2nd)\s+quarter\b", "q2", t)
    t = re.sub(r"\b(third|3rd)\s+quarter\b", "q3", t)
    t = re.sub(r"\b(fourth|4th)\s+quarter\b", "q4", t)
    
    # Normalize Q notation
    t = re.sub(r"\bq1\b", "q1", t)
    t = re.sub(r"\bq2\b", "q2", t)
    t = re.sub(r"\bq3\b", "q3", t)
    t = re.sub(r"\bq4\b", "q4", t)
    
    # Normalize years to YEAR token
    t = re.sub(r"\b20\d{2}\b", "YEAR", t)
    
    # Normalize percentages to PCT token
    t = re.sub(r"\d+(?:\.\d+)?\s*%", "PCT", t)
    
    # Normalize numbers to NUM token
    t = re.sub(r"\d+(?:\.\d+)?", "NUM", t)
    
    # Remove special characters
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    
    # Collapse whitespace
    t = " ".join(t.split())
    
    # Truncate to max length
    return t[:120]