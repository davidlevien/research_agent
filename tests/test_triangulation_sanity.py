"""CI tests for triangulation sanity checks."""

import json
import pytest
from pathlib import Path
from research_system.triangulation.compute import union_rate


def test_union_not_exceed_cards():
    """Test that union rate doesn't exceed total cards."""
    # Mock triangulation data
    test_dir = Path("debug_test")
    if not test_dir.exists():
        pytest.skip("Debug test directory not found")
    
    tri_path = test_dir / "triangulation.json"
    cards_path = test_dir / "evidence_cards.jsonl"
    
    if not tri_path.exists() or not cards_path.exists():
        pytest.skip("Required test files not found")
    
    # Load data
    tri = json.load(open(tri_path))
    N = sum(1 for _ in open(cards_path))
    
    # Calculate union rate
    union = union_rate(
        tri.get("paraphrase_clusters", []),
        tri.get("structured_triangles", []),
        N
    )
    
    # Assert bounds
    assert 0.0 <= union <= 1.0, f"Union rate {union} out of bounds"


def test_no_giant_paraphrase_cluster():
    """Test that no single paraphrase cluster contains >50% of cards."""
    # Mock triangulation data
    test_dir = Path("debug_test")
    if not test_dir.exists():
        pytest.skip("Debug test directory not found")
    
    tri_path = test_dir / "triangulation.json"
    cards_path = test_dir / "evidence_cards.jsonl"
    
    if not tri_path.exists() or not cards_path.exists():
        pytest.skip("Required test files not found")
    
    # Load data
    tri = json.load(open(tri_path))
    N = sum(1 for _ in open(cards_path))
    
    # Check cluster sizes
    para_clusters = tri.get("paraphrase_clusters", [])
    for cluster in para_clusters:
        indices = cluster.get("indices", [])
        cluster_size = len(indices)
        
        assert cluster_size <= 0.5 * N, \
            f"Giant cluster found: {cluster_size}/{N} cards ({cluster_size/N:.0%})"


def test_triangulation_domains():
    """Test that triangulated clusters have multiple domains."""
    test_dir = Path("debug_test")
    if not test_dir.exists():
        pytest.skip("Debug test directory not found")
    
    tri_path = test_dir / "triangulation.json"
    if not tri_path.exists():
        pytest.skip("Triangulation file not found")
    
    tri = json.load(open(tri_path))
    
    # Check paraphrase clusters
    for cluster in tri.get("paraphrase_clusters", []):
        domains = cluster.get("domains", [])
        unique_domains = len(set(domains))
        assert unique_domains >= 2, \
            f"Paraphrase cluster has only {unique_domains} domain(s)"
    
    # Check structured triangles
    for triangle in tri.get("structured_triangles", []):
        domains = triangle.get("domains", [])
        unique_domains = len(set(domains))
        assert unique_domains >= 2, \
            f"Structured triangle has only {unique_domains} domain(s)"


def test_metrics_consistency():
    """Test that metrics.json values are consistent."""
    test_dir = Path("debug_test")
    if not test_dir.exists():
        pytest.skip("Debug test directory not found")
    
    metrics_path = test_dir / "metrics.json"
    if not metrics_path.exists():
        pytest.skip("Metrics file not found")
    
    metrics = json.load(open(metrics_path))
    
    # Check all required metrics exist
    required = ["cards", "quote_coverage", "union_triangulation", "primary_share_in_union"]
    for key in required:
        assert key in metrics, f"Missing required metric: {key}"
    
    # Check ranges
    assert 0 <= metrics["quote_coverage"] <= 1, "Quote coverage out of range"
    assert 0 <= metrics["union_triangulation"] <= 1, "Union triangulation out of range"
    assert 0 <= metrics["primary_share_in_union"] <= 1, "Primary share out of range"
    assert metrics["cards"] > 0, "Card count must be positive"