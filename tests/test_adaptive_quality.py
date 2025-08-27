"""Test adaptive quality system functionality."""
import pytest
from pathlib import Path
import json
from research_system.quality_config.quality import (
    QualityConfig, TriangulationConfig, PrimaryShareConfig,
    DomainBalanceConfig, BackfillConfig, CredibilityConfig
)
from research_system.quality_config.report import ReportConfig, ReportTier, choose_report_tier
from research_system.strict.adaptive_guard import (
    ConfidenceLevel, SupplyContext, detect_supply_context,
    adaptive_strict_check, should_attempt_last_mile_backfill
)


class TestQualityConfig:
    """Test adaptive quality configuration."""
    
    def test_default_configuration(self):
        """Test default quality config values."""
        config = QualityConfig()
        
        assert config.triangulation.target_strict_pct == 0.35
        assert config.triangulation.target_normal_pct == 0.30
        assert config.triangulation.floor_pct_low_supply == 0.25
        assert config.primary_share.target_pct == 0.40
        assert config.domain_balance.cap_default == 0.25
    
    def test_triangulation_threshold_adaptation(self):
        """Test triangulation threshold adapts to conditions."""
        config = TriangulationConfig()
        
        # Normal conditions
        assert config.get_threshold(30, 10) == 0.30
        
        # Low supply conditions (few domains)
        assert config.get_threshold(20, 4) == 0.25
        
        # Very low cards
        assert config.get_threshold(5, 10) == 0.25
    
    def test_domain_balance_adaptation(self):
        """Test domain balance cap adapts to domain count."""
        config = DomainBalanceConfig()
        
        # Many domains - use default cap
        assert config.get_cap(10) == 0.25
        
        # Few domains - relax cap
        assert config.get_cap(4) == 0.40
    
    def test_load_save_config(self, tmp_path):
        """Test config persistence."""
        config = QualityConfig()
        config.triangulation.target_strict_pct = 0.40
        
        config_path = tmp_path / "quality.json"
        config.save(config_path)
        
        loaded = QualityConfig.load(config_path)
        assert loaded.triangulation.target_strict_pct == 0.40


class TestReportTierSelection:
    """Test adaptive report tier selection."""
    
    def test_selects_brief_for_low_confidence(self):
        """Test brief tier selected for low confidence."""
        config = ReportConfig()
        
        tier, confidence, max_tokens, explanation = choose_report_tier(
            triangulated_cards=5,
            credible_cards=15,
            primary_share=0.20,
            unique_domains=4,
            provider_error_rate=0.40,
            depth="standard",
            time_budget_remaining_sec=300,
            config=config
        )
        
        assert tier == ReportTier.BRIEF
        assert confidence < 0.55
        assert "low confidence" in explanation.lower()
    
    def test_selects_deep_for_high_quality(self):
        """Test deep tier selected for high quality evidence."""
        config = ReportConfig()
        
        tier, confidence, max_tokens, explanation = choose_report_tier(
            triangulated_cards=25,
            credible_cards=40,
            primary_share=0.60,
            unique_domains=12,
            provider_error_rate=0.05,
            depth="deep",
            time_budget_remaining_sec=1000,
            config=config
        )
        
        assert tier == ReportTier.DEEP
        assert confidence >= 0.75
        assert max_tokens <= 3800
    
    def test_respects_rapid_depth(self):
        """Test rapid depth forces brief tier."""
        config = ReportConfig()
        
        tier, confidence, max_tokens, explanation = choose_report_tier(
            triangulated_cards=20,
            credible_cards=30,
            primary_share=0.50,
            unique_domains=10,
            provider_error_rate=0.10,
            depth="rapid",
            time_budget_remaining_sec=500,
            config=config
        )
        
        assert tier == ReportTier.BRIEF
        assert "rapid depth" in explanation.lower()
    
    def test_time_budget_constrains_tokens(self):
        """Test time budget limits max tokens."""
        config = ReportConfig()
        
        tier, confidence, max_tokens, explanation = choose_report_tier(
            triangulated_cards=20,
            credible_cards=30,
            primary_share=0.50,
            unique_domains=10,
            provider_error_rate=0.10,
            depth="standard",
            time_budget_remaining_sec=10,  # Very little time
            config=config
        )
        
        # Should be constrained by time
        assert max_tokens < config.tiers[tier].max_tokens


class TestAdaptiveStrictGuard:
    """Test adaptive strict checking."""
    
    def test_detect_supply_context(self):
        """Test supply context detection."""
        metrics = {
            "cards": 15,
            "unique_domains": 4,
            "provider_error_rate": 0.35,
            "credible_cards": 12
        }
        
        context = detect_supply_context(metrics)
        assert context == SupplyContext.LOW_EVIDENCE
    
    def test_confidence_level_calculation(self):
        """Test confidence level determination."""
        metrics = {
            "union_triangulation": 0.20,
            "primary_share_in_union": 0.25,
            "unique_domains": 5,
            "credible_cards": 18
        }
        
        # Would normally fail strict but gets adjusted
        from research_system.strict.adaptive_guard import determine_confidence_level
        level = determine_confidence_level(metrics, SupplyContext.LOW_EVIDENCE)
        assert level == ConfidenceLevel.MODERATE
    
    def test_last_mile_backfill_logic(self):
        """Test last-mile backfill triggers correctly."""
        config = QualityConfig()
        
        metrics = {
            "union_triangulation": 0.32,  # Just below 35%
            "cards": 22
        }
        
        # Should trigger when close to threshold
        should_backfill = should_attempt_last_mile_backfill(
            metrics, config,
            time_remaining_pct=0.30,
            attempt_number=2
        )
        assert should_backfill
        
        # Should not trigger when far from threshold
        metrics["union_triangulation"] = 0.20
        should_backfill = should_attempt_last_mile_backfill(
            metrics, config,
            time_remaining_pct=0.30,
            attempt_number=2
        )
        assert not should_backfill
    
    def test_adaptive_strict_check_relaxation(self, tmp_path):
        """Test strict check relaxation under supply constraints."""
        # Create test metrics file
        metrics = {
            "union_triangulation": 0.28,  # Below 35% strict
            "primary_share_in_union": 0.35,
            "unique_domains": 5,
            "credible_cards": 20,
            "cards": 20
        }
        
        metrics_path = tmp_path / "metrics.json"
        metrics_path.write_text(json.dumps(metrics))
        
        # Create config
        config = QualityConfig()
        
        # Run adaptive check
        errs, confidence, adjustments = adaptive_strict_check(tmp_path, config)
        
        # Should have adjustments due to low supply
        assert "triangulation_threshold" in adjustments
        assert confidence in [ConfidenceLevel.MODERATE, ConfidenceLevel.LOW]


class TestIntegration:
    """Test integration of adaptive components."""
    
    def test_orchestrator_imports(self):
        """Test orchestrator can import adaptive modules."""
        # This tests that imports work without circular dependencies
        from research_system.orchestrator import Orchestrator
        from research_system.orchestrator_adaptive import (
            apply_adaptive_domain_balance,
            apply_adaptive_credibility_floor
        )
        
        # Should not raise ImportError
        assert Orchestrator is not None
        assert apply_adaptive_domain_balance is not None
    
    def test_adaptive_helpers_work(self):
        """Test adaptive helper functions."""
        from research_system.orchestrator_adaptive import compute_adaptive_metrics
        
        cards = []  # Empty for test
        metrics = compute_adaptive_metrics(cards, unique_domains=5)
        
        assert "adaptive_confidence" in metrics
        assert 0 <= metrics["adaptive_confidence"] <= 1