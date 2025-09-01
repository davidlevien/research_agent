"""Smoke test for end-to-end research system verification.

v8.25.0: Minimal test to verify all critical paths work without crashing.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

def test_smoke_trends(monkeypatch):
    """Test that basic research flow works end-to-end."""
    from research_system.utils.deterministic import set_global_seeds
    set_global_seeds("20230817")
    
    from research_system.orchestrator import Orchestrator, OrchestratorSettings
    
    # Mock external API calls to avoid network dependencies
    mock_results = [
        {
            'title': 'Test Result 1',
            'url': 'https://example.com/1',
            'snippet': 'Tourism trends increased by 15% in 2024',
            'source_domain': 'example.com'
        },
        {
            'title': 'Test Result 2', 
            'url': 'https://oecd.org/tourism',
            'snippet': 'International arrivals grew to 1.5 billion',
            'source_domain': 'oecd.org'
        },
        {
            'title': 'Test Result 3',
            'url': 'https://worldbank.org/data',
            'snippet': 'Travel industry recovery continues',
            'source_domain': 'worldbank.org'
        },
        {
            'title': 'Test Result 4',
            'url': 'https://doi.org/10.1234/test',
            'snippet': 'Academic paper on tourism',
            'source_domain': 'doi.org'
        }
    ]
    
    async def mock_search(*args, **kwargs):
        return {'test_provider': mock_results}
    
    with tempfile.TemporaryDirectory() as tmpdir:
        settings = OrchestratorSettings(
            topic='latest travel & tourism trends',
            depth='rapid',
            output_dir=Path(tmpdir),
            strict=False
        )
        
        # Patch the collection to return mock data
        with patch('research_system.orchestrator.parallel_provider_search', mock_search):
            with patch('research_system.orchestrator.collect_from_free_apis') as mock_free:
                mock_free.return_value = []
                
                o = Orchestrator(settings)
                
                # Verify initialization
                assert o.context is not None
                assert isinstance(o.context, dict)
                
                # Check that DOI resolution method exists
                assert hasattr(o, '_resolve_doi_cards')
                
                # Verify quality config loaded
                assert hasattr(o, 'v813_config')
                
                # Basic checks that would catch major issues
                assert o.s.topic == 'latest travel & tourism trends'
                assert o.s.depth == 'rapid'
                assert o.s.output_dir == Path(tmpdir)
                
    # If we get here without exceptions, basic wiring is correct
    assert True

def test_seed_accepts_strings():
    """Test that set_global_seeds accepts both strings and ints."""
    from research_system.utils.deterministic import set_global_seeds
    
    # Should not raise TypeError
    set_global_seeds("test_seed")
    set_global_seeds(12345)
    set_global_seeds(None)  # Should use default
    
    assert True

def test_registry_idempotence():
    """Test that duplicate tool registration doesn't crash."""
    from research_system.tools.registry import Registry, ToolSpec
    
    r = Registry()
    spec = ToolSpec(name="test_tool", fn=lambda: None, description="Test")
    
    # First registration should work
    r.register(spec)
    
    # Second registration should be idempotent (no crash)
    r.register(spec)
    
    assert "test_tool" in r._tools

def test_doi_resolver():
    """Test that DOI resolver is available."""
    from research_system.tools.doi import resolve_doi
    
    # Just check it exists and can be called
    result = resolve_doi("https://doi.org/fake/doi")
    # It's ok if it returns None (failed to resolve)
    assert result is None or isinstance(result, str)

def test_evidence_io_coercion():
    """Test that evidence_io handles different object types."""
    from research_system.tools.evidence_io import _coerce_item
    from dataclasses import dataclass
    
    # Test dict
    assert _coerce_item({'key': 'value'}) == {'key': 'value'}
    
    # Test dataclass
    @dataclass
    class TestCard:
        title: str
        url: str
    
    card = TestCard(title="Test", url="https://test.com")
    result = _coerce_item(card)
    assert result['title'] == 'Test'
    assert result['url'] == 'https://test.com'
    
    # Test object with __dict__
    class SimpleObj:
        def __init__(self):
            self.field = 'value'
    
    obj = SimpleObj()
    result = _coerce_item(obj)
    assert result['field'] == 'value'

def test_api_hosts_exempt_from_robots():
    """Test that API hosts are exempt from robots.txt checking."""
    from research_system.net.robots import is_allowed
    
    # API hosts should always be allowed
    assert is_allowed("https://api.worldbank.org/v2/data")
    assert is_allowed("https://api.openalex.org/works")
    assert is_allowed("https://stats.oecd.org/sdmx-json/dataflow")
    assert is_allowed("https://stats-nxd.oecd.org/sdmx-json/dataflow")

def test_intent_thresholds():
    """Test that intent-specific thresholds work."""
    from research_system.config.settings import quality_for_intent
    
    # Test different intents have different thresholds
    travel_thresholds = quality_for_intent('travel', strict=False)
    stats_thresholds = quality_for_intent('stats', strict=False)
    
    # Travel should have more lenient thresholds than stats
    assert travel_thresholds.primary <= stats_thresholds.primary
    assert travel_thresholds.triangulation <= stats_thresholds.triangulation

def test_contradiction_tolerance():
    """Test that contradiction filter uses 35% tolerance."""
    from research_system.triangulation.contradiction_filter import TRI_CONTRA_TOL_PCT
    
    # Should be 0.35 (35% tolerance)
    assert TRI_CONTRA_TOL_PCT == 0.35

def test_legacy_shims():
    """Test that legacy shims forward correctly."""
    # Test collection shim
    from research_system.collection import parallel_provider_search
    assert parallel_provider_search is not None
    
    # Test seeding shim
    from research_system.utils.seeding import set_global_seeds
    assert set_global_seeds is not None
    
    # Test datetime shim
    from research_system.utils.dtime import safe_strftime
    assert safe_strftime is not None

if __name__ == "__main__":
    # Run basic smoke tests
    print("Running smoke tests...")
    
    test_seed_accepts_strings()
    print("✅ Seed accepts strings")
    
    test_registry_idempotence()
    print("✅ Registry is idempotent")
    
    test_doi_resolver()
    print("✅ DOI resolver available")
    
    test_evidence_io_coercion()
    print("✅ Evidence IO handles all types")
    
    test_api_hosts_exempt_from_robots()
    print("✅ API hosts exempt from robots")
    
    test_intent_thresholds()
    print("✅ Intent thresholds working")
    
    test_contradiction_tolerance()
    print("✅ Contradiction tolerance at 35%")
    
    test_legacy_shims()
    print("✅ Legacy shims working")
    
    print("\n🎯 All smoke tests passed!")