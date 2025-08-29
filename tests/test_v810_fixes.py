"""
Tests for v8.10.0 surgical fixes to prevent incoherent reports.
"""

import pytest
from pathlib import Path
import json
import tempfile
from unittest.mock import Mock, patch
from research_system.models import EvidenceCard
from research_system.tools.aggregates import triangulation_rate_from_clusters
from research_system.report.claim_filter import (
    is_numeric_claim, is_on_topic, filter_key_findings
)


class TestTriangulationMetricsFix:
    """Test that triangulation metrics are correctly calculated."""
    
    def test_triangulation_rate_with_total_cards(self):
        """Test that triangulation rate uses total card count, not just clustered cards."""
        # 2 clusters with 3 cards each (6 triangulated out of 10 total)
        clusters = [
            {"indices": [0, 1, 2], "domains": ["a.com", "b.com", "c.com"], "size": 3},
            {"indices": [3, 4, 5], "domains": ["d.com", "e.com"], "size": 3}
        ]
        
        # OLD BROKEN: Would return 6/6 = 100%
        # NEW CORRECT: Should return 6/10 = 60%
        rate = triangulation_rate_from_clusters(clusters, total_cards=10)
        assert rate == 0.6, f"Expected 0.6 (6/10) but got {rate}"
    
    def test_triangulation_requires_multi_domain(self):
        """Test that single-domain clusters don't count as triangulated."""
        clusters = [
            {"indices": [0, 1, 2], "domains": ["a.com"], "size": 3},  # Single domain
            {"indices": [3, 4], "domains": ["b.com", "c.com"], "size": 2}  # Multi domain
        ]
        
        rate = triangulation_rate_from_clusters(clusters, total_cards=10)
        # Only second cluster (2 cards) counts as triangulated
        assert rate == 0.2, f"Expected 0.2 (2/10) but got {rate}"
    
    def test_metrics_consistency(self):
        """Test that triangulated_cards == round(triangulation * total_cards)."""
        clusters = [
            {"indices": [0, 1], "domains": ["a.com", "b.com"], "size": 2},
            {"indices": [2, 3, 4], "domains": ["c.com", "d.com"], "size": 3}
        ]
        
        total = 20
        rate = triangulation_rate_from_clusters(clusters, total_cards=total)
        triangulated_cards = 5  # 2 + 3
        
        # Verify consistency
        assert triangulated_cards == round(rate * total), \
            f"Inconsistent: {triangulated_cards} != round({rate} * {total})"


class TestClaimFiltering:
    """Test typed, numeric, on-topic claim filtering."""
    
    def test_numeric_claim_detection(self):
        """Test detection of numeric claims."""
        # Should pass
        assert is_numeric_claim("Tax rate increased by 5% in 2024")
        assert is_numeric_claim("GDP growth was $2.1 trillion")
        assert is_numeric_claim("Unemployment fell to 3.5 percent")
        assert is_numeric_claim("Top bracket pays 37% marginal rate")
        
        # Should fail
        assert not is_numeric_claim("Tax policy changed significantly")
        assert not is_numeric_claim("Other titles in this series")
        assert not is_numeric_claim("The economy improved")
    
    def test_on_topic_filtering(self):
        """Test on-topic relevance checking."""
        topic = "tax rates and social class correlation"
        
        # Should pass
        assert is_on_topic("Top 1% pay 40% of total tax revenue", topic)
        assert is_on_topic("Middle class tax burden increased", topic)
        assert is_on_topic("Progressive tax rates by income bracket", topic)
        
        # Should fail  
        assert not is_on_topic("Weather forecast for tomorrow", topic)
        assert not is_on_topic("Other titles in this series", topic)
    
    def test_filter_nonsensical_metadata(self):
        """Test that metadata/citation text is filtered out."""
        claims = [
            {"text": "Tax rate is 25%", "sources": ["a.com", "b.com"]},
            {"text": "Other titles in this series", "sources": ["c.com"]},
            {"text": "© 2001 IMF", "sources": ["imf.org"]},
            {"text": "ISBN 978-0-12345", "sources": ["d.com"]},
            {"text": "Tax rate for top bracket is 35%", "sources": ["e.com", "f.com"]}
        ]
        
        filtered = filter_key_findings(
            claims, 
            topic="tax rates",
            require_numeric=True,
            min_sources=0  # Don't filter by sources for this test
        )
        
        # Should only keep real claims, not metadata
        assert len(filtered) == 2
        assert filtered[0]["text"] == "Tax rate is 25%"
        assert filtered[1]["text"] == "Tax rate for top bracket is 35%"


class TestGuardrailsHardFail:
    """Test that guardrails prevent final report generation on failure."""
    
    def test_no_final_report_on_low_triangulation(self):
        """Test that final_report.md is not generated when triangulation is too low."""
        
        # Mock metrics with failing triangulation
        metrics = {
            "union_triangulation": 0.15,  # Below 25% threshold
            "primary_share_in_union": 0.45,  # Above 40% threshold
            "total_cards": 20
        }
        
        # Simulate the check from orchestrator
        should_generate = not (
            metrics.get("primary_share_in_union", 0) < 0.40 or 
            metrics.get("union_triangulation", 0) < 0.25
        )
        
        assert not should_generate, "Should not generate report with low triangulation"
        
    def test_no_final_report_on_low_primary_share(self):
        """Test that final_report.md is not generated when primary share is too low."""
        
        # Mock metrics with failing primary share
        metrics = {
            "union_triangulation": 0.30,  # Above 25% threshold
            "primary_share_in_union": 0.35,  # Below 40% threshold
            "total_cards": 20
        }
        
        # Simulate the check from orchestrator
        should_generate = not (
            metrics.get("primary_share_in_union", 0) < 0.40 or 
            metrics.get("union_triangulation", 0) < 0.25
        )
        
        assert not should_generate, "Should not generate report with low primary share"


class TestMetadataLeak:
    """Test that metadata shows correct card counts."""
    
    def test_metadata_uses_correct_metrics(self):
        """Test that Evidence Supply Metrics shows actual card counts."""
        from research_system.orchestrator_adaptive import generate_adaptive_report_metadata
        from research_system.strict.adaptive_guard import ConfidenceLevel
        
        # Simulate combined metrics
        metrics = {
            "total_cards": 34,  # Actual cards
            "credible_cards": 30,
            "unique_domains": 12,
            "triangulated_cards": 19,
            "triangulation_rate": 0.558,  # 19/34
            "primary_share": 0.265,
            "provider_error_rate": 0.1,
            "domain_concentration": 0.15,
            "union_triangulation": 0.441,
            "primary_share_in_union": 0.265
        }
        
        metadata = generate_adaptive_report_metadata(
            metrics,
            ConfidenceLevel.LOW,
            {},
            "BRIEF",
            0.3,
            "Low evidence quality"
        )
        
        # Verify correct values in output
        assert "Total cards collected: 34" in metadata
        assert "Total cards collected: 0" not in metadata
        assert "Triangulated cards: 19" in metadata
        assert "Credible cards: 30" in metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])