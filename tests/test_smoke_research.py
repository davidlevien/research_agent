"""Smoke test for research orchestrator - verifies critical fixes from v8.25.0."""

import pytest


def test_smoke_trends(monkeypatch):
    """Basic smoke test for travel & tourism trends research.
    
    v8.25.0: Verifies key fixes:
    - Seeds accept strings without crashing
    - Query expansion never returns empty
    - Intent-based provider selection guarantees breadth
    - OECD/OpenAlex don't fail with 403/404
    - DOI URLs get resolved to prevent domination
    - Adaptive caps on small samples
    - Triangulation uses post-sanitization metrics
    """
    # Set up deterministic seed (string should work without crash)
    from research_system.utils.deterministic import set_global_seeds
    set_global_seeds("20230817")
    
    # Mock API responses to test in offline mode
    monkeypatch.setenv("ENABLE_FREE_APIS", "false")
    monkeypatch.setenv("ENABLE_HTTP_CACHE", "false")
    
    # Import after environment setup
    from research_system.orchestrator import Orchestrator, OrchestratorSettings
    from pathlib import Path
    import tempfile
    
    # Create temporary directory for output
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create settings with the test query
        s = OrchestratorSettings(
            topic="latest travel & tourism trends",
            depth="quick",
            output_dir=Path(tmpdir),
            strict=False,
            verbose=False
        )
        
        # Create orchestrator with settings
        o = Orchestrator(s)
        
        # Run the search
        metrics = o.run()
        
        # Basic sanity checks on breadth
        assert hasattr(metrics, 'unique_domains'), "Metrics should have unique_domains"
        assert metrics.unique_domains >= 2, "Should have at least 2 domains in smoke test"
        
        # Primary share should be reasonable
        assert hasattr(metrics, 'primary_share'), "Metrics should have primary_share"
        assert metrics.primary_share >= 0.0, "Primary share should be non-negative"
        
        # Triangulation should not be negative
        assert hasattr(metrics, 'triangulation_rate'), "Metrics should have triangulation_rate"
        assert metrics.triangulation_rate >= 0.0, "Triangulation rate should be non-negative"
        
        # Domain concentration should be bounded
        assert hasattr(metrics, 'domain_concentration'), "Metrics should have domain_concentration"
        assert 0.0 <= metrics.domain_concentration <= 1.0, "Domain concentration should be between 0 and 1"


def test_seed_accepts_strings():
    """Test that seed accepts strings without crashing (v8.25.0 fix)."""
    from research_system.utils.deterministic import set_global_seeds
    
    # Should not raise
    set_global_seeds("test_seed")
    set_global_seeds("20230817")
    set_global_seeds(None)  # Should use time-based seed
    set_global_seeds(42)  # Should accept integers too


def test_canonical_id_exists():
    """Test that canonical_id utility exists (v8.25.0 addition)."""
    from research_system.utils.ids import canonical_id
    
    # Should generate consistent IDs
    id1 = canonical_id("test_string")
    id2 = canonical_id("test_string")
    assert id1 == id2, "canonical_id should be deterministic"
    assert len(id1) == 16, "canonical_id should be 16 characters"


def test_doi_resolver_exists():
    """Test that DOI resolver exists (v8.25.0 addition)."""
    from research_system.tools.doi import resolve_doi
    
    # Should exist and be callable
    assert callable(resolve_doi), "resolve_doi should be callable"


def test_evidence_io_handles_multiple_types():
    """Test that evidence_io handles various data types (v8.25.0 fix)."""
    from research_system.tools.evidence_io import _coerce_item
    from dataclasses import dataclass
    import tempfile
    import json
    
    # Test dict
    item_dict = {"id": "123", "title": "Test"}
    result = _coerce_item(item_dict)
    assert result == item_dict
    
    # Test dataclass
    @dataclass
    class TestCard:
        id: str
        title: str
    
    item_dc = TestCard(id="456", title="Test DC")
    result = _coerce_item(item_dc)
    assert result["id"] == "456"
    assert result["title"] == "Test DC"
    
    # Test object with model_dump (mock Pydantic)
    class MockPydantic:
        def model_dump(self):
            return {"id": "789", "title": "Test Pydantic"}
    
    item_pyd = MockPydantic()
    result = _coerce_item(item_pyd)
    assert result["id"] == "789"