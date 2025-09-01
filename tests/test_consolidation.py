"""Tests for the v8.25.0 module consolidation."""

import pytest
import sys
from unittest.mock import Mock, patch
import warnings


class TestUnifiedConfig:
    """Test unified configuration module."""
    
    def test_import_from_unified_config(self):
        """Test that unified config imports work."""
        from research_system.config.settings import (
            Settings,
            QualityThresholds,
            quality_for_intent,
            PRIMARY_ORGS,
            PER_DOMAIN_HEADERS,
        )
        
        assert Settings is not None
        assert QualityThresholds is not None
        assert callable(quality_for_intent)
        assert isinstance(PRIMARY_ORGS, set)
        assert isinstance(PER_DOMAIN_HEADERS, dict)
    
    def test_intent_aware_thresholds(self):
        """Test that thresholds adapt based on intent."""
        from research_system.config.settings import quality_for_intent
        
        # Travel should have lower thresholds
        travel = quality_for_intent("travel", strict=True)
        assert travel.primary == 0.30
        assert travel.triangulation == 0.25
        assert travel.domain_cap == 0.35
        
        # Stats should have higher thresholds
        stats = quality_for_intent("stats", strict=True)
        assert stats.primary == 0.60
        assert stats.triangulation == 0.40
        assert stats.domain_cap == 0.30
    
    def test_per_domain_headers(self):
        """Test domain-specific headers configuration."""
        from research_system.config.settings import PER_DOMAIN_HEADERS
        
        # Mastercard should have browser headers
        assert "www.mastercard.com" in PER_DOMAIN_HEADERS
        mastercard = PER_DOMAIN_HEADERS["www.mastercard.com"]
        assert "Referer" in mastercard
        assert "Accept" in mastercard
        
        # OECD should have JSON headers
        assert "oecd.org" in PER_DOMAIN_HEADERS
        oecd = PER_DOMAIN_HEADERS["oecd.org"]
        assert "application/json" in oecd["Accept"]


class TestUnifiedCollection:
    """Test unified collection module."""
    
    def test_import_from_unified_collection(self):
        """Test that unified collection imports work."""
        from research_system.collection import (
            parallel_provider_search,
            collect_from_free_apis,
            _provider_policy,
        )
        
        assert callable(parallel_provider_search)
        assert callable(collect_from_free_apis)
        assert callable(_provider_policy)
    
    def test_legacy_forwarder_works(self):
        """Test that legacy imports still work with warnings."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # This should work but emit deprecation warning
            from research_system.collection_enhanced import collect_from_free_apis
            
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()


class TestUnifiedMetrics:
    """Test unified metrics module."""
    
    def test_run_metrics_model(self):
        """Test the unified RunMetrics model."""
        from research_system.metrics import RunMetrics
        
        metrics = RunMetrics(
            primary_share=0.45,
            triangulation=0.35,
            domain_concentration=0.20,
            total_cards=100,
            unique_domains=15
        )
        
        assert metrics.primary_share == 0.45
        assert metrics.triangulation == 0.35
        assert metrics.total_cards == 100
        
        # Test passes_gates method
        thresholds = {
            "primary": 0.40,
            "triangulation": 0.30,
            "domain_cap": 0.25
        }
        assert metrics.passes_gates(thresholds) == True
    
    def test_metrics_adapters(self):
        """Test adapters for legacy compatibility."""
        from research_system.metrics.adapters import (
            from_quality_metrics_v2,
            to_legacy_format
        )
        from research_system.metrics import RunMetrics
        
        # Create a mock legacy metrics object
        legacy = Mock()
        legacy.primary_share = 0.50
        legacy.triangulation_rate = 0.40
        legacy.domain_concentration = 0.30
        legacy.total_cards = 50
        
        # Convert to unified
        unified = from_quality_metrics_v2(legacy)
        assert isinstance(unified, RunMetrics)
        assert unified.primary_share == 0.50
        assert unified.triangulation == 0.40
        
        # Convert back to legacy format
        legacy_dict = to_legacy_format(unified)
        assert legacy_dict["primary_share_in_union"] == 0.50
        assert legacy_dict["union_triangulation"] == 0.40


class TestImportGuard:
    """Test import guard functionality."""
    
    def test_import_health_check(self):
        """Test that import health check works."""
        from research_system.guard import check_import_health
        
        health = check_import_health()
        assert isinstance(health, dict)
        assert "is_healthy" in health
        assert "warnings" in health
        assert isinstance(health["warnings"], list)
    
    def test_no_legacy_mix_detection(self):
        """Test that mixed imports are detected."""
        from research_system.guard import assert_no_legacy_mix
        
        # This should not raise (warnings only)
        assert_no_legacy_mix()


class TestEnhancedFeatures:
    """Test enhanced features from consolidation."""
    
    def test_primary_detection_uses_unified_config(self):
        """Test that primary detection uses unified PRIMARY_ORGS."""
        from research_system.quality.primary_detection import is_primary_source
        
        # Create mock card
        card = Mock()
        card.url = "https://www.oecd.org/report.pdf"
        card.title = "Economic Report"
        card.snippet = "GDP grew by 3.5% in 2024"
        card.text = "Economic growth accelerated to 3.5%"
        
        # OECD should be recognized as primary
        result = is_primary_source(card)
        assert result == True
    
    def test_contradiction_filter_uses_unified_config(self):
        """Test that contradiction filter uses unified trusted domains."""
        from research_system.triangulation.contradiction_filter import filter_contradictory_clusters
        
        # Create cluster with trusted domain
        cluster = {
            "cards": [
                Mock(source_domain="oecd.org", domain="oecd.org"),
                Mock(source_domain="imf.org", domain="imf.org"),
                Mock(source_domain="worldbank.org", domain="worldbank.org"),
            ]
        }
        
        # Should be preserved due to trusted domains
        filtered = filter_contradictory_clusters([cluster])
        assert len(filtered) == 1
    
    @patch('httpx.get')
    def test_fetch_uses_per_domain_headers(self, mock_get):
        """Test that fetch module uses per-domain headers."""
        from research_system.tools.fetch import _get_headers
        
        # Test Mastercard headers
        headers = _get_headers("https://www.mastercard.com/report.pdf")
        assert "Referer" in headers
        assert headers["Referer"] == "https://www.mastercard.com/newsroom/"
        
        # Test SEC headers
        headers = _get_headers("https://www.sec.gov/filing.txt")
        assert "User-Agent" in headers
        assert "research" in headers["User-Agent"].lower()


class TestOrchestratorIntegration:
    """Test that orchestrator uses unified modules correctly."""
    
    def test_orchestrator_imports_unified(self):
        """Test that orchestrator imports work with unified modules."""
        # This import should work without errors
        from research_system.orchestrator import Orchestrator, OrchestratorSettings
        
        assert Orchestrator is not None
        assert OrchestratorSettings is not None
    
    def test_orchestrator_calls_import_guard(self):
        """Test that orchestrator checks for mixed imports."""
        # The orchestrator has the guard import at the top
        # We can verify it's imported by checking the module
        import research_system.orchestrator
        import inspect
        source = inspect.getsource(research_system.orchestrator)
        
        # Check that assert_no_legacy_mix is imported and called
        assert "from research_system.guard import assert_no_legacy_mix" in source
        assert "assert_no_legacy_mix()" in source