"""
Numeric and units normalization for consistent value comparisons
"""

import re
from typing import Tuple, Optional

def parse_number_with_unit(text: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Extract number and unit from text.
    Returns (value, unit) where unit can be:
    - "%" for percentages
    - "PP" for percentage points
    - "B" for billions
    - "M" for millions
    - "T" for trillions
    - "K" for thousands
    - None for plain numbers
    """
    if not text:
        return None, None
    
    t = text.lower().strip()
    
    # Percentage
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*%", t)
    if m:
        return float(m.group(1)), "%"
    
    # Percentage points
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:pp|percentage\s+points?|ppts?)\b", t)
    if m:
        return float(m.group(1)), "PP"
    
    # Trillions
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:trillion|tn|t)\b", t)
    if m:
        return float(m.group(1)), "T"
    
    # Billions
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:billion|bn|b)\b", t)
    if m:
        return float(m.group(1)), "B"
    
    # Millions
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:million|mn|m)\b", t)
    if m:
        return float(m.group(1)), "M"
    
    # Thousands
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:thousand|k)\b", t)
    if m:
        return float(m.group(1)), "K"
    
    # Plain number with comma separators
    m = re.search(r"\b(\d{1,3}(?:,\d{3})+(?:\.\d+)?)\b", t)
    if m:
        num_str = m.group(1).replace(",", "")
        return float(num_str), None
    
    # Plain number
    m = re.search(r"\b(\d+(?:\.\d+)?)\b", t)
    if m:
        return float(m.group(1)), None
    
    return None, None


def numbers_compatible(
    a: Tuple[Optional[float], Optional[str]], 
    b: Tuple[Optional[float], Optional[str]], 
    pct_tol: float = 0.10
) -> bool:
    """
    Check if two number-unit pairs are compatible within tolerance.
    
    Args:
        a: First (value, unit) tuple
        b: Second (value, unit) tuple
        pct_tol: Percentage tolerance for comparison (default 10%)
    
    Returns:
        True if numbers are compatible, False otherwise
    """
    (av, au), (bv, bu) = a, b
    
    # If either value is None, consider compatible
    if av is None or bv is None:
        return True
    
    # Normalize units to same scale
    av_normalized = av
    bv_normalized = bv
    
    # Convert to base units (everything to raw number)
    if au == "T":
        av_normalized *= 1e12
    elif au == "B":
        av_normalized *= 1e9
    elif au == "M":
        av_normalized *= 1e6
    elif au == "K":
        av_normalized *= 1e3
    
    if bu == "T":
        bv_normalized *= 1e12
    elif bu == "B":
        bv_normalized *= 1e9
    elif bu == "M":
        bv_normalized *= 1e6
    elif bu == "K":
        bv_normalized *= 1e3
    
    # Special handling for percentages vs percentage points
    if (au == "%" and bu == "PP") or (au == "PP" and bu == "%"):
        # These are fundamentally different units
        return False
    
    # For percentages, use the raw values
    if au == "%" and bu == "%":
        return abs(av - bv) / max(1.0, max(av, bv)) <= pct_tol
    
    # For regular numbers, compare normalized values
    if av_normalized == 0 and bv_normalized == 0:
        return True
    
    return abs(av_normalized - bv_normalized) / max(1.0, max(av_normalized, bv_normalized)) <= pct_tol


def format_number_with_unit(value: float, unit: Optional[str]) -> str:
    """
    Format a number-unit pair for display.
    """
    if unit == "%":
        return f"{value}%"
    elif unit == "PP":
        return f"{value}pp"
    elif unit == "T":
        return f"{value}T"
    elif unit == "B":
        return f"{value}B"
    elif unit == "M":
        return f"{value}M"
    elif unit == "K":
        return f"{value}K"
    else:
        return str(value)