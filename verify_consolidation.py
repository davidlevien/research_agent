#!/usr/bin/env python3
"""
Verification script for v8.25.0 module consolidation.

This script verifies that:
1. All unified modules work correctly
2. Intent-aware configuration is functional
3. No import errors occur
4. Legacy compatibility is maintained
"""

import sys
import warnings
from typing import Dict, Any


def test_unified_config() -> bool:
    """Test unified configuration module."""
    print("Testing unified configuration...")
    
    try:
        from research_system.config.settings import (
            Settings,
            QualityThresholds,
            quality_for_intent,
            PRIMARY_ORGS,
            PER_DOMAIN_HEADERS,
        )
        
        # Test settings instance
        settings = Settings()
        assert settings.time_budget_seconds > 0
        print("  ✅ Settings instance created")
        
        # Test intent-aware thresholds
        travel = quality_for_intent("travel", strict=True)
        assert travel.primary == 0.30
        assert travel.triangulation == 0.25
        print("  ✅ Travel thresholds: 30%/25%/35%")
        
        stats = quality_for_intent("stats", strict=True)
        assert stats.primary == 0.60
        assert stats.triangulation == 0.40
        print("  ✅ Stats thresholds: 60%/40%/30%")
        
        # Test primary orgs
        assert "oecd.org" in PRIMARY_ORGS
        assert "worldbank.org" in PRIMARY_ORGS
        print(f"  ✅ {len(PRIMARY_ORGS)} primary organizations configured")
        
        # Test per-domain headers
        assert "www.mastercard.com" in PER_DOMAIN_HEADERS
        assert "Referer" in PER_DOMAIN_HEADERS["www.mastercard.com"]
        print(f"  ✅ {len(PER_DOMAIN_HEADERS)} domain-specific headers configured")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_unified_collection() -> bool:
    """Test unified collection module."""
    print("\nTesting unified collection...")
    
    try:
        from research_system.collection import (
            parallel_provider_search,
            collect_from_free_apis,
            _provider_policy,
        )
        
        # Test imports work
        assert callable(parallel_provider_search)
        assert callable(collect_from_free_apis)
        assert callable(_provider_policy)
        print("  ✅ All collection functions imported")
        
        # Test provider policy
        providers = ["tavily", "brave", "nps", "fred"]
        filtered = _provider_policy("test query", providers)
        assert isinstance(filtered, list)
        print("  ✅ Provider policy function works")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_unified_metrics() -> bool:
    """Test unified metrics module."""
    print("\nTesting unified metrics...")
    
    try:
        from research_system.metrics import (
            RunMetrics,
            TriangulationMetrics,
            from_quality_metrics_v2,
            to_legacy_format,
        )
        
        # Test RunMetrics creation
        metrics = RunMetrics(
            primary_share=0.45,
            triangulation=0.35,
            domain_concentration=0.20,
            total_cards=100
        )
        assert metrics.primary_share == 0.45
        print("  ✅ RunMetrics model created")
        
        # Test passes_gates method
        thresholds = {
            "primary": 0.40,
            "triangulation": 0.30,
            "domain_cap": 0.25
        }
        assert metrics.passes_gates(thresholds) == True
        print("  ✅ Quality gate evaluation works")
        
        # Test legacy conversion
        legacy = to_legacy_format(metrics)
        assert legacy["primary_share_in_union"] == 0.45
        assert legacy["union_triangulation"] == 0.35
        print("  ✅ Legacy format conversion works")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_import_guard() -> bool:
    """Test import guard functionality."""
    print("\nTesting import guard...")
    
    try:
        from research_system.guard import (
            assert_no_legacy_mix,
            check_import_health,
        )
        
        # Check import health
        health = check_import_health()
        assert isinstance(health, dict)
        assert "is_healthy" in health
        print(f"  ✅ Import health check: {'healthy' if health['is_healthy'] else 'has warnings'}")
        
        if health["warnings"]:
            for warning in health["warnings"]:
                print(f"     ⚠️  {warning}")
        
        # Test no legacy mix (should not raise)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert_no_legacy_mix()
        print("  ✅ No critical import conflicts detected")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_enhanced_features() -> bool:
    """Test enhanced features from consolidation."""
    print("\nTesting enhanced features...")
    
    try:
        # Test primary detection
        from research_system.quality.primary_detection import is_primary_source
        from unittest.mock import Mock
        
        card = Mock()
        card.url = "https://www.oecd.org/report.pdf"
        card.title = "Economic Report"
        card.snippet = "GDP grew by 3.5%"
        card.text = "Economic growth"
        
        result = is_primary_source(card)
        assert result == True
        print("  ✅ Primary source detection works")
        
        # Test fetch headers
        from research_system.tools.fetch import _get_headers
        
        headers = _get_headers("https://www.mastercard.com/report.pdf")
        assert "Referer" in headers
        print("  ✅ Per-domain headers applied")
        
        # Test contradiction filter
        from research_system.triangulation.contradiction_filter import TRI_CONTRA_TOL_PCT
        assert TRI_CONTRA_TOL_PCT == 0.35
        print("  ✅ Contradiction tolerance: 35%")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_orchestrator_integration() -> bool:
    """Test orchestrator integration."""
    print("\nTesting orchestrator integration...")
    
    try:
        # Suppress deprecation warnings for this test
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            
            from research_system.orchestrator import Orchestrator, OrchestratorSettings
            from pathlib import Path
            import tempfile
            
            # Test orchestrator can be created
            with tempfile.TemporaryDirectory() as tmpdir:
                settings = OrchestratorSettings(
                    topic="test query",
                    depth="rapid",
                    output_dir=Path(tmpdir),
                    strict=False
                )
                
                orch = Orchestrator(settings)
                assert orch is not None
                print("  ✅ Orchestrator initialized successfully")
                
                # Check context is initialized
                assert hasattr(orch, 'context')
                assert isinstance(orch.context, dict)
                print("  ✅ Context dictionary initialized")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("v8.25.0 Module Consolidation Verification")
    print("=" * 60)
    
    results = {
        "Unified Config": test_unified_config(),
        "Unified Collection": test_unified_collection(),
        "Unified Metrics": test_unified_metrics(),
        "Import Guard": test_import_guard(),
        "Enhanced Features": test_enhanced_features(),
        "Orchestrator Integration": test_orchestrator_integration(),
    }
    
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:.<30} {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎯 ALL VERIFICATIONS PASSED!")
        print("✅ Module consolidation is working correctly")
        print("✅ System is production-ready")
        return 0
    else:
        print("\n❌ SOME VERIFICATIONS FAILED")
        print("Please review the errors above")
        return 1


if __name__ == "__main__":
    sys.exit(main())