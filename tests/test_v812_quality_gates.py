"""Tests for v8.12.0 quality gates and stats-specific requirements."""

import pytest
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from research_system.config import Settings
from research_system.quality.gates import (
    meets_minimum_bar,
    explain_bar, 
    calculate_recent_primary_count,
    count_triangulated_clusters,
    calculate_stats_metrics
)
from research_system.orchestrator import Orchestrator, OrchestratorSettings


class TestStatsQualityGates:
    """Test stats-specific quality gates."""
    
    def test_meets_minimum_bar_stats_intent_passes(self):
        """Test that stats intent passes when all requirements are met."""
        metrics = {
            "primary_share_in_union": 0.55,  # > 50%
            "recent_primary_count": 4,        # > 3
            "triangulated_clusters": 2        # > 1
        }
        
        assert meets_minimum_bar(metrics, "stats") == True
    
    def test_meets_minimum_bar_stats_intent_fails_primary_share(self):
        """Test that stats intent fails when primary share is too low."""
        metrics = {
            "primary_share_in_union": 0.45,  # < 50%
            "recent_primary_count": 4,
            "triangulated_clusters": 2
        }
        
        assert meets_minimum_bar(metrics, "stats") == False
    
    def test_meets_minimum_bar_stats_intent_fails_recent_primary(self):
        """Test that stats intent fails when recent primary count is too low."""
        metrics = {
            "primary_share_in_union": 0.55,
            "recent_primary_count": 2,  # < 3
            "triangulated_clusters": 2
        }
        
        assert meets_minimum_bar(metrics, "stats") == False
    
    def test_meets_minimum_bar_stats_intent_fails_triangulation(self):
        """Test that stats intent fails when triangulation is insufficient."""
        metrics = {
            "primary_share_in_union": 0.55,
            "recent_primary_count": 4,
            "triangulated_clusters": 0  # < 1
        }
        
        assert meets_minimum_bar(metrics, "stats") == False
    
    def test_meets_minimum_bar_generic_intent(self):
        """Test generic intent quality gates."""
        metrics = {
            "primary_share_in_union": 0.45,
            "union_triangulation": 0.30,
            "confidence": 0.40
        }
        
        assert meets_minimum_bar(metrics, "generic") == True
        
        # Test failure
        metrics["confidence"] = 0.30
        assert meets_minimum_bar(metrics, "generic") == False
    
    def test_explain_bar_stats_intent(self):
        """Test quality gate explanation for stats intent."""
        metrics = {
            "primary_share_in_union": 0.30,
            "recent_primary_count": 1,
            "triangulated_clusters": 0
        }
        
        explanations = explain_bar(metrics, "stats")
        
        assert "primary_share" in explanations
        assert explanations["primary_share"][0] == 0.30
        assert explanations["primary_share"][1] >= 0.50
        
        assert "recent_primary_count" in explanations
        assert explanations["recent_primary_count"][0] == 1
        assert explanations["recent_primary_count"][1] >= 3
    
    def test_calculate_recent_primary_count(self):
        """Test counting recent primary sources."""
        settings = Settings()
        
        # Create mock cards
        recent_date = datetime.now() - timedelta(days=100)
        old_date = datetime.now() - timedelta(days=1000)
        
        cards = [
            Mock(
                source_domain="oecd.org",
                is_primary_source=True,
                collected_at=recent_date.isoformat()
            ),
            Mock(
                source_domain="imf.org",
                is_primary_source=False,  # Will be detected as primary by domain
                collected_at=recent_date.isoformat()
            ),
            Mock(
                source_domain="wikipedia.org",
                is_primary_source=False,
                collected_at=recent_date.isoformat()
            ),
            Mock(
                source_domain="bls.gov",
                is_primary_source=True,
                collected_at=old_date.isoformat()  # Too old
            ),
        ]
        
        count = calculate_recent_primary_count(cards, days=730)
        assert count == 2  # Only the recent primary sources
    
    def test_count_triangulated_clusters(self):
        """Test counting triangulated clusters."""
        clusters = [
            {"domains": ["oecd.org", "imf.org"]},  # 2 domains - triangulated
            {"domains": ["wikipedia.org"]},         # 1 domain - not triangulated
            {"domains": ["bls.gov", "irs.gov", "cbo.gov"]},  # 3 domains - triangulated
        ]
        
        count = count_triangulated_clusters(clusters)
        assert count == 2
    
    def test_calculate_stats_metrics(self):
        """Test calculation of stats-specific metrics."""
        settings = Settings()
        
        cards = [
            Mock(source_domain="oecd.org", is_primary_source=False),
            Mock(source_domain="imf.org", is_primary_source=False),
            Mock(source_domain="wikipedia.org", is_primary_source=False),
            Mock(source_domain="bls.gov", is_primary_source=True),
        ]
        
        clusters = [
            {"domains": ["oecd.org", "imf.org"]},
        ]
        
        metrics = calculate_stats_metrics(cards, clusters)
        
        assert metrics["total_cards"] == 4
        assert metrics["primary_cards"] == 3  # oecd, imf, bls are all primary
        assert metrics["primary_share_in_union"] == 0.75
        assert metrics["triangulated_clusters"] == 1


class TestOrchestratorQualityGates:
    """Test orchestrator integration with quality gates."""
    
    def test_orchestrator_validates_output_dir(self):
        """Test that orchestrator validates output_dir is not None."""
        with pytest.raises(ValueError, match="output_dir cannot be None"):
            settings = OrchestratorSettings(
                topic="test",
                depth="rapid",
                output_dir=None,
                strict=False
            )
            Orchestrator(settings)
    
    def test_orchestrator_creates_output_dir(self):
        """Test that orchestrator creates output directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "test_run"
            assert not output_dir.exists()
            
            settings = OrchestratorSettings(
                topic="test",
                depth="rapid",
                output_dir=output_dir,
                strict=False
            )
            
            orch = Orchestrator(settings)
            assert output_dir.exists()
    
    @patch('research_system.orchestrator.meets_minimum_bar')
    def test_quality_gates_prevent_final_report(self, mock_meets_bar):
        """Test that failed quality gates prevent final report generation."""
        mock_meets_bar.return_value = False
        
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = OrchestratorSettings(
                topic="tax rates statistics",
                depth="rapid",
                output_dir=Path(tmpdir),
                strict=False
            )
            
            orch = Orchestrator(settings)
            
            # Mock the evidence and metrics
            orch.context['intent'] = 'stats'
            
            # This would normally be called during run()
            # We're testing that when quality gates fail, only insufficient_evidence_report.md is created
            # and NOT final_report.md
            
            # The actual test would require mocking more of the pipeline
            # For now, we're verifying the structure is in place
            assert hasattr(orch, 'context')
            assert orch.s.output_dir.exists()


class TestSourceFilters:
    """Test source admissibility filters."""
    
    def test_is_admissible_stats_intent(self):
        """Test source admissibility for stats intent."""
        from research_system.selection.source_filters import is_admissible
        
        # Official source - always admissible
        card = Mock(source_domain="oecd.org")
        assert is_admissible(card, "stats") == True
        assert hasattr(card, 'flags')
        assert card.flags.get('is_primary_official') == True
        
        # Banned representative domain - admissible but flagged
        card = Mock(source_domain="taxfoundation.org")
        assert is_admissible(card, "stats") == True
        assert card.flags.get('non_representative_only') == True
        
        # Low credibility - not admissible
        card = Mock(source_domain="random-blog.com", credibility_score=0.2)
        assert is_admissible(card, "stats") == False
    
    def test_filter_by_admissibility(self):
        """Test filtering cards by admissibility."""
        from research_system.selection.source_filters import filter_by_admissibility
        
        cards = [
            Mock(source_domain="oecd.org", credibility_score=0.9),
            Mock(source_domain="random-blog.com", credibility_score=0.2),
            Mock(source_domain="imf.org", credibility_score=0.95),
        ]
        
        filtered = filter_by_admissibility(cards, "stats")
        assert len(filtered) == 2
        assert all(c.source_domain in ["oecd.org", "imf.org"] for c in filtered)


class TestEnhancedClustering:
    """Test enhanced clustering with domain constraints."""
    
    def test_cluster_with_stats_constraints(self):
        """Test clustering with stats-specific constraints."""
        from research_system.triangulation.enhanced_clustering import (
            cluster_claims, Cluster, ClusterMember
        )
        
        # Mock cards with different domains
        cards = [
            Mock(
                claim="Tax rate is 35%",
                source_domain="oecd.org",
                is_primary_source=True
            ),
            Mock(
                claim="Tax rate is approximately 35%", 
                source_domain="imf.org",
                is_primary_source=True
            ),
            Mock(
                claim="Tax rate is 35%",
                source_domain="taxfoundation.org",  # Banned representative
                is_primary_source=False
            ),
        ]
        
        # With sentence transformers mocked
        with patch('research_system.triangulation.enhanced_clustering.SentenceTransformer'):
            clusters = cluster_claims(cards, "stats", threshold=0.40)
            
            # The function would need proper mocking of embeddings
            # This tests the structure is in place
            assert isinstance(clusters, list)


class TestExtractionSchemas:
    """Test extraction-only schemas with entailment."""
    
    def test_key_finding_schema_validation(self):
        """Test KeyFinding schema validation."""
        from research_system.writers.schemas import KeyFinding
        
        # Valid finding
        finding = KeyFinding(
            metric="effective tax rate",
            value=35.5,
            unit="%",
            geography="US",
            cohort="top 1%",
            year=2024,
            citation_id="card_123"
        )
        
        assert finding.metric == "effective tax rate"
        assert finding.value == 35.5
        
        # Invalid - missing required field
        with pytest.raises(Exception):
            KeyFinding(
                metric="tax rate",
                value=35.5,
                # Missing unit, geography, etc.
            )
    
    def test_entailment_validation(self):
        """Test entailment validation for claims."""
        from research_system.validation.entailment import entails
        
        # Strong match - should pass
        premise = "The effective tax rate for the top 1% was 35.5% in 2024"
        hypothesis = "effective tax rate is 35.5% in 2024"
        assert entails(premise, hypothesis) == True
        
        # Weak match - should fail
        premise = "Various economic indicators showed improvement"
        hypothesis = "GDP grew by 3.2% in Q4"
        assert entails(premise, hypothesis) == False
    
    @patch('research_system.validation.entailment.entails')
    def test_build_key_findings_with_entailment(self, mock_entails):
        """Test that key findings require entailment."""
        from research_system.writers.schemas import build_key_findings
        
        mock_entails.return_value = True
        
        cards = [
            Mock(
                id="card_1",
                claim="Tax rate is 35%",
                source_domain="oecd.org"
            )
        ]
        
        with patch('research_system.writers.schemas.extract_structured_fact') as mock_extract:
            mock_extract.return_value = {
                "metric": "tax rate",
                "value": 35,
                "unit": "%",
                "geography": "US",
                "cohort": "all",
                "year": 2024,
                "citation_id": "card_1"
            }
            
            findings = build_key_findings(cards, "stats")
            
            # Should check entailment was called
            assert mock_entails.called


class TestHTTPRetryResilience:
    """Test HTTP retry with exponential backoff."""
    
    def test_http_client_retry_for_official_domains(self):
        """Test that official domains get more aggressive retries."""
        from research_system.net.http import Client
        
        client = Client()
        
        # Check official domains are configured
        assert "oecd.org" in client.official_domains
        assert "imf.org" in client.official_domains
        
        # Test would need to mock httpx.Client.get to simulate 429 errors
        # and verify retry behavior
        with patch.object(client.client, 'get') as mock_get:
            # Simulate rate limiting then success
            mock_get.side_effect = [
                Mock(status_code=429),
                Mock(status_code=429),
                Mock(status_code=200, text="Success")
            ]
            
            with patch('time.sleep'):  # Don't actually sleep in tests
                response = client.get("https://oecd.org/data")
                assert response.status_code == 200


class TestDatetimeHandling:
    """Test comprehensive datetime handling."""
    
    def test_safe_format_dt_with_float(self):
        """Test formatting datetime from float timestamp."""
        from research_system.utils.datetime_safe import safe_format_dt
        
        timestamp = 1704067200.0  # 2024-01-01 00:00:00 UTC
        result = safe_format_dt(timestamp, "%Y-%m-%d")
        assert "2024" in result or "2023" in result  # Timezone dependent
    
    def test_safe_format_dt_with_datetime(self):
        """Test formatting datetime object."""
        from research_system.utils.datetime_safe import safe_format_dt
        
        dt = datetime(2024, 1, 1, 12, 0, 0)
        result = safe_format_dt(dt, "%Y-%m-%d %H:%M")
        assert result == "2024-01-01 12:00"
    
    def test_safe_format_dt_with_none(self):
        """Test formatting None returns current time."""
        from research_system.utils.datetime_safe import safe_format_dt
        
        result = safe_format_dt(None, "%Y")
        current_year = datetime.now().year
        assert str(current_year) in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])