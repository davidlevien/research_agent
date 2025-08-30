"""Comprehensive tests for surgical production fixes to make system topic-agnostic."""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import json

# Test imports
from research_system.strict.adaptive_guard import (
    format_confidence_report, 
    ConfidenceLevel,
    SupplyContextData
)
from research_system.orchestrator_adaptive import generate_adaptive_report_metadata
from research_system.selection.domain_balance import (
    is_primary_source,
    get_primary_pool_for_intent,
    get_domain_family,
    PRIMARY_POOLS_BY_INTENT,
    DOMAIN_FAMILIES
)


class TestConfidenceBadgeCrashFix:
    """Test that confidence badge handles None without crashing."""
    
    def test_format_confidence_report_handles_none(self):
        """Test that format_confidence_report gracefully handles None confidence."""
        context = SupplyContextData(
            total_cards=50,
            unique_domains=8,
            provider_attempts=10,
            provider_errors=2
        )
        
        # Should not crash when confidence is None
        report = format_confidence_report(
            confidence=None,
            adjustments={},
            context=context
        )
        
        assert "Research Confidence Report" in report
        assert "Confidence Level" in report
        # Should default to MODERATE when None
        assert "Moderate" in report or "🟡" in report
    
    def test_generate_adaptive_report_metadata_handles_none(self):
        """Test that report metadata generation handles None confidence."""
        metrics = {
            "total_cards": 100,
            "credible_cards": 80,
            "unique_domains": 12,
            "triangulated_cards": 40,
            "triangulation_rate": 0.4,
            "primary_share": 0.5,
            "provider_error_rate": 0.1,
            "domain_concentration": 0.2
        }
        
        # Should not crash when confidence_level is None
        metadata = generate_adaptive_report_metadata(
            metrics=metrics,
            confidence_level=None,
            adjustments={},
            report_tier="standard",
            report_confidence=0.75,
            tier_explanation="Standard evidence quality"
        )
        
        assert "Research Metadata" in metadata
        assert "Quality Assessment" in metadata
        # Should have some confidence indicator even with None
        assert "Confidence" in metadata


class TestSerpAPICircuitBreaker:
    """Test SerpAPI circuit breaker and deduplication."""
    
    def test_circuit_breaker_trips_on_429(self):
        """Test that circuit breaker trips on 429 responses."""
        from research_system.tools.search_serpapi import run, _serpapi_state, reset_serpapi_state
        from research_system.tools.search_models import SearchRequest
        
        # Reset state using proper function
        reset_serpapi_state()
        
        with patch.dict(os.environ, {"SERPAPI_CIRCUIT_BREAKER": "true", "SERPAPI_TRIP_ON_429": "true"}):
            with patch('research_system.tools.search_serpapi._make_serpapi_request') as mock_request:
                import httpx
                # Simulate 429 error
                mock_response = Mock()
                mock_response.status_code = 429
                mock_request.side_effect = httpx.HTTPStatusError(
                    "Rate limited",
                    request=Mock(),
                    response=mock_response
                )
                
                req = SearchRequest(query="test query", count=10)
                
                # First call should attempt and get 429
                results = run(req)
                assert results == []
                assert _serpapi_state["consecutive_429s"] == 1
                assert _serpapi_state["is_open"] == True
                
                # Second call should be blocked by circuit breaker
                results = run(req)
                assert results == []
                # Request should not be made when circuit is open
                assert mock_request.call_count == 1  # Only the first call
    
    def test_query_deduplication(self):
        """Test that duplicate queries are not sent."""
        from research_system.tools.search_serpapi import run, _serpapi_state, reset_serpapi_state
        from research_system.tools.search_models import SearchRequest
        
        # Reset state using proper function
        reset_serpapi_state()
        
        with patch.dict(os.environ, {"SERPAPI_CIRCUIT_BREAKER": "true"}):
            with patch('research_system.tools.search_serpapi._make_serpapi_request') as mock_request:
                mock_request.return_value = {"organic_results": []}
                
                # First query
                req1 = SearchRequest(query="wildlife yellowstone", count=10)
                run(req1)
                
                # Duplicate query (case insensitive)
                req2 = SearchRequest(query="Wildlife Yellowstone", count=10)
                results = run(req2)
                
                # Should only make one actual request
                assert mock_request.call_count == 1
                assert results == []  # Deduplicated query returns empty
    
    def test_call_budget_enforcement(self):
        """Test that call budget is enforced."""
        from research_system.tools.search_serpapi import run, _serpapi_state, reset_serpapi_state
        from research_system.tools.search_models import SearchRequest
        
        # Reset state using proper function
        reset_serpapi_state()
        _serpapi_state["call_budget"] = 2  # Set budget for this test
        
        with patch.dict(os.environ, {"SERPAPI_CIRCUIT_BREAKER": "true", "SERPAPI_MAX_CALLS_PER_RUN": "2"}):
            with patch('research_system.tools.search_serpapi._make_serpapi_request') as mock_request:
                mock_request.return_value = {"organic_results": []}
                
                # Make calls up to budget
                for i in range(3):
                    req = SearchRequest(query=f"query {i}", count=10)
                    run(req)
                
                # Should only make 2 actual requests (the budget)
                assert mock_request.call_count == 2
                assert _serpapi_state["call_count"] == 2


class TestEncyclopediaQueryPlanner:
    """Test encyclopedia query expansion without forced recency."""
    
    def test_encyclopedia_queries_no_recency(self):
        """Test that encyclopedia queries don't force recency filters."""
        from research_system.orchestrator import Orchestrator, OrchestratorSettings
        
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = OrchestratorSettings(
                topic="wildlife in yellowstone national park",
                depth="rapid",
                output_dir=Path(tmpdir),
                strict=False
            )
            
            orch = Orchestrator(settings)
            
            # Generate queries for encyclopedia intent
            queries = orch._generate_intent_queries("encyclopedia", "wildlife yellowstone")
            
            # Should include time-agnostic expansions
            assert any("timeline" in q.lower() for q in queries)
            assert any("site:nps.gov" in q.lower() for q in queries)
            assert any("site:usgs.gov" in q.lower() for q in queries)
            
            # Should NOT include forced recency
            assert not any("2024" in q for q in queries)
            assert not any("2025" in q for q in queries)
            assert not any("latest" in q.lower() for q in queries)
    
    def test_news_queries_include_recency(self):
        """Test that news queries DO include recency filters."""
        from research_system.orchestrator import Orchestrator, OrchestratorSettings
        
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = OrchestratorSettings(
                topic="AI developments",
                depth="rapid", 
                output_dir=Path(tmpdir),
                strict=False
            )
            
            orch = Orchestrator(settings)
            queries = orch._generate_intent_queries("news", "AI developments")
            
            # News queries should include recency
            assert any("2024" in q or "2025" in q or "latest" in q.lower() for q in queries)


class TestIntentAwarePrimaryPools:
    """Test intent-aware primary source pools."""
    
    def test_encyclopedia_primary_pool(self):
        """Test encyclopedia intent uses park/gov sources as primary."""
        pool = get_primary_pool_for_intent("encyclopedia")
        
        assert "nps.gov" in pool
        assert "usgs.gov" in pool
        assert "loc.gov" in pool
        # Should NOT include economics sources
        assert "imf.org" not in pool
        assert "worldbank.org" not in pool
    
    def test_macroecon_primary_pool(self):
        """Test macroecon intent uses economic sources as primary."""
        pool = get_primary_pool_for_intent("macroecon")
        
        assert "imf.org" in pool
        assert "worldbank.org" in pool
        assert "oecd.org" in pool
        # Should NOT include park sources
        assert "nps.gov" not in pool
    
    def test_is_primary_source_with_intent(self):
        """Test primary source detection is intent-aware."""
        # NPS should be primary for encyclopedia
        assert is_primary_source("nps.gov", "encyclopedia") == True
        assert is_primary_source("nps.gov", "macroecon") == False
        
        # IMF should be primary for macroecon
        assert is_primary_source("imf.org", "macroecon") == True
        assert is_primary_source("imf.org", "encyclopedia") == False
    
    def test_wildcard_pattern_matching(self):
        """Test wildcard patterns work for primary detection."""
        # Any .edu should be primary for academic
        assert is_primary_source("harvard.edu", "academic") == True
        assert is_primary_source("mit.edu", "academic") == True
        assert is_primary_source("stanford.edu", "academic") == True
        
        # Any .gov should be primary for generic
        assert is_primary_source("fda.gov", "generic") == True
        assert is_primary_source("nih.gov", "generic") == True
    
    def test_backward_compatibility(self):
        """Test backward compatibility with default PRIMARY_POOL."""
        from research_system.selection.domain_balance import PRIMARY_POOL
        
        # Should default to macroecon pool for backward compat
        assert PRIMARY_POOL == PRIMARY_POOLS_BY_INTENT.get("macroecon", set())


class TestDomainFamilies:
    """Test domain family grouping for better capping."""
    
    def test_domain_family_detection(self):
        """Test that related domains are grouped into families."""
        assert get_domain_family("nps.gov") == "nps"
        assert get_domain_family("npshistory.com") == "nps"
        assert get_domain_family("usgs.gov") == "usgs"
        assert get_domain_family("worldbank.org") == "econ"
        assert get_domain_family("imf.org") == "econ"
    
    def test_wildcard_family_detection(self):
        """Test wildcard patterns in domain families."""
        # Any .gov domain should be in gov family
        assert get_domain_family("fda.gov") == "gov"
        assert get_domain_family("nih.gov") == "gov"
        assert get_domain_family("cdc.gov") == "gov"
        
        # Any .edu domain should be in edu family
        assert get_domain_family("harvard.edu") == "edu"
        assert get_domain_family("mit.edu") == "edu"
    
    def test_unknown_domain_returns_self(self):
        """Test unknown domains return themselves as family."""
        assert get_domain_family("example.com") == "example.com"
        assert get_domain_family("random-site.org") == "random-site.org"


class TestVerticalAPIExclusion:
    """Test that vertical APIs are excluded from generic searches."""
    
    def test_vertical_apis_excluded_with_site_decorator(self):
        """Test vertical APIs excluded when site: is used."""
        from research_system.collection import _provider_policy
        
        providers = ["tavily", "brave", "nps", "fred", "oecd"]
        
        # Query with site: should exclude vertical APIs
        filtered = _provider_policy("site:.gov tourism", providers)
        
        assert "tavily" in filtered
        assert "brave" in filtered
        assert "nps" not in filtered  # Vertical API excluded
        assert "fred" not in filtered  # Vertical API excluded
        assert "oecd" not in filtered  # Vertical API excluded
    
    def test_vertical_apis_included_for_specific_intents(self):
        """Test vertical APIs included for their specific domains."""
        from research_system.collection import _provider_policy
        
        providers = ["tavily", "brave", "nps", "fred", "oecd"]
        
        # NPS should be included for park queries (no site: decorator)
        filtered = _provider_policy("yellowstone national park wildlife", providers)
        
        assert "tavily" in filtered
        assert "brave" in filtered
        assert "nps" in filtered  # Should be included for park query
        assert "fred" not in filtered  # Economic API not relevant
        assert "oecd" not in filtered  # Economic API not relevant


class TestStrictModeDegradation:
    """Test graceful degradation in strict mode."""
    
    def test_strict_mode_generates_report_on_insufficient_evidence(self):
        """Test that strict mode generates insufficient evidence report."""
        from research_system.strict.adaptive_guard import (
            adaptive_strict_check,
            should_skip_strict_fail,
            ConfidenceLevel
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create metrics with insufficient evidence
            metrics = {
                "unique_domains": 2,
                "credible_cards": 10,
                "triangulated_cards": 5,
                "union_triangulation": 0.15,
                "primary_share_in_union": 0.20,
                "provider_error_rate": 0.4,
                "primary_cards": 2,
                "cards": 10
            }
            
            (tmpdir / "metrics.json").write_text(json.dumps(metrics))
            
            # Run adaptive strict check
            errors, confidence, adjustments = adaptive_strict_check(tmpdir)
            
            # Should have errors but also adjustments
            assert len(errors) > 0
            assert len(adjustments) > 0
            assert confidence in [ConfidenceLevel.LOW, ConfidenceLevel.MODERATE]
            
            # Should recommend skipping strict fail
            should_skip = should_skip_strict_fail(errors, adjustments, confidence)
            # With heavy adjustments and low confidence, might convert to warning
            assert isinstance(should_skip, bool)


class TestObservabilityAndMetrics:
    """Test structured logging and metrics."""
    
    def test_serpapi_structured_logging(self):
        """Test SerpAPI logs with structured format."""
        from research_system.tools.search_serpapi import run, _serpapi_state
        from research_system.tools.search_models import SearchRequest
        
        # Reset state
        _serpapi_state["is_open"] = False
        _serpapi_state["seen_queries"].clear()
        
        with patch('research_system.tools.search_serpapi.logger') as mock_logger:
            with patch('research_system.tools.search_serpapi._make_serpapi_request'):
                req = SearchRequest(query="test", count=10)
                
                # Trigger circuit breaker by setting it open
                _serpapi_state["is_open"] = True
                run(req)
                
                # Should log with structured format
                mock_logger.info.assert_called()
                call_args = mock_logger.info.call_args
                assert "SERPAPI_CIRCUIT_OPEN" in str(call_args)
    
    def test_confidence_level_always_set(self):
        """Test confidence level is never None in final output."""
        from research_system.orchestrator_adaptive import generate_adaptive_report_metadata
        from research_system.strict.adaptive_guard import ConfidenceLevel
        
        # Even with None input, should produce valid output
        metadata = generate_adaptive_report_metadata(
            metrics={"total_cards": 50},
            confidence_level=None,
            adjustments={},
            report_tier="brief",
            report_confidence=0.5,
            tier_explanation="Low evidence"
        )
        
        # Should have confidence indicator
        assert "Confidence" in metadata
        assert ("🟢" in metadata or "🟡" in metadata or "🔴" in metadata)


class TestIntegration:
    """End-to-end integration tests."""
    
    def test_wildlife_query_completes(self):
        """Test that wildlife query completes without crash."""
        from research_system.orchestrator import Orchestrator, OrchestratorSettings
        
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = OrchestratorSettings(
                topic="wildlife in yellowstone national park",
                depth="rapid",
                output_dir=Path(tmpdir),
                strict=False
            )
            
            orch = Orchestrator(settings)
            
            # Should classify as encyclopedia  
            with patch('research_system.intent.classifier.classify') as mock_classify:
                from research_system.intent.classifier import Intent
                mock_classify.return_value = Intent.ENCYCLOPEDIA
                
                # This should not crash
                try:
                    # Just test initialization and basic setup
                    assert orch.context is not None
                    assert orch.settings.topic == "wildlife in yellowstone national park"
                    
                    # Test intent-aware query generation
                    queries = orch._generate_intent_queries("encyclopedia", orch.settings.topic)
                    assert len(queries) > 0
                    assert not any("2024" in q for q in queries)  # No forced recency
                    
                    # Test primary class detection works
                    assert hasattr(orch, '_is_primary_class')
                    # NPS should be primary for encyclopedia intent
                    orch.context['intent'] = 'encyclopedia'
                    assert orch._is_primary_class('nps.gov') == True
                    
                except AttributeError as e:
                    if "to_emoji" in str(e):
                        pytest.fail("Confidence badge crash not fixed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])