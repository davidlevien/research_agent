#!/usr/bin/env python3
"""Quality gate for CI - enforces minimum metrics thresholds."""
import json
import sys
import pathlib
from typing import Dict, List

def check_quality_gates(metrics_path: pathlib.Path) -> List[str]:
    """Check if metrics meet quality thresholds.
    
    Args:
        metrics_path: Path to metrics.json file
        
    Returns:
        List of failure messages (empty if all pass)
    """
    if not metrics_path.exists():
        return [f"Metrics file not found: {metrics_path}"]
    
    try:
        metrics = json.loads(metrics_path.read_text())
    except Exception as e:
        return [f"Failed to parse metrics: {e}"]
    
    errors = []
    
    def require(key: str, operator: str, threshold: float):
        """Check a single metric against threshold."""
        if key not in metrics:
            errors.append(f"Missing metric: {key}")
            return
        
        value = metrics[key]
        if operator == ">=":
            passed = value >= threshold
        elif operator == "<=":
            passed = value <= threshold
        elif operator == ">":
            passed = value > threshold
        elif operator == "<":
            passed = value < threshold
        else:
            errors.append(f"Invalid operator: {operator}")
            return
        
        if not passed:
            errors.append(f"{key}: {value:.3f} not {operator} {threshold}")
    
    # Define quality gates
    require("quote_coverage", ">=", 0.70)
    require("union_triangulation", ">=", 0.35)
    require("primary_share_in_union", ">=", 0.50)
    require("top_domain_share", "<=", 0.25)
    require("provider_entropy", ">=", 0.60)
    
    # Check for error rate if available
    if "error_rate" in metrics:
        require("error_rate", "<", 0.01)
    
    # Check wall time if available (900s = 15 min default)
    if "wall_time_seconds" in metrics:
        require("wall_time_seconds", "<=", 900)
    
    return errors


def main():
    """Main entry point for CI quality gate."""
    if len(sys.argv) < 2:
        print("Usage: python quality_gate.py <output_directory>")
        sys.exit(1)
    
    output_dir = pathlib.Path(sys.argv[1])
    metrics_path = output_dir / "metrics.json"
    
    errors = check_quality_gates(metrics_path)
    
    if errors:
        print("❌ QUALITY GATE FAILED:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(2)
    else:
        print("✅ QUALITY GATE PASSED")
        
        # Print metrics summary if available
        try:
            metrics = json.loads(metrics_path.read_text())
            print("\nMetrics summary:")
            print(f"  Quote coverage: {metrics.get('quote_coverage', 0):.1%}")
            print(f"  Triangulation: {metrics.get('union_triangulation', 0):.1%}")
            print(f"  Primary share: {metrics.get('primary_share_in_union', 0):.1%}")
            print(f"  Top domain share: {metrics.get('top_domain_share', 0):.1%}")
            print(f"  Provider entropy: {metrics.get('provider_entropy', 0):.2f}")
            if "wall_time_seconds" in metrics:
                print(f"  Wall time: {metrics['wall_time_seconds']:.1f}s")
        except Exception:
            pass
        
        sys.exit(0)


if __name__ == "__main__":
    main()