"""Test PE-grade cluster filtering with domain diversity."""

import pytest
from research_system.triangulation.post import sanitize_paraphrase_clusters, _cap_for_cluster


class MockCard:
    """Mock evidence card for testing."""
    def __init__(self, domain: str):
        self.source_domain = domain


def test_cap_for_cluster_calculation():
    """Test cluster size cap calculation with domain diversity."""
    # With 24 total cards:
    # Base cap = max(3, ceil(0.20 * 24)) = 5
    # Bonus per extra domain = ceil(0.10 * 24) = 3
    # Hard ceiling = max(8, ceil(0.35 * 24)) = max(8, 9) = 9
    assert _cap_for_cluster(5, 2, 24) == 8  # 2 domains: 5 + 3*1 = 8
    assert _cap_for_cluster(10, 3, 24) == 9  # 3 domains: 5 + 3*2 = 11, capped at 9
    assert _cap_for_cluster(15, 5, 24) == 9  # 5 domains: 5 + 3*4 = 17, capped at 9
    
    # Hard ceiling at max(8, 35%) = 9 cards (for 24 total)
    assert _cap_for_cluster(100, 10, 24) == 9  # Even with many domains, capped at 9


def test_single_domain_clusters_rejected():
    """Test that single-domain clusters are always rejected."""
    cards = [MockCard("example.com") for _ in range(10)]
    
    clusters = [{
        "indices": list(range(10)),
        "domains": ["example.com"],
        "representative_claim": "Test claim",
        "size": 10
    }]
    
    result = sanitize_paraphrase_clusters(clusters, cards)
    assert len(result) == 0  # Single-domain cluster rejected


def test_multi_domain_clusters_accepted():
    """Test that multi-domain clusters are accepted."""
    cards = [
        MockCard("example.com"),
        MockCard("test.org"),
        MockCard("example.com"),
        MockCard("test.org"),
    ]
    
    clusters = [{
        "indices": [0, 1, 2, 3],
        "domains": ["example.com", "test.org"],
        "representative_claim": "Test claim",
        "size": 4
    }]
    
    result = sanitize_paraphrase_clusters(clusters, cards)
    assert len(result) == 1  # Multi-domain cluster accepted


def test_oversized_cluster_trimmed():
    """Test that oversized clusters are trimmed to cap."""
    # Create 30 cards from 3 domains
    cards = []
    for i in range(30):
        domain = ["a.com", "b.org", "c.net"][i % 3]
        cards.append(MockCard(domain))
    
    # Create oversized cluster with similarity scores
    indices = list(range(30))
    sim_scores = [0.9 - (i * 0.01) for i in range(30)]  # Decreasing similarity
    
    clusters = [{
        "indices": indices,
        "domains": ["a.com", "b.org", "c.net"],
        "sim": sim_scores,
        "representative_claim": "Test",
        "size": 30
    }]
    
    result = sanitize_paraphrase_clusters(clusters, cards)
    assert len(result) == 1
    
    # Check that it was trimmed (3 domains = base 6 + bonus 2 = 8 cap)
    cap = _cap_for_cluster(30, 3, 30)
    assert len(result[0]["indices"]) <= cap
    
    # Check that highest similarity items were kept
    kept_indices = result[0]["indices"]
    for idx in kept_indices:
        assert idx in indices[:cap]  # Should be from the top similarity items


def test_empty_and_none_inputs():
    """Test edge cases with empty/None inputs."""
    cards = [MockCard("test.com")]
    
    # Empty clusters
    assert sanitize_paraphrase_clusters([], cards) == []
    
    # None clusters
    assert sanitize_paraphrase_clusters(None, cards) == []
    
    # Empty cards
    assert sanitize_paraphrase_clusters([{"indices": [0]}], []) == []