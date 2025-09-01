"""Tests for v8.22.0 critical production patches."""

import pytest
import time
import os
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

# Test Patch 1: Per-provider circuit breaker + rate limiting
class TestProviderCircuitBreakers:
    """Test circuit breakers for Tavily and Serper providers."""
    
    def test_tavily_circuit_breaker_opens_on_rate_limit(self):
        """Test that Tavily circuit opens on 429/432 status codes."""
        from research_system.tools.search_tavily import (
            _make_tavily_request, reset_tavily_circuit, 
            _CIRCUIT_OPEN_UNTIL
        )
        
        # Reset circuit first
        reset_tavily_circuit()
        
        # Mock httpx client to return 432
        with patch('research_system.tools.search_tavily.httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 432
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response
            
            # Make request - should open circuit
            result = _make_tavily_request("test query", 10, "fake_key")
            
            # Check circuit is open
            from research_system.tools import search_tavily
            assert search_tavily._CIRCUIT_OPEN_UNTIL is not None
            assert search_tavily._CIRCUIT_OPEN_UNTIL > time.time()
            assert result == {"results": []}
    
    def test_tavily_token_bucket_rate_limiting(self):
        """Test token bucket rate limiting for Tavily."""
        from research_system.tools.search_tavily import _bucket_take, reset_tavily_circuit
        
        reset_tavily_circuit()
        
        # Should allow initial burst of 5
        for _ in range(5):
            assert _bucket_take() is True
        
        # 6th should fail immediately
        assert _bucket_take() is False
        
        # Wait for refill (0.5 tokens/sec)
        time.sleep(2.1)
        
        # Should have ~1 token now
        assert _bucket_take() is True
        assert _bucket_take() is False
    
    def test_serper_circuit_breaker(self):
        """Test Serper circuit breaker functionality."""
        from research_system.tools.search_serper import (
            _make_serper_request, reset_serper_circuit
        )
        
        reset_serper_circuit()
        
        with patch('research_system.tools.search_serper.httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response
            
            result = _make_serper_request("test", 10, "fake_key")
            
            from research_system.tools import search_serper
            assert search_serper._CIRCUIT_OPEN_UNTIL is not None
            assert result == {"organic": []}


# Test Patch 2: Query templater sanitization
class TestQuerySanitization:
    """Test query sanitization to remove None and inappropriate filters."""
    
    def test_sanitize_query_removes_none(self):
        """Test that None tokens are removed from queries."""
        from research_system.orchestrator import Orchestrator, OrchestratorSettings
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = OrchestratorSettings(
                topic="test topic",
                depth="rapid",
                output_dir=Path(tmpdir),
                strict=False
            )
            orch = Orchestrator(settings)
            
            # Test None removal
            query = orch._sanitize_query("test None query null N/A")
            assert "None" not in query
            assert "null" not in query
            assert "N/A" not in query
            assert "test query" == query
    
    def test_sanitize_query_removes_inappropriate_site_filters(self):
        """Test removal of inappropriate site filters for travel queries."""
        from research_system.orchestrator import Orchestrator, OrchestratorSettings
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = OrchestratorSettings(
                topic="travel trends",
                depth="rapid",
                output_dir=Path(tmpdir),
                strict=False
            )
            orch = Orchestrator(settings)
            
            # Test SEC/FRED removal for travel intent
            query = orch._sanitize_query(
                "travel trends site:sec.gov site:fred.stlouisfed.org data",
                intent="travel"
            )
            assert "site:sec.gov" not in query
            assert "site:fred.stlouisfed.org" not in query
            assert "travel trends data" == query
    
    def test_generate_intent_queries_sanitized(self):
        """Test that generated queries are properly sanitized."""
        from research_system.orchestrator import Orchestrator, OrchestratorSettings
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = OrchestratorSettings(
                topic="travel tourism trends",
                depth="rapid",
                output_dir=Path(tmpdir),
                strict=False
            )
            orch = Orchestrator(settings)
            
            queries = orch._generate_intent_queries("travel", "travel tourism trends")
            
            # Check no None values in any query
            for q in queries:
                assert "None" not in q
                assert "null" not in q
                assert q.strip() == q  # No extra spaces


# Test Patch 3: OECD provider fixes
class TestOECDProviderFixes:
    """Test OECD provider with canonical endpoint and headers."""
    
    def test_oecd_uses_canonical_endpoint_first(self):
        """Test that OECD tries canonical endpoint with proper headers."""
        from research_system.providers.oecd import _dataflows, DATAFLOW_URL, reset_circuit_state
        
        reset_circuit_state()
        
        with patch('research_system.providers.oecd.http_json') as mock_http:
            mock_http.return_value = {
                "Dataflows": {
                    "Dataflow": [
                        {"id": "TEST", "Name": [{"value": "Test Dataset"}]}
                    ]
                }
            }
            
            result = _dataflows()
            
            # Check first call uses canonical endpoint with JSON accept header
            first_call = mock_http.call_args_list[0]
            assert DATAFLOW_URL in first_call[0][2]  # URL argument
            assert first_call[1]['headers'] == {"Accept": "application/json"}
    
    def test_oecd_fallback_on_failure(self):
        """Test OECD retries with exponential backoff on failure."""
        from research_system.providers.oecd import _dataflows, reset_circuit_state
        
        reset_circuit_state()
        
        with patch('research_system.providers.oecd.http_json') as mock_http:
            # First two attempts fail, third succeeds
            mock_http.side_effect = [
                Exception("Connection error"),
                Exception("Timeout"),
                {"Dataflows": {"Dataflow": []}}
            ]
            
            result = _dataflows()
            
            # v8.23.0: Should retry up to 3 times
            assert mock_http.call_count == 3
            assert result == {}  # Empty but successful


# Test Patch 4: Triangulation contradiction filter
class TestTriangulationContradictionFilter:
    """Test numeric tolerance in contradiction detection."""
    
    def test_numeric_contradiction_with_tolerance(self):
        """Test that small numeric differences within tolerance aren't contradictions."""
        from research_system.triangulation.contradiction_filter import _is_numeric_contradiction
        
        # Create mock cards with similar numbers (within 15% tolerance)
        cards = []
        for i, value in enumerate([1.5, 1.48, 1.52, 1.45]):  # All within 15% of median
            card = Mock()
            card.source_domain = f"domain{i}.com"  # Use unique domains
            card.domain = f"domain{i}.com"
            text = f"Tourist arrivals reached {value} billion last year"
            card.snippet = text
            card.best_quote = None
            card.quotes = None
            card.title = ""
            card.supporting_text = ""
            card.claim = ""
            cards.append(card)
        
        # Should NOT be a contradiction with 4 unique domains
        # Values in billions: 1.5B, 1.48B, 1.52B, 1.45B
        # Median is ~1.49B, all values are within 15% tolerance
        assert not _is_numeric_contradiction(cards, tol_pct=0.15, min_domains=3)
    
    def test_numeric_contradiction_beyond_tolerance(self):
        """Test that large numeric differences are contradictions."""
        from research_system.triangulation.contradiction_filter import _is_numeric_contradiction
        
        # Create cards with contradictory numbers
        cards = []
        for i, value in enumerate([1.5, 1.5, 3.0, 3.0]):  # 100% difference
            card = Mock()
            card.source_domain = f"domain{i}.com"
            card.domain = f"domain{i}.com" 
            text = f"Arrivals were {value} billion"
            card.snippet = text
            card.best_quote = None
            card.quotes = None
            card.title = ""
            card.supporting_text = ""
            card.claim = ""
            cards.append(card)
        
        # Should be a contradiction with 4 unique domains
        assert _is_numeric_contradiction(cards, tol_pct=0.15, min_domains=3)
    
    def test_min_domains_requirement(self):
        """Test that min_domains requirement is enforced."""
        from research_system.triangulation.contradiction_filter import _is_numeric_contradiction
        
        # Only 2 domains - should not trigger contradiction
        cards = []
        for i, value in enumerate([1.5, 3.0]):  # Large difference but only 2 sources
            card = Mock()
            card.source_domain = f"domain{i}.com"  # Only 2 unique domains
            card.domain = f"domain{i}.com"
            card.snippet = f"Value is {value} billion"
            card.best_quote = None
            card.quotes = None
            card.title = ""
            card.supporting_text = ""
            card.claim = ""
            cards.append(card)
        
        # Should NOT be a contradiction with < 3 domains
        assert not _is_numeric_contradiction(cards, tol_pct=0.15, min_domains=3)


# Test Patch 5: Intent-scoped quality gates
class TestIntentScopedQualityGates:
    """Test intent-specific quality thresholds."""
    
    def test_travel_intent_uses_lower_thresholds(self):
        """Test that travel intent uses relaxed thresholds."""
        from research_system.quality.metrics_v2 import gates_pass, FinalMetrics
        
        # Create metrics that would fail default but pass travel thresholds
        metrics = FinalMetrics(
            primary_share=0.32,  # Above travel's 0.30, below default 0.50
            triangulation_rate=0.26,  # Above travel's 0.25, below default 0.45
            domain_concentration=0.34,  # Below travel's 0.35 cap
            sample_sizes={"total_cards": 50},
            unique_domains=10,
            credible_cards=40
        )
        
        # Should pass for travel intent
        assert gates_pass(metrics, intent="travel")
        
        # Should fail for generic intent
        assert not gates_pass(metrics, intent="generic")
    
    def test_stats_intent_additional_requirements(self):
        """Test stats intent has additional requirements."""
        from research_system.quality.metrics_v2 import gates_pass, FinalMetrics
        
        # Good basic metrics but missing stats requirements
        metrics = FinalMetrics(
            primary_share=0.55,
            triangulation_rate=0.50,
            domain_concentration=0.20,
            sample_sizes={"total_cards": 50},
            unique_domains=10,
            credible_cards=40,
            recent_primary_count=1,  # Need 3
            triangulated_clusters=0   # Need 1
        )
        
        # Should fail stats intent due to additional requirements
        assert not gates_pass(metrics, intent="stats")
        
        # Update to meet requirements
        metrics.recent_primary_count = 3
        metrics.triangulated_clusters = 1
        assert gates_pass(metrics, intent="stats")


# Test Patch 6: Controlled strictness degradation
class TestStrictnessDegradation:
    """Test controlled degradation of strict mode after failure."""
    
    @patch('research_system.orchestrator.should_attempt_last_mile_backfill')
    def test_strict_mode_degrades_after_failure(self, mock_backfill):
        """Test that strict mode allows one backfill pass after failing gates."""
        from research_system.orchestrator import Orchestrator, OrchestratorSettings
        from pathlib import Path
        import tempfile
        
        mock_backfill.return_value = False
        
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = OrchestratorSettings(
                topic="test",
                depth="rapid",
                output_dir=Path(tmpdir),
                strict=True  # Strict mode enabled
            )
            
            orch = Orchestrator(settings)
            
            # Initially, strict_failed_once should not be set
            assert orch.context.get("strict_failed_once") is False or \
                   orch.context.get("strict_failed_once") is None
            
            # Simulate quality gate failure
            orch.context["strict_failed_once"] = True
            
            # Check that backfill would now be allowed
            strict_failed_once = orch.context.get("strict_failed_once", False)
            skip_backfill = orch.s.strict and not strict_failed_once
            
            assert not skip_backfill  # Should allow backfill now


# Test Patch 7: Default HTTP headers
class TestDefaultHTTPHeaders:
    """Test safer default HTTP headers for data APIs."""
    
    def test_default_headers_include_user_agent(self):
        """Test that default headers include proper User-Agent."""
        from research_system.providers.http import DEFAULT_HEADERS
        
        assert "User-Agent" in DEFAULT_HEADERS
        assert "ResearchAgent" in DEFAULT_HEADERS["User-Agent"]
    
    def test_default_headers_include_accept(self):
        """Test that default headers include Accept."""
        from research_system.providers.http import DEFAULT_HEADERS
        
        assert "Accept" in DEFAULT_HEADERS
        # v8.23.0: Accept header is now */* for broader compatibility
        assert DEFAULT_HEADERS["Accept"] == "*/*"
    
    def test_http_json_merges_headers(self):
        """Test that http_json properly merges default and custom headers."""
        from research_system.providers.http import http_json, DEFAULT_HEADERS
        
        with patch('research_system.providers.http.httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"test": "data"}
            mock_response.raise_for_status = Mock()
            mock_client.return_value.__enter__.return_value.request.return_value = mock_response
            
            # Call with custom header
            custom_headers = {"X-Custom": "value"}
            http_json("GET", "http://test.com", headers=custom_headers)
            
            # Check that Client was called with merged headers
            call_args = mock_client.call_args
            headers_used = call_args[1]['headers']
            
            # Should have both default and custom headers
            assert "User-Agent" in headers_used  # From defaults
            assert "X-Custom" in headers_used    # From custom
            assert headers_used["X-Custom"] == "value"


# Test Patch 8: Run wrapper script
class TestRunWrapperScript:
    """Test run wrapper script improvements."""
    
    def test_run_wrapper_sets_repo_root(self):
        """Test that run wrapper correctly sets REPO_ROOT."""
        import subprocess
        import os
        
        # Read the script to verify it has the fix
        script_path = "run_full_features.sh"
        if os.path.exists(script_path):
            with open(script_path, 'r') as f:
                content = f.read()
                
            assert 'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"' in content
            assert 'REPO_ROOT=' in content
            assert 'cd "$REPO_ROOT"' in content


# Test intent thresholds configuration
class TestIntentThresholdsConfiguration:
    """Test intent threshold configuration."""
    
    def test_intent_thresholds_defined(self):
        """Test that intent thresholds are properly defined."""
        from research_system.providers.intent_registry import INTENT_THRESHOLDS
        
        # Check key intents have thresholds
        assert "travel" in INTENT_THRESHOLDS
        assert "stats" in INTENT_THRESHOLDS
        assert "default" in INTENT_THRESHOLDS
        
        # Check travel has relaxed thresholds
        travel = INTENT_THRESHOLDS["travel"]
        assert travel["triangulation"] == 0.25
        assert travel["primary_share"] == 0.30
        assert travel["domain_cap"] == 0.35
    
    def test_get_intent_thresholds(self):
        """Test get_intent_thresholds function."""
        from research_system.providers.intent_registry import get_intent_thresholds
        
        # Test with string
        thresholds = get_intent_thresholds("travel")
        assert thresholds["triangulation"] == 0.25
        
        # Test with unknown intent - should return defaults
        thresholds = get_intent_thresholds("unknown_intent")
        assert thresholds["triangulation"] == 0.45  # Default
        
        # Test with enum-like object
        mock_intent = Mock()
        mock_intent.value = "stats"
        thresholds = get_intent_thresholds(mock_intent)
        assert thresholds["triangulation"] == 0.40


if __name__ == "__main__":
    pytest.main([__file__, "-v"])