"""
Temporal period normalization for consistent time references
"""

from __future__ import annotations
from typing import Optional
import re

_MONTHS = {
    m.lower(): i for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", 
         "jul", "aug", "sep", "oct", "nov", "dec"], 
        start=1
    )
}

# Full month names
_MONTHS.update({
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12
})

def normalize_period(text: str) -> Optional[str]:
    """
    Normalize various period formats to canonical forms:
    - Q1 2025, Q2 2025, etc.
    - H1 2025, H2 2025
    - FY 2025
    - 2025 (year only)
    """
    if not text:
        return None
    
    t = (text or "").strip()
    
    # Q1/Q2/Q3/Q4 patterns
    q = re.search(r"\b(q[1-4])\s*(?:of\s*)?(20\d{2})\b", t, re.I)
    if q:
        return f"{q.group(1).upper()} {q.group(2)}"
    
    # First/second/third/fourth quarter
    q2 = re.search(r"\b(1st|2nd|3rd|4th|first|second|third|fourth)\s+quarter\s+(?:of\s+)?(20\d{2})\b", t, re.I)
    if q2:
        m = {
            "1st": "Q1", "2nd": "Q2", "3rd": "Q3", "4th": "Q4",
            "first": "Q1", "second": "Q2", "third": "Q3", "fourth": "Q4"
        }[q2.group(1).lower()]
        return f"{m} {q2.group(2)}"
    
    # H1/H2 (half year)
    h = re.search(r"\b(h[12])\s*(20\d{2})\b", t, re.I)
    if h:
        return f"{h.group(1).upper()} {h.group(2)}"
    
    # First/second half
    h2 = re.search(r"\b(first|second)\s+half\s+(?:of\s+)?(20\d{2})\b", t, re.I)
    if h2:
        half = "H1" if h2.group(1).lower() == "first" else "H2"
        return f"{half} {h2.group(2)}"
    
    # Month ranges: Jan-Mar 2025, January to March 2025 → Q1 2025
    span = re.search(r"\b([A-Za-z]{3,9})\s*(?:-|to|–|through)\s*([A-Za-z]{3,9})\s*(20\d{2})\b", t)
    if span:
        m1_str, m2_str, y = span.groups()
        m1 = _MONTHS.get(m1_str[:3].lower(), 0)
        m2 = _MONTHS.get(m2_str[:3].lower(), 0)
        
        if 1 <= m1 <= 12 and 1 <= m2 <= 12:
            # Determine quarter based on end month
            q = (m2 + 2) // 3
            return f"Q{q} {y}"
    
    # FY (fiscal year)
    fy = re.search(r"\bFY\s*(20\d{2})\b", t, re.I)
    if fy:
        return f"FY {fy.group(1)}"
    
    # YTD (year to date)
    ytd = re.search(r"\bYTD\s*(20\d{2})\b", t, re.I)
    if ytd:
        return f"YTD {ytd.group(1)}"
    
    # Year only
    y = re.search(r"\b(20\d{2})\b", t)
    if y:
        return y.group(1)
    
    return None