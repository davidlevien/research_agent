"""Claim mining from text using numeric and temporal patterns.

v8.21.0: Extracts structured claims with metric/value/period/geo information
for triangulation and validation.
"""

import re
import tldextract
from typing import List, Optional
from .claims import Claim, ClaimKey

# Pattern recognizers
PCT = re.compile(r"(?P<val>-?\d+(?:\.\d+)?)\s?%")
NUMBER = re.compile(r"(?P<val>-?\d{1,3}(?:[,\s]\d{3})*(?:\.\d+)?)")
QTR = re.compile(r"(?:Q(?P<q>[1-4])\s*(?P<y>20\d{2}))|(?P<y2>20\d{2})-Q(?P<q2>[1-4])", re.I)
YEAR = re.compile(r"\b(20\d{2})\b")

# Metric hints mapping
METRIC_HINTS = {
    "arrivals": "international_tourist_arrivals",
    "tourist arrivals": "international_tourist_arrivals", 
    "visitor arrivals": "international_tourist_arrivals",
    "tourism arrivals": "international_tourist_arrivals",
    "jobs": "tourism_jobs",
    "tourism jobs": "tourism_jobs",
    "employment": "tourism_jobs",
    "spend": "tourism_spend",
    "spending": "tourism_spend",
    "expenditure": "tourism_spend",
    "revenue": "tourism_revenue",
    "receipts": "tourism_receipts",
    "cpi": "cpi_travel",
    "consumer price": "cpi_travel",
    "airline fares": "cpi_airline_fares",
    "airfares": "cpi_airline_fares",
    "hotel": "hotel_occupancy",
    "occupancy": "hotel_occupancy",
    "gdp": "gdp_contribution",
    "contribution": "gdp_contribution",
    "capacity": "airline_capacity",
    "seats": "airline_capacity",
    "load factor": "load_factor",
    "passengers": "passenger_volume"
}

def normalize_num(s: str) -> float:
    """Convert string number to float, handling commas and spaces."""
    return float(s.replace(",", "").replace(" ", ""))

def mine_claims(text: str, url: str, geo_hint: Optional[str] = None, is_primary: bool = False) -> List[Claim]:
    """
    Mine structured claims from text.
    
    Args:
        text: Text to mine claims from
        url: Source URL for provenance
        geo_hint: Geographic hint (e.g., "USA", "EU27")
        is_primary: Whether source is primary/authoritative
        
    Returns:
        List of extracted claims
    """
    if not text:
        return []
    
    # Extract domain for source attribution
    try:
        domain = tldextract.extract(url).registered_domain
    except Exception:
        domain = None
    
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    claims: List[Claim] = []
    
    for i, ln in enumerate(lines):
        low = ln.lower()
        
        # Look for metric hints
        metric = None
        for hint_text, metric_name in METRIC_HINTS.items():
            if hint_text in low:
                metric = metric_name
                break
        
        if not metric:
            continue
        
        # Look for numeric value (percentage or number)
        pct_match = PCT.search(ln)
        num_match = NUMBER.search(ln) if not pct_match else None
        
        if not pct_match and not num_match:
            continue
        
        # Extract value and unit
        if pct_match:
            val = normalize_num(pct_match.group("val"))
            unit = "percent"
        else:
            val = normalize_num(num_match.group("val"))
            unit = "value"
        
        # Look for time period in context (current line + neighbors)
        context_start = max(0, i - 1)
        context_end = min(len(lines), i + 2)
        ctx = " ".join(lines[context_start:context_end])
        
        period = None
        
        # Try to find quarter
        qtr_match = QTR.search(ctx)
        if qtr_match:
            y = qtr_match.group("y") or qtr_match.group("y2")
            q = qtr_match.group("q") or qtr_match.group("q2")
            period = f"{y}-Q{q}"
        else:
            # Try to find year
            year_match = YEAR.search(ctx)
            if year_match:
                period = year_match.group(1)
        
        if not period:
            # Skip claims without temporal context
            continue
        
        # Determine geography
        geo = geo_hint or "WORLD"
        
        # Check for geographic indicators in context
        if any(term in low for term in ["united states", "u.s.", "usa", "america"]):
            geo = "USA"
        elif any(term in low for term in ["europe", "eu", "european union"]):
            geo = "EU27"
        elif any(term in low for term in ["china", "chinese"]):
            geo = "CHN"
        elif any(term in low for term in ["global", "world", "international"]):
            geo = "WORLD"
        
        # Create claim key
        key = ClaimKey(metric=metric, unit=unit, period=period, geo=geo)
        
        # Create claim with quote span
        quote_span = ln[:320] if len(ln) <= 320 else ln[:317] + "..."
        
        claims.append(Claim(
            key=key,
            value=val,
            method=None,
            source_url=url,
            quote_span=quote_span,
            source_domain=domain,
            is_primary=is_primary
        ))
    
    return claims