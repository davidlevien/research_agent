#!/usr/bin/env python3.11
"""
Quality gate enforcement for CI/CD pipeline.

Usage:
    python scripts/quality_gate.py <output_dir>
    
Enforces minimum thresholds for all PE-grade metrics.
"""

import json
import sys
import pathlib
from typing import Dict, Any


def load_metrics(output_dir: pathlib.Path) -> Dict[str, Any]:
    """Load metrics from output directory."""
    metrics_file = output_dir / "metrics.json"
    if not metrics_file.exists():
        print(f"ERROR: {metrics_file} not found")
        sys.exit(1)
    
    with open(metrics_file, 'r') as f:
        return json.load(f)


def check_requirement(metrics: Dict[str, Any], name: str, op: str, threshold: float) -> bool:
    """Check if a metric meets the requirement."""
    value = metrics.get(name, 0.0)
    
    # Build the comparison expression
    expr = f"{value} {op} {threshold}"
    result = eval(expr)
    
    if not result:
        print(f"❌ FAIL {name}: {value:.3f} {op} {threshold}")
        return False
    else:
        print(f"✅ PASS {name}: {value:.3f} {op} {threshold}")
        return True


def main():
    """Run quality gate checks."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/quality_gate.py <output_dir>")
        sys.exit(1)
    
    output_dir = pathlib.Path(sys.argv[1])
    if not output_dir.exists():
        print(f"ERROR: Directory {output_dir} does not exist")
        sys.exit(1)
    
    # Load metrics
    metrics = load_metrics(output_dir)
    
    print("=" * 60)
    print("QUALITY GATE CHECKS")
    print("=" * 60)
    
    # Define requirements
    requirements = [
        ("quote_coverage", ">=", 0.70),
        ("union_triangulation", ">=", 0.35),
        ("primary_share_in_union", ">=", 0.50),
        ("top_domain_share", "<=", 0.25),
        ("provider_entropy", ">=", 0.60),
    ]
    
    # Check each requirement
    all_pass = True
    for name, op, threshold in requirements:
        if not check_requirement(metrics, name, op, threshold):
            all_pass = False
    
    print("=" * 60)
    
    # Additional checks for file existence
    required_files = [
        "evidence_cards.jsonl",
        "triangulation.json",
        "metrics.json",
        "final_report.md",
        "source_quality_table.md"
    ]
    
    print("\nFILE CHECKS:")
    for fname in required_files:
        fpath = output_dir / fname
        if fpath.exists():
            size = fpath.stat().st_size
            print(f"✅ {fname}: {size:,} bytes")
        else:
            print(f"❌ {fname}: MISSING")
            all_pass = False
    
    print("=" * 60)
    
    if all_pass:
        print("✅ QUALITY GATE: PASS")
        
        # Print summary metrics for README
        print("\n📊 Metrics Summary (for README):")
        print(json.dumps({
            "quote_coverage": round(metrics.get("quote_coverage", 0), 3),
            "union_triangulation": round(metrics.get("union_triangulation", 0), 3),
            "primary_share_in_union": round(metrics.get("primary_share_in_union", 0), 3),
            "top_domain_share": round(metrics.get("top_domain_share", 0), 3),
            "provider_entropy": round(metrics.get("provider_entropy", 0), 3),
            "cards": metrics.get("cards", 0)
        }, indent=2))
        sys.exit(0)
    else:
        print("❌ QUALITY GATE: FAIL")
        sys.exit(2)


if __name__ == "__main__":
    main()
