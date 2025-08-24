"""Test AREX reranking and filtering functionality."""

import pytest
from research_system.tools.arex_rerank import (
    jaccard_similarity,
    rerank_and_filter,
    filter_tangential_results
)


def test_jaccard_similarity():
    """Test Jaccard similarity calculation."""
    # Identical texts
    assert jaccard_similarity("hello world", "hello world") == 1.0
    
    # Partial overlap
    sim = jaccard_similarity("global tourism recovery", "tourism growth global")
    assert 0.5 < sim < 1.0
    
    # No overlap
    assert jaccard_similarity("apple orange", "car truck") == 0.0
    
    # Empty texts
    assert jaccard_similarity("", "") == 0.0
    assert jaccard_similarity("hello", "") == 0.0
    assert jaccard_similarity("", "world") == 0.0
    
    # Case insensitive
    assert jaccard_similarity("HELLO WORLD", "hello world") == 1.0


def test_filters_tangents():
    """Test that tangential results are filtered out."""
    key = "Germany international tourist arrivals Q1 2025"
    candidates = [
        ("Hotel jobs growth in Germany 2025", "url1"),
        ("International tourist arrivals up 5% in Q1 2025, Germany leads", "url2"),
        ("German tourism recovery statistics for first quarter 2025", "url3"),
        ("Visa requirements for Germany travel", "url4")
    ]
    
    # Use Jaccard fallback for deterministic testing
    results = rerank_and_filter(key, candidates, min_sim=0.2)
    
    # Extract URLs from results
    urls = [url for _, url, _ in results]
    
    # Should keep relevant results
    assert "url2" in urls or "url3" in urls
    
    # Should filter tangential results
    assert "url1" not in urls or "url4" not in urls


def test_rerank_empty_candidates():
    """Test reranking with empty candidates."""
    results = rerank_and_filter("test key", [])
    assert results == []


def test_filter_tangential_results():
    """Test filtering search results by structured key."""
    search_results = [
        {"title": "Tourism arrivals Q1 2025", "url": "url1", "snippet": "5% growth"},
        {"title": "Hotel jobs in tourism", "url": "url2", "snippet": "employment data"},
        {"title": "Q1 2025 arrivals statistics", "url": "url3", "snippet": "tourist data"}
    ]
    
    filtered = filter_tangential_results(
        key_entity="global",
        key_metric="tourist arrivals",
        key_period="Q1 2025",
        search_results=search_results,
        max_results=2
    )
    
    # Should keep relevant results
    assert len(filtered) <= 2
    
    # Should prioritize matching results
    if filtered:
        urls = [r["url"] for r in filtered]
        assert "url1" in urls or "url3" in urls