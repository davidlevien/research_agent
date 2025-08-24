"""Strict mode acceptance gates for quality control."""

import json
from pathlib import Path
from typing import List


def strict_check(out_dir: Path) -> List[str]:
    """
    Check if output meets strict quality criteria.
    
    Args:
        out_dir: Output directory containing metrics.json
        
    Returns:
        List of error messages (empty if all checks pass)
    """
    errs = []
    
    # Load metrics
    metrics_path = out_dir / "metrics.json"
    if not metrics_path.exists():
        return ["METRICS_MISSING: metrics.json not found"]
    
    try:
        m = json.loads(metrics_path.read_text())
    except Exception as e:
        return [f"METRICS_INVALID: {e}"]
    
    # Check quote coverage
    quote_coverage = m.get("quote_coverage", 0)
    if quote_coverage < 0.70:
        errs.append(f"QUOTE_COVERAGE({quote_coverage:.0%}) < 70%")
    
    # Check triangulation rate
    union_triangulation = m.get("union_triangulation", 0)
    if union_triangulation < 0.35:
        errs.append(f"TRIANGULATION({union_triangulation:.0%}) < 35%")
    
    # Check primary share in union
    primary_share = m.get("primary_share_in_union", 0)
    if primary_share < 0.50:
        errs.append(f"PRIMARY_SHARE({primary_share:.0%}) < 50%")
    
    return errs