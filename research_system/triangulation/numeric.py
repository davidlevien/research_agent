"""Numeric triangulation with tolerance-based agreement detection.

v8.21.0: Groups claims by key and determines consensus using numeric tolerances
to handle minor variations in reported values.
"""

from collections import defaultdict
from typing import Dict, List, Tuple
from research_system.extraction.claims import Claim, ClaimKey

# Default relative tolerances per metric
DEFAULT_TOLERANCE_PCT = {
    # Core tourism metrics
    "international_tourist_arrivals": 0.03,  # 3% tolerance
    "tourism_jobs": 0.05,  # 5% for employment
    "tourism_spend": 0.04,  # 4% for financial
    "tourism_revenue": 0.04,
    "tourism_receipts": 0.04,
    "gdp_contribution": 0.02,  # 2% for GDP
    # Price indices
    "cpi_travel": 0.01,  # 1% for indices
    "cpi_airline_fares": 0.015,
    # Operational metrics
    "hotel_occupancy": 0.02,  # 2% for percentages
    "load_factor": 0.02,
    "airline_capacity": 0.03,
    "passenger_volume": 0.03
}

def _agree(a: float, b: float, tol: float) -> bool:
    """
    Check if two values agree within tolerance.
    
    Args:
        a: First value
        b: Second value
        tol: Relative tolerance (e.g., 0.03 for 3%)
        
    Returns:
        True if values agree within tolerance
    """
    if a == 0 and b == 0:
        return True
    
    # Use larger value as base for relative comparison
    base = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / base <= tol

def triangulate(claims: List[Claim]) -> Dict[ClaimKey, Dict]:
    """
    Triangulate claims by grouping and finding consensus.
    
    Args:
        claims: List of structured claims
        
    Returns:
        Dict mapping claim keys to consensus information
    """
    if not claims:
        return {}
    
    # Group claims by key
    buckets: Dict[ClaimKey, List[Claim]] = defaultdict(list)
    for c in claims:
        buckets[c.key].append(c)
    
    result = {}
    
    for key, items in buckets.items():
        # Get tolerance for this metric
        tol = DEFAULT_TOLERANCE_PCT.get(key.metric, 0.03)
        
        # Sort values to find median
        sorted_vals = sorted([c.value for c in items])
        
        # Use median as consensus value
        mid_idx = len(sorted_vals) // 2
        if len(sorted_vals) % 2 == 0 and len(sorted_vals) > 1:
            # Even number: average of two middle values
            consensus = (sorted_vals[mid_idx - 1] + sorted_vals[mid_idx]) / 2
        else:
            # Odd number or single value
            consensus = sorted_vals[mid_idx]
        
        # Find supporters and dissenters
        supporters = []
        dissenters = []
        
        for c in items:
            if _agree(c.value, consensus, tol):
                supporters.append(c)
            else:
                dissenters.append(c)
        
        # Calculate support ratio
        support_ratio = len(supporters) / max(1, len(items))
        
        # Mark as triangulated if multiple sources agree
        triangulated = len(supporters) >= 2 and support_ratio >= 0.5
        
        result[key] = {
            "consensus": consensus,
            "support": supporters,
            "dissent": dissenters,
            "support_ratio": support_ratio,
            "triangulated": triangulated,
            "source_count": len(set(c.source_domain for c in items if c.source_domain))
        }
    
    return result

def find_contradictions(claims: List[Claim], strict_tolerance: float = 0.1) -> List[Tuple[Claim, Claim]]:
    """
    Find claims that contradict each other beyond tolerance.
    
    Args:
        claims: List of claims to check
        strict_tolerance: Maximum allowed difference (default 10%)
        
    Returns:
        List of contradicting claim pairs
    """
    contradictions = []
    
    # Group by key first
    buckets: Dict[ClaimKey, List[Claim]] = defaultdict(list)
    for c in claims:
        buckets[c.key].append(c)
    
    # Check for contradictions within each bucket
    for key, items in buckets.items():
        if len(items) < 2:
            continue
        
        # Check all pairs
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                c1, c2 = items[i], items[j]
                
                # Skip if from same source
                if c1.source_domain and c1.source_domain == c2.source_domain:
                    continue
                
                # Check for contradiction
                if not _agree(c1.value, c2.value, strict_tolerance):
                    contradictions.append((c1, c2))
    
    return contradictions