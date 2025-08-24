"""
Contradiction detection for conflicting numeric claims
"""

from __future__ import annotations
from typing import List, Dict, Any
from .claim_struct import extract_struct_claim, struct_key, numbers_close

def find_numeric_conflicts(texts: List[str], tol: float = 0.10) -> List[Dict[str, Any]]:
    """
    Find numeric contradictions in a list of claim texts.
    
    Args:
        texts: List of claim texts to analyze
        tol: Tolerance for numeric comparison (default 10%)
    
    Returns:
        List of contradiction dictionaries with keys:
        - key: The structured claim key
        - indices: List of conflicting text indices
        - values: List of conflicting values
        - claims: The structured claims involved
    """
    # Extract structured claims
    scs = [extract_struct_claim(t) for t in texts]
    
    # Group by key
    by_key = {}
    for i, sc in enumerate(scs):
        k = struct_key(sc)
        if not k:
            continue
        by_key.setdefault(k, []).append((i, sc))
    
    # Find conflicts
    conflicts = []
    for k, items in by_key.items():
        # Only check items with values
        vals = [(i, sc) for i, sc in items if sc.value is not None]
        
        if len(vals) < 2:
            continue
        
        # Check all pairs for conflicts
        for a in range(len(vals)):
            for b in range(a + 1, len(vals)):
                i1, sc1 = vals[a]
                i2, sc2 = vals[b]
                
                # Check if values conflict
                if not numbers_close(sc1.value, sc2.value, tol=tol):
                    conflicts.append({
                        "key": k,
                        "indices": [i1, i2],
                        "values": [sc1.value, sc2.value],
                        "units": [sc1.unit, sc2.unit],
                        "claims": [sc1, sc2],
                        "texts": [texts[i1][:100], texts[i2][:100]]
                    })
    
    return conflicts


def format_contradiction(conflict: Dict[str, Any]) -> str:
    """
    Format a contradiction for display in reports.
    
    Args:
        conflict: Contradiction dictionary from find_numeric_conflicts
    
    Returns:
        Formatted string for display
    """
    key_parts = conflict["key"].split("|")
    entity = key_parts[0] if len(key_parts) > 0 else "Unknown"
    metric = key_parts[1] if len(key_parts) > 1 else "Unknown"
    period = key_parts[2] if len(key_parts) > 2 else "Unknown"
    
    v1, v2 = conflict["values"]
    u1, u2 = conflict["units"]
    
    # Format values with units
    val1_str = f"{v1}{u1 or ''}"
    val2_str = f"{v2}{u2 or ''}"
    
    return (
        f"**Conflicting values for {entity} {metric} in {period}:**\n"
        f"  - Source 1 claims: {val1_str}\n"
        f"  - Source 2 claims: {val2_str}\n"
    )