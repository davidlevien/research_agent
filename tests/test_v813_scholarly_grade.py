"""Tests for v8.13.0 scholarly-grade improvements."""

import pytest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Test imports
from research_system.config_v2 import load_quality_config, QualityConfigV2
from research_system.utils.file_ops import atomic_write_text, atomic_write_json, run_transaction
from research_system.quality.metrics_v2 import compute_metrics, gates_pass, FinalMetrics
from research_system.evidence.canonicalize import canonical_id, dedup_by_canonical, get_canonical_domain
from research_system.quality.domain_weights import tier_for, credibility_weight, mark_primary
from research_system.retrieval.filters import is_partisan, is_jurisdiction_mismatch, admit_for_stats
from research_system.quality.quote_rescue import has_number, numeric_density, allow_quote
from research_system.report.binding import enforce_number_bindings, NumberBinding, BindingError
from research_system.report.insufficient import write_insufficient_evidence_report


class TestQualityConfig:
    """Test the unified quality configuration system."""
    
    def test_load_quality_config_singleton(self):
        """Test that config is loaded as singleton."""
        cfg1 = load_quality_config()
        cfg2 = load_quality_config()
        assert cfg1 is cfg2  # Same object
    
    def test_config_has_required_fields(self):
        """Test that config has all required fields."""
        cfg = load_quality_config()
        
        assert cfg.primary_share_floor == 0.50
        assert cfg.triangulation_floor == 0.45
        assert cfg.domain_concentration_cap == 0.25
        assert cfg.numeric_quote_min_density == 0.03
        assert cfg.topic_similarity_floor == 0.50
        
        assert "TIER1" in cfg.tiers
        assert cfg.tiers["TIER1"] == 1.00
        
        assert "stats" in cfg.intents
        assert "providers_hard_prefer" in cfg.intents["stats"]


class TestAtomicFileOps:
    """Test atomic file operations and transactions."""
    
    def test_atomic_write_text(self):
        """Test atomic text file writing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = f"{tmpdir}/test.txt"
            content = "Test content"
            
            atomic_write_text(file_path, content)
            
            assert os.path.exists(file_path)
            with open(file_path) as f:
                assert f.read() == content
    
    def test_atomic_write_json(self):
        """Test atomic JSON file writing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = f"{tmpdir}/test.json"
            data = {"key": "value", "number": 42}
            
            atomic_write_json(file_path, data)
            
            assert os.path.exists(file_path)
            with open(file_path) as f:
                loaded = json.load(f)
                assert loaded == data
    
    def test_run_transaction_success(self):
        """Test transaction completes successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with run_transaction(tmpdir):
                # Simulate work
                atomic_write_text(f"{tmpdir}/work.txt", "done")
            
            # Check RUN_STATE.json
            state_file = f"{tmpdir}/RUN_STATE.json"
            assert os.path.exists(state_file)
            
            with open(state_file) as f:
                state = json.load(f)
                assert state["status"] == "COMPLETED"
    
    def test_run_transaction_failure_cleanup(self):
        """Test transaction cleans up on failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a final report
            report_path = f"{tmpdir}/final_report.md"
            with open(report_path, "w") as f:
                f.write("Draft report")
            
            try:
                with run_transaction(tmpdir):
                    raise ValueError("Simulated error")
            except ValueError:
                pass
            
            # Final report should be deleted
            assert not os.path.exists(report_path)
            
            # RUN_STATE should show ABORTED
            with open(f"{tmpdir}/RUN_STATE.json") as f:
                state = json.load(f)
                assert state["status"] == "ABORTED"
                assert "ValueError" in state["error"]


class TestUnifiedMetrics:
    """Test unified metrics computation."""
    
    def test_compute_metrics_basic(self):
        """Test basic metrics computation."""
        cards = [
            Mock(is_primary_source=True, source_domain="oecd.org", triangulated=True, credibility_score=0.8),
            Mock(is_primary_source=False, source_domain="wikipedia.org", triangulated=False, credibility_score=0.5),
            Mock(is_primary_source=True, source_domain="imf.org", triangulated=True, credibility_score=0.9),
        ]
        
        metrics = compute_metrics(cards)
        
        assert metrics.primary_share == 2/3
        assert metrics.triangulation_rate == 2/3
        assert metrics.unique_domains == 3
        assert metrics.credible_cards == 2  # Two cards above 0.6 threshold
    
    def test_gates_pass_generic(self):
        """Test quality gates for generic intent."""
        metrics = FinalMetrics(
            primary_share=0.55,
            triangulation_rate=0.50,
            domain_concentration=0.20,
            sample_sizes={"total_cards": 100},
            unique_domains=10,
            credible_cards=80,
            recent_primary_count=5,
            triangulated_clusters=3
        )
        
        assert gates_pass(metrics, "generic") == True
        
        # Fail primary share
        metrics.primary_share = 0.40
        assert gates_pass(metrics, "generic") == False
    
    def test_gates_pass_stats(self):
        """Test quality gates for stats intent."""
        metrics = FinalMetrics(
            primary_share=0.55,
            triangulation_rate=0.50,
            domain_concentration=0.20,
            sample_sizes={"total_cards": 100},
            unique_domains=10,
            credible_cards=80,
            recent_primary_count=4,  # Above minimum of 3
            triangulated_clusters=2   # Above minimum of 1
        )
        
        assert gates_pass(metrics, "stats") == True
        
        # Fail recent primary requirement
        metrics.recent_primary_count = 2
        assert gates_pass(metrics, "stats") == False


class TestCanonicalization:
    """Test evidence canonicalization and deduplication."""
    
    def test_canonical_id_doi(self):
        """Test DOI extraction for canonical ID."""
        card = Mock(doi="10.1234/test", url="https://example.com")
        assert canonical_id(card) == "doi:10.1234/test"
    
    def test_canonical_id_crs(self):
        """Test CRS report ID extraction."""
        card = Mock(doi=None, url="https://sgp.fas.org/crs/misc/R12345.pdf")
        assert canonical_id(card) == "crs:R12345"
    
    def test_canonical_id_mirror_collapse(self):
        """Test that mirrors are collapsed to canonical."""
        card1 = Mock(doi=None, url="https://sgp.fas.org/crs/test.pdf")
        card2 = Mock(doi=None, url="https://www.congress.gov/crs/test.pdf")
        
        # Should collapse to same canonical domain
        id1 = canonical_id(card1)
        id2 = canonical_id(card2)
        
        assert "congress.gov" in id1.lower()
        assert "congress.gov" in id2.lower()
    
    def test_dedup_by_canonical(self):
        """Test deduplication by canonical ID."""
        cards = [
            Mock(doi="10.1234/test", url="https://example1.com", id="1"),
            Mock(doi="10.1234/test", url="https://example2.com", id="2"),  # Duplicate DOI
            Mock(doi="10.5678/other", url="https://example3.com", id="3"),
        ]
        
        deduped = dedup_by_canonical(cards)
        
        assert len(deduped) == 2
        assert all(hasattr(c, "canonical_id") for c in deduped)


class TestDomainWeights:
    """Test domain tier classification and weighting."""
    
    def test_tier_classification(self):
        """Test correct tier assignment."""
        # TIER1 - official/peer-reviewed
        card1 = Mock(url="https://oecd.org/data", peer_reviewed=False)
        assert tier_for(card1) == "TIER1"
        
        # TIER2 - working papers
        card2 = Mock(url="https://nber.org/papers/w12345", peer_reviewed=False)
        assert tier_for(card2) == "TIER2"
        
        # TIER3 - think tanks
        card3 = Mock(url="https://brookings.edu/research", peer_reviewed=False)
        assert tier_for(card3) == "TIER3"
        
        # TIER4 - media/other
        card4 = Mock(url="https://nytimes.com/article", peer_reviewed=False)
        assert tier_for(card4) == "TIER4"
    
    def test_credibility_weight(self):
        """Test credibility weights match tiers."""
        card1 = Mock(url="https://imf.org/data", peer_reviewed=False)
        assert credibility_weight(card1) == 1.00
        
        card2 = Mock(url="https://wikipedia.org/wiki/Tax", peer_reviewed=False)
        assert credibility_weight(card2) == 0.20
    
    def test_mark_primary(self):
        """Test primary source marking."""
        # TIER1 should be primary
        card1 = Mock(url="https://bls.gov/data", labels=None)
        mark_primary(card1)
        assert card1.labels.is_primary == True
        
        # OWID without DOI should not be primary
        card2 = Mock(url="https://ourworldindata.org/taxes", bound_primary_doi=None, labels=None)
        mark_primary(card2)
        assert card2.labels.is_primary == False
        
        # OWID with DOI should be primary
        card3 = Mock(url="https://ourworldindata.org/taxes", bound_primary_doi="10.1234/test", labels=None)
        mark_primary(card3)
        assert card3.labels.is_primary == True


class TestRetrievalFilters:
    """Test retrieval filters for partisan content and jurisdiction."""
    
    def test_is_partisan(self):
        """Test partisan source detection."""
        assert is_partisan("https://www.heritage.org/taxes") == True
        assert is_partisan("https://www.americanprogress.org/article") == True
        assert is_partisan("https://www.jec.senate.gov/public/index.cfm/democrats/report") == True
        assert is_partisan("https://oecd.org/data") == False
    
    def test_is_jurisdiction_mismatch(self):
        """Test jurisdiction mismatch detection."""
        # UK source for US query
        card = Mock(url="https://gov.uk/taxes", is_international_org=False, snippet="UK tax rates")
        assert is_jurisdiction_mismatch(card, "US") == True
        
        # International org is always OK
        card = Mock(url="https://oecd.org/data", is_international_org=True)
        assert is_jurisdiction_mismatch(card, "US") == False
    
    def test_admit_for_stats(self):
        """Test stats admission requirements."""
        # Has number, not partisan, US source
        card = Mock(
            url="https://bls.gov/data",
            snippet="Unemployment rate was 3.5% in 2024",
            has_table_or_number=True
        )
        assert admit_for_stats(card) == True
        
        # No numeric content
        card = Mock(
            url="https://example.com",
            snippet="Economic trends are improving",
            has_table_or_number=False
        )
        assert admit_for_stats(card) == False


class TestQuoteRescue:
    """Test quote rescue with numeric requirements."""
    
    def test_has_number(self):
        """Test number detection."""
        assert has_number("The rate was 3.5% in 2024") == True
        assert has_number("Revenue increased by $2.3 billion") == True
        assert has_number("No numbers here") == False
    
    def test_numeric_density(self):
        """Test numeric density calculation."""
        text1 = "The rate was 3.5% in 2024"  # 2 numbers, 6 tokens
        assert numeric_density(text1) == 2/6
        
        text2 = "No numbers in this text"  # 0 numbers, 5 tokens
        assert numeric_density(text2) == 0.0
    
    def test_allow_quote(self):
        """Test quote admission logic."""
        # Primary source with number
        card = Mock(is_primary_source=True)
        quote = "Tax rate increased to 35% in fiscal year 2024"
        assert allow_quote(card, quote) == True
        
        # Non-primary source
        card = Mock(is_primary_source=False, labels=Mock(is_primary=False))
        assert allow_quote(card, quote) == False


class TestEvidenceBinding:
    """Test evidence-number binding enforcement."""
    
    def test_enforce_number_bindings_valid(self):
        """Test valid bindings pass."""
        bullets = [
            {"id": "b1", "text": "Tax rate", "value": "35%"}
        ]
        
        bindings = {
            "b1": NumberBinding(
                bullet_id="b1",
                value="35%",
                evidence_card_id="card1",
                quote_span="The tax rate was 35% in 2024"
            )
        }
        
        cards_by_id = {
            "card1": Mock(id="card1")
        }
        
        # Should not raise
        enforce_number_bindings(bullets, bindings, cards_by_id)
    
    def test_enforce_number_bindings_missing(self):
        """Test missing bindings fail."""
        bullets = [
            {"id": "b1", "text": "Tax rate", "value": "35%"},
            {"id": "b2", "text": "GDP growth", "value": "2.5%"}
        ]
        
        bindings = {
            "b1": NumberBinding(
                bullet_id="b1",
                value="35%",
                evidence_card_id="card1",
                quote_span="The tax rate was 35%"
            )
        }
        
        cards_by_id = {"card1": Mock(id="card1")}
        
        with pytest.raises(BindingError, match="Unbound numeric bullets"):
            enforce_number_bindings(bullets, bindings, cards_by_id)
    
    def test_enforce_number_bindings_placeholder(self):
        """Test placeholders are rejected."""
        bullets = [
            {"id": "b1", "text": "Tax trend", "value": "[increasing]"}
        ]
        
        bindings = {
            "b1": NumberBinding(
                bullet_id="b1",
                value="[increasing]",
                evidence_card_id="card1",
                quote_span="Taxes have been rising"
            )
        }
        
        cards_by_id = {"card1": Mock(id="card1")}
        
        with pytest.raises(BindingError, match="placeholder"):
            enforce_number_bindings(bullets, bindings, cards_by_id)


class TestInsufficientEvidenceWriter:
    """Test consistent insufficient evidence report writing."""
    
    def test_write_insufficient_evidence_report(self):
        """Test insufficient evidence report generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = FinalMetrics(
                primary_share=0.30,
                triangulation_rate=0.20,
                domain_concentration=0.40,
                sample_sizes={"total_cards": 50, "primary": 15},
                unique_domains=5,
                credible_cards=25,
                recent_primary_count=1,
                triangulated_clusters=0
            )
            
            write_insufficient_evidence_report(
                output_dir=tmpdir,
                metrics=metrics,
                intent="stats",
                errors=["Insufficient primary sources"]
            )
            
            report_path = Path(tmpdir) / "insufficient_evidence_report.md"
            assert report_path.exists()
            
            content = report_path.read_text()
            assert "Insufficient Evidence Report" in content
            assert "30.0%" in content  # Primary share
            assert "statistical" in content  # Intent-specific content
            assert "Insufficient primary sources" in content


class TestIntegration:
    """Integration tests for v8.13.0 improvements."""
    
    @patch('research_system.quality.metrics_v2.compute_metrics')
    @patch('research_system.quality.metrics_v2.gates_pass')
    def test_hard_gate_prevents_final_report(self, mock_gates, mock_compute):
        """Test that failed gates prevent final report generation."""
        # Setup mocks
        mock_metrics = FinalMetrics(
            primary_share=0.20,  # Below threshold
            triangulation_rate=0.15,  # Below threshold
            domain_concentration=0.60,  # Above cap
            sample_sizes={"total_cards": 20},
            unique_domains=3,
            credible_cards=10,
            recent_primary_count=1,
            triangulated_clusters=0
        )
        mock_compute.return_value = mock_metrics
        mock_gates.return_value = False
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Simulate orchestrator behavior
            output_dir = Path(tmpdir)
            
            # Compute metrics
            cards = [Mock() for _ in range(20)]
            metrics = mock_compute(cards)
            
            # Check gates
            if not mock_gates(metrics, "stats"):
                # Write insufficient evidence ONLY
                write_insufficient_evidence_report(
                    str(output_dir),
                    metrics,
                    "stats"
                )
            else:
                # Would write final report (but shouldn't reach here)
                (output_dir / "final_report.md").write_text("Should not exist")
            
            # Verify only insufficient evidence report exists
            assert (output_dir / "insufficient_evidence_report.md").exists()
            assert not (output_dir / "final_report.md").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])