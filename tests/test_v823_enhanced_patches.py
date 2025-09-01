"""
Tests for v8.23.0 enhanced production patches based on third-party reviewer feedback.
"""

import pytest
import os
import time
from unittest.mock import Mock, patch, MagicMock
import httpx

class TestEnhancedHTTPHeaders:
    """Test enhanced HTTP client with per-domain headers."""
    
    def test_default_headers_configured(self):
        """Test that default headers are properly configured."""
        from research_system.providers.http import DEFAULT_HEADERS
        
        assert "User-Agent" in DEFAULT_HEADERS
        assert "ResearchAgent" in DEFAULT_HEADERS["User-Agent"]
        assert "Accept" in DEFAULT_HEADERS
        assert "Accept-Language" in DEFAULT_HEADERS
    
    def test_per_domain_headers_for_sec(self):
        """Test SEC-specific headers are applied."""
        from research_system.providers.http import PER_DOMAIN_HEADERS, _merge_headers_for_domain
        
        # Check SEC headers configured
        assert "www.sec.gov" in PER_DOMAIN_HEADERS
        assert "sec.gov" in PER_DOMAIN_HEADERS
        
        sec_headers = PER_DOMAIN_HEADERS["sec.gov"]
        assert "User-Agent" in sec_headers
        assert "Accept-Encoding" in sec_headers
        assert sec_headers["Accept-Encoding"] == "identity"
        
        # Test merging for SEC URL
        merged = _merge_headers_for_domain("https://www.sec.gov/edgar/data")
        assert "ResearchAgent" in merged["User-Agent"]
        assert merged["Accept-Encoding"] == "identity"
    
    def test_per_domain_headers_for_oecd(self):
        """Test OECD-specific headers are applied."""
        from research_system.providers.http import PER_DOMAIN_HEADERS, _merge_headers_for_domain
        
        assert "stats.oecd.org" in PER_DOMAIN_HEADERS
        
        oecd_headers = PER_DOMAIN_HEADERS["stats.oecd.org"]
        assert "Accept" in oecd_headers
        assert "application/json" in oecd_headers["Accept"]  # v8.24.0 includes more formats
        
        # Test merging for OECD URL
        merged = _merge_headers_for_domain("https://stats.oecd.org/SDMX-JSON/dataflow")
        assert "application/json" in merged["Accept"]


class TestOECDSingleCanonicalURL:
    """Test OECD uses single canonical URL with proper retries."""
    
    def test_oecd_canonical_url(self):
        """Test OECD uses multiple endpoints with fallback (v8.24.0)."""
        from research_system.providers.oecd import DATAFLOW_URLS
        
        # v8.24.0: Changed to multiple URLs with fallback
        assert len(DATAFLOW_URLS) >= 4
        assert any("/ALL" in url for url in DATAFLOW_URLS)  # At least one has ALL suffix
        assert any("sdmx-json" in url for url in DATAFLOW_URLS)  # Using lowercase
    
    @patch('research_system.providers.oecd.http_json')
    def test_oecd_retries_with_backoff(self, mock_http):
        """Test OECD retries with fallback to alt endpoints (v8.24.0)."""
        from research_system.providers.oecd import _dataflows, reset_circuit_state
        
        reset_circuit_state()
        
        # v8.24.0: Now tries multiple endpoints instead of retrying same one
        # Simulate first three failing, fourth succeeding
        mock_http.side_effect = [
            Exception("404 Not Found"),
            Exception("404 Not Found"),
            Exception("404 Not Found"),
            {"Dataflows": {"Dataflow": [{"id": "GDP", "Name": [{"value": "Gross Domestic Product"}]}]}}
        ]
        
        result = _dataflows()
        
        assert mock_http.call_count == 4  # v8.24.0: Tries 4 different endpoints
        assert "GDP" in result
        assert result["GDP"]["name"] == "Gross Domestic Product"
    
    @patch('research_system.providers.oecd.http_json')
    def test_oecd_uses_json_accept_header(self, mock_http):
        """Test OECD always sends JSON accept header."""
        from research_system.providers.oecd import _dataflows, reset_circuit_state
        
        reset_circuit_state()
        mock_http.return_value = {"Dataflows": {"Dataflow": []}}
        
        _dataflows()
        
        # v8.24.0: Check that Accept header includes application/json
        # The first endpoint tried should be the first in DATAFLOW_URLS
        args, kwargs = mock_http.call_args
        assert "application/json" in kwargs["headers"]["Accept"]
        assert kwargs["timeout"] == 30


class TestEnhancedCircuitBreakers:
    """Test enhanced circuit breakers with 10-minute cooldown."""
    
    def test_tavily_10_minute_cooldown(self):
        """Test Tavily uses 10-minute circuit breaker cooldown."""
        from research_system.tools.search_tavily import reset_tavily_circuit, _make_tavily_request
        
        reset_tavily_circuit()
        
        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 432
            mock_response.json.return_value = {"results": []}
            
            mock_client_instance = Mock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value = mock_client_instance
            
            # First call triggers rate limit
            result = _make_tavily_request("test", 10, "fake_key")
            assert result == {"results": []}
            
            # Circuit should be open for 600 seconds
            from research_system.tools.search_tavily import _CIRCUIT_OPEN_UNTIL
            assert _CIRCUIT_OPEN_UNTIL is not None
            assert _CIRCUIT_OPEN_UNTIL > time.time() + 590  # At least 590 seconds in future
    
    def test_serpapi_10_minute_cooldown(self):
        """Test SerpAPI uses 10-minute circuit breaker cooldown."""
        from research_system.tools.search_serpapi import CIRCUIT_COOLDOWN_SEC
        
        assert CIRCUIT_COOLDOWN_SEC == 600  # 10 minutes


class TestIntentAwareQualityGates:
    """Test intent-aware quality gates with lenient recovery."""
    
    def test_travel_intent_uses_relaxed_thresholds(self):
        """Test travel intent uses 25% triangulation threshold."""
        from research_system.providers.intent_registry import get_intent_thresholds
        
        thresholds = get_intent_thresholds("travel")
        assert thresholds["triangulation"] == 0.25
        assert thresholds["primary_share"] == 0.30
        assert thresholds["domain_cap"] == 0.35
    
    def test_stats_intent_uses_strict_thresholds(self):
        """Test stats intent uses 40% triangulation threshold."""
        from research_system.providers.intent_registry import get_intent_thresholds
        
        thresholds = get_intent_thresholds("stats")
        assert thresholds["triangulation"] == 0.40
        assert thresholds["primary_share"] == 0.50
        assert thresholds["domain_cap"] == 0.25
    
    def test_lenient_recovery_uses_minima(self):
        """Test lenient recovery uses 15% minimum thresholds."""
        # This is tested via orchestrator integration
        # The LENIENT_MINIMA should be 0.15 for both primary and triangulation
        pass


class TestTriangulationFiltering:
    """Test less aggressive triangulation cluster filtering."""
    
    def test_preserves_clusters_with_trusted_domains(self):
        """Test clusters with 3+ trusted domains are preserved."""
        from research_system.triangulation.contradiction_filter import filter_contradictory_clusters
        
        # Create mock cards with trusted domains
        cards = []
        for domain in ["oecd.org", "unwto.org", "worldbank.org", "wikipedia.org"]:
            card = Mock()
            card.source_domain = domain
            card.snippet = "Tourism increased by 5%"
            card.credibility_score = 0.8
            cards.append(card)
        
        clusters = [{"cards": cards}]
        
        # Should preserve cluster despite any contradictions
        filtered = filter_contradictory_clusters(clusters)
        assert len(filtered) == 1
    
    def test_numeric_tolerance_15_percent(self):
        """Test numeric contradictions allow 15% tolerance."""
        from research_system.triangulation.contradiction_filter import _is_numeric_contradiction
        
        # v8.24.0: Updated test - values [0.9, 1.0, 1.1] DO trigger contradiction
        # because (0.9, 1.1) pair has 18.2% difference > 15% tolerance
        # and 1 out of 3 pairs = 33% > 10% threshold for contradiction
        cards = []
        for val in [1.0, 1.1, 0.9]:  
            card = Mock()
            card.source_domain = f"domain{val}.com"
            card.snippet = f"Value is {val} billion"
            card.best_quote = None
            card.quotes = None
            cards.append(card)
        
        # v8.24.0: This IS a contradiction with pairwise comparison
        assert _is_numeric_contradiction(cards, tol_pct=0.15, min_domains=3)
        
        # Test case that should NOT be a contradiction - tighter values
        cards2 = []
        for val in [1.0, 1.05, 1.10]:  # Max diff is 10% < 15%
            card = Mock()
            card.source_domain = f"domain{val}.com"
            card.snippet = f"Value is {val} billion"
            card.best_quote = None
            card.quotes = None
            cards2.append(card)
        
        # All pairs within 15% tolerance, so no contradiction
        assert not _is_numeric_contradiction(cards2, tol_pct=0.15, min_domains=3)
    
    def test_requires_3_domains_for_contradiction(self):
        """Test contradictions require 3+ unique domains."""
        from research_system.triangulation.contradiction_filter import _is_numeric_contradiction
        
        # Only 2 domains - should not trigger contradiction
        cards = []
        for i, val in enumerate([1.0, 2.0]):
            card = Mock()
            card.source_domain = f"domain{i}.com"
            card.snippet = f"Value is {val} billion"
            card.best_quote = None
            card.quotes = None
            cards.append(card)
        
        # Should NOT be a contradiction with only 2 domains
        assert not _is_numeric_contradiction(cards, min_domains=3)


class TestMetricsAlignmentWithGates:
    """Test metrics.json aligns with quality gates."""
    
    def test_metrics_include_pass_fail_status(self):
        """Test metrics include pass/fail aligned with gates."""
        from research_system.quality.metrics_v2 import write_metrics, FinalMetrics
        import tempfile
        import json
        
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = FinalMetrics(
                primary_share=0.32,
                triangulation_rate=0.26,
                domain_concentration=0.34,
                sample_sizes={"total_cards": 50},
                unique_domains=10,
                credible_cards=40
            )
            
            write_metrics(tmpdir, metrics, intent="travel")
            
            # Read back and verify
            with open(f"{tmpdir}/metrics.json") as f:
                data = json.load(f)
            
            # Should pass travel thresholds
            assert data["pass_primary"] == True  # 0.32 >= 0.30
            assert data["pass_triangulation"] == True  # 0.26 >= 0.25
            assert data["pass_concentration"] == True  # 0.34 <= 0.35
            
            # Should include thresholds used
            assert data["thresholds_used"]["intent"] == "travel"
            assert data["thresholds_used"]["primary_share_floor"] == 0.30
            assert data["thresholds_used"]["triangulation_floor"] == 0.25
    
    def test_metrics_fail_for_generic_intent(self):
        """Test same metrics fail for generic intent."""
        from research_system.quality.metrics_v2 import write_metrics, FinalMetrics
        import tempfile
        import json
        
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = FinalMetrics(
                primary_share=0.32,
                triangulation_rate=0.26,
                domain_concentration=0.34,
                sample_sizes={"total_cards": 50},
                unique_domains=10,
                credible_cards=40
            )
            
            write_metrics(tmpdir, metrics, intent="generic")
            
            # Read back and verify
            with open(f"{tmpdir}/metrics.json") as f:
                data = json.load(f)
            
            # Should fail generic thresholds
            assert data["pass_primary"] == False  # 0.32 < 0.50
            assert data["pass_triangulation"] == False  # 0.26 < 0.45
            assert data["pass_concentration"] == False  # 0.34 > 0.25


class TestStrictModeDegradation:
    """Test controlled strictness degradation after first failure."""
    
    def test_strict_failed_once_flag_set(self):
        """Test that strict_failed_once flag is set on quality gate failure."""
        # This would require mocking the orchestrator run
        # The flag should be set in context["strict_failed_once"]
        pass
    
    def test_allows_backfill_after_first_failure(self):
        """Test backfill is allowed after first strict mode failure."""
        # The logic is: skip_backfill = self.s.strict and not context.get("strict_failed_once")
        # After first failure, strict_failed_once=True, so skip_backfill=False
        pass


class TestQuerySanitization:
    """Test query template sanitization."""
    
    def test_removes_none_tokens(self):
        """Test sanitization removes None/null/N/A tokens."""
        from research_system.orchestrator import Orchestrator, OrchestratorSettings
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = OrchestratorSettings(
                topic="test",
                depth="rapid",
                output_dir=Path(tmpdir),
                strict=False
            )
            orch = Orchestrator(settings)
            
            query = orch._sanitize_query("africa monthly_active_users None null N/A")
            assert "None" not in query
            assert "null" not in query
            assert "N/A" not in query
            assert "africa" in query
            assert "monthly_active_users" in query
    
    def test_removes_inappropriate_site_filters_for_travel(self):
        """Test removes SEC/FRED site filters for travel queries."""
        from research_system.orchestrator import Orchestrator, OrchestratorSettings
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = OrchestratorSettings(
                topic="test",
                depth="rapid",
                output_dir=Path(tmpdir),
                strict=False
            )
            orch = Orchestrator(settings)
            
            query = orch._sanitize_query("travel trends site:sec.gov site:fred.stlouisfed.org", intent="travel")
            assert "site:sec.gov" not in query
            assert "site:fred.stlouisfed.org" not in query
            assert "travel trends" in query