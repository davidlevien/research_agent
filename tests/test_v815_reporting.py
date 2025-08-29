"""
Tests for v8.15.0 enhanced reporting system.
Validates quality gates, citation binding, and actionable guidance.
"""

from pathlib import Path
import json
import tempfile
import pytest
from unittest.mock import Mock, patch

from research_system.context import RunContext, Metrics
from research_system.report.enhanced_final_report import ReportWriter as FinalReportWriter
from research_system.report.enhanced_insufficient import ReportWriter as InsufficientReportWriter
from research_system.report.source_strategy import ReportWriter as SourceStrategyWriter
from research_system.report.utils import (
    sentence_trim, unique_preserve_order, extract_domain,
    format_citations, is_numeric_claim, clean_html
)


class TestMetrics:
    """Test metrics loading and gate checking."""
    
    def test_metrics_from_file_with_valid_data(self, tmp_path):
        """Test loading metrics from valid JSON file."""
        metrics_file = tmp_path / "metrics.json"
        metrics_data = {
            "cards": 50,
            "union_triangulation": 0.65,
            "primary_share": 0.45,
            "top_domain_share": 0.20,
            "triangulated_cards": 30,
            "credible_cards": 40,
            "unique_domains": 15
        }
        metrics_file.write_text(json.dumps(metrics_data))
        
        metrics = Metrics.from_file(metrics_file)
        
        assert metrics.cards == 50
        assert metrics.union_triangulation == 0.65
        assert metrics.primary_share == 0.45
        assert metrics.top_domain_share == 0.20
        assert metrics.triangulated_cards == 30
        assert metrics.credible_cards == 40
        assert metrics.unique_domains == 15
    
    def test_metrics_from_file_with_missing_fields(self, tmp_path):
        """Test loading metrics with some fields missing."""
        metrics_file = tmp_path / "metrics.json"
        metrics_data = {
            "cards": 25,
            "union_triangulation_rate": 0.40,  # Alternative field name
            "primary_share_in_union": 0.30     # Alternative field name
        }
        metrics_file.write_text(json.dumps(metrics_data))
        
        metrics = Metrics.from_file(metrics_file)
        
        assert metrics.cards == 25
        assert metrics.union_triangulation == 0.40
        assert metrics.primary_share == 0.30
        assert metrics.top_domain_share == 0.0  # Default value
    
    def test_metrics_from_nonexistent_file(self, tmp_path):
        """Test loading metrics from nonexistent file."""
        metrics_file = tmp_path / "missing.json"
        
        metrics = Metrics.from_file(metrics_file)
        
        assert metrics.cards == 0
        assert metrics.union_triangulation == 0.0
        assert metrics.primary_share == 0.0
    
    def test_meets_gates_passing(self):
        """Test quality gates passing."""
        metrics = Metrics(
            cards=50,
            union_triangulation=0.60,
            primary_share=0.40
        )
        
        assert metrics.meets_gates() is True
        assert metrics.meets_gates(0.50, 0.33, 25) is True
    
    def test_meets_gates_failing(self):
        """Test quality gates failing."""
        metrics = Metrics(
            cards=20,
            union_triangulation=0.30,
            primary_share=0.25
        )
        
        assert metrics.meets_gates() is False
        failures = metrics.get_gate_failures()
        
        assert len(failures) == 3
        assert "triangulation" in failures[0]
        assert "primary_share" in failures[1]
        assert "cards" in failures[2]


class TestRunContext:
    """Test run context management."""
    
    def test_context_creation(self, tmp_path):
        """Test creating run context."""
        metrics = Metrics(cards=50, union_triangulation=0.60, primary_share=0.40)
        
        ctx = RunContext(
            outdir=tmp_path,
            query="test query",
            metrics=metrics,
            allow_final_report=True,
            providers_used=["tavily", "brave"],
            intent="stats"
        )
        
        assert ctx.outdir == tmp_path
        assert ctx.query == "test query"
        assert ctx.allow_final_report is True
        assert ctx.intent == "stats"
        assert len(ctx.providers_used) == 2
    
    def test_context_paths(self, tmp_path):
        """Test context path properties."""
        ctx = RunContext(
            outdir=tmp_path,
            query="test",
            metrics=Metrics(),
            allow_final_report=False
        )
        
        assert ctx.metrics_path == tmp_path / "metrics.json"
        assert ctx.cards_path == tmp_path / "evidence_cards.jsonl"
        assert ctx.final_report_path == tmp_path / "final_report.md"
        assert ctx.insufficient_report_path == tmp_path / "insufficient_evidence_report.md"
    
    def test_should_generate_final(self, tmp_path):
        """Test final report generation decision."""
        metrics_file = tmp_path / "metrics.json"
        metrics_data = {
            "cards": 50,
            "union_triangulation": 0.60,
            "primary_share": 0.40
        }
        metrics_file.write_text(json.dumps(metrics_data))
        
        ctx = RunContext(
            outdir=tmp_path,
            query="test",
            metrics=Metrics(),
            allow_final_report=False
        )
        
        # Should reload metrics and determine gates pass
        assert ctx.should_generate_final() is True
        assert ctx.allow_final_report is True
        assert ctx.reason_final_report_blocked is None


class TestReportUtils:
    """Test report utility functions."""
    
    def test_sentence_trim_short_text(self):
        """Test trimming text shorter than limit."""
        text = "This is a short sentence."
        result = sentence_trim(text, 100)
        assert result == text
    
    def test_sentence_trim_at_boundary(self):
        """Test trimming at sentence boundary."""
        text = "First sentence. Second sentence. Third sentence that is very long and should be cut off."
        result = sentence_trim(text, 50)
        assert result == "First sentence. Second sentence."
    
    def test_sentence_trim_no_boundary(self):
        """Test trimming when no sentence boundary found."""
        text = "This is a very long sentence without any punctuation that goes on and on"
        result = sentence_trim(text, 30)
        assert result.endswith("…")
        assert len(result) <= 31  # 30 chars + ellipsis
    
    def test_unique_preserve_order(self):
        """Test removing duplicates while preserving order."""
        items = ["a", "b", "c", "b", "d", "a", "e"]
        result = unique_preserve_order(items)
        assert result == ["a", "b", "c", "d", "e"]
    
    def test_extract_domain(self):
        """Test domain extraction from URLs."""
        assert extract_domain("https://www.example.com/page") == "example.com"
        assert extract_domain("http://sub.domain.org") == "sub.domain.org"
        assert extract_domain("invalid-url") == ""
    
    def test_is_numeric_claim(self):
        """Test numeric claim detection."""
        assert is_numeric_claim("GDP grew by 3.5% in 2024") is True
        assert is_numeric_claim("Revenue reached $1.2 billion") is True
        assert is_numeric_claim("Unemployment is at five percent") is True
        assert is_numeric_claim("The economy is growing") is False
    
    def test_format_citations(self):
        """Test citation formatting."""
        urls = [
            "https://example.com/1",
            "https://example.com/2",
            "https://example.com/3"
        ]
        result = format_citations(urls)
        assert result == "[1](https://example.com/1) [2](https://example.com/2) [3](https://example.com/3)"
    
    def test_clean_html(self):
        """Test HTML cleaning."""
        text = "This has <b>bold</b> and <a href='#'>links</a>."
        result = clean_html(text)
        assert result == "This has bold and links."


class TestFinalReportWriter:
    """Test final report generation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tmp_path = Path(tempfile.mkdtemp())
        
        # Create test metrics
        metrics_data = {
            "cards": 50,
            "union_triangulation": 0.60,
            "primary_share": 0.40,
            "unique_domains": 15,
            "credible_cards": 40
        }
        (self.tmp_path / "metrics.json").write_text(json.dumps(metrics_data))
        
        # Create test evidence cards
        cards = [
            {
                "url": "https://oecd.org/report1",
                "snippet": "GDP increased by 3.5% in Q4 2024",
                "provider": "tavily",
                "credibility_score": 0.9,
                "triangulated": True
            },
            {
                "url": "https://imf.org/data",
                "quote": "Unemployment rate fell to 4.2%",
                "provider": "brave",
                "credibility_score": 0.85
            },
            {
                "url": "https://worldbank.org/stats",
                "claim": "Global trade volume rose 5.1%",
                "provider": "tavily",
                "credibility_score": 0.88,
                "triangulated": True
            }
        ]
        
        with open(self.tmp_path / "evidence_cards.jsonl", "w") as f:
            for card in cards:
                f.write(json.dumps(card) + "\n")
        
        # Create test triangulation data
        triangulation = {
            "clusters": [
                {
                    "representative_text": "Economic growth accelerated in Q4",
                    "domains": ["oecd.org", "imf.org"]
                }
            ]
        }
        (self.tmp_path / "triangulation.json").write_text(json.dumps(triangulation))
    
    def test_final_report_generation_allowed(self):
        """Test final report generation when gates pass."""
        ctx = RunContext(
            outdir=self.tmp_path,
            query="global economic indicators 2024",
            metrics=Metrics.from_file(self.tmp_path / "metrics.json"),
            allow_final_report=True,
            providers_used=["tavily", "brave"]
        )
        
        writer = FinalReportWriter(ctx)
        writer.write()
        
        report_path = self.tmp_path / "final_report.md"
        assert report_path.exists()
        
        content = report_path.read_text()
        assert "# Final Report" in content
        assert "global economic indicators 2024" in content
        assert "## Executive Summary" in content
        assert "## Key Numbers (with citations)" in content
        assert "## Evidence Supply" in content
        assert "## Citation Safety" in content
    
    def test_final_report_suppressed_when_gated(self):
        """Test final report is not written when gates fail."""
        ctx = RunContext(
            outdir=self.tmp_path,
            query="test query",
            metrics=Metrics(cards=10, union_triangulation=0.20, primary_share=0.15),
            allow_final_report=False,
            reason_final_report_blocked="triangulation 0.20 < 0.50"
        )
        
        writer = FinalReportWriter(ctx)
        writer.write()
        
        report_path = self.tmp_path / "final_report.md"
        assert not report_path.exists()
    
    def test_key_numbers_extraction(self):
        """Test extraction of key numbers with citations."""
        ctx = RunContext(
            outdir=self.tmp_path,
            query="test",
            metrics=Metrics.from_file(self.tmp_path / "metrics.json"),
            allow_final_report=True
        )
        
        writer = FinalReportWriter(ctx)
        cards = writer._load_cards()
        key_numbers = writer._build_key_numbers(cards)
        
        assert len(key_numbers) > 0
        
        # Check that each key number has citations
        for claim, citations in key_numbers:
            assert is_numeric_claim(claim)
            assert len(citations) > 0
            assert all(c.startswith("http") for c in citations)
    
    def test_citation_safety_calculation(self):
        """Test citation safety metrics."""
        ctx = RunContext(
            outdir=self.tmp_path,
            query="test",
            metrics=Metrics(),
            allow_final_report=True
        )
        
        writer = FinalReportWriter(ctx)
        
        # Test with all numbers having citations
        key_numbers = [
            ("GDP grew 3%", ["https://example.com"]),
            ("Unemployment 4%", ["https://example.org"])
        ]
        safety = writer._calculate_citation_safety(key_numbers)
        assert safety["pass"] is True
        assert "2/2" in safety["summary"]
        
        # Test with missing citations
        key_numbers = [
            ("GDP grew 3%", ["https://example.com"]),
            ("Unemployment 4%", [])
        ]
        safety = writer._calculate_citation_safety(key_numbers)
        assert safety["pass"] is False
        assert "1/2" in safety["summary"]


class TestInsufficientReportWriter:
    """Test insufficient evidence report generation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tmp_path = Path(tempfile.mkdtemp())
        
        # Create failing metrics
        metrics_data = {
            "cards": 15,
            "union_triangulation": 0.25,
            "primary_share": 0.20
        }
        (self.tmp_path / "metrics.json").write_text(json.dumps(metrics_data))
    
    def test_insufficient_report_generation(self):
        """Test insufficient evidence report generation."""
        ctx = RunContext(
            outdir=self.tmp_path,
            query="tax rates and economic class",
            metrics=Metrics.from_file(self.tmp_path / "metrics.json"),
            allow_final_report=False,
            reason_final_report_blocked="triangulation 0.25 < 0.50; primary_share 0.20 < 0.33",
            providers_used=["tavily", "brave"],
            intent="stats"
        )
        
        writer = InsufficientReportWriter(ctx)
        writer.write()
        
        report_path = self.tmp_path / "insufficient_evidence_report.md"
        assert report_path.exists()
        
        content = report_path.read_text()
        assert "# Insufficient Evidence Report" in content
        assert "tax rates and economic class" in content
        assert "## Why Quality Gates Were Not Met" in content
        assert "## Next Steps (Concrete Actions)" in content
        assert "triangulation 0.25 < 0.50" in content
    
    def test_next_steps_generation_stats(self):
        """Test generation of next steps for stats intent."""
        ctx = RunContext(
            outdir=self.tmp_path,
            query="unemployment statistics",
            metrics=Metrics(cards=10, union_triangulation=0.20, primary_share=0.15),
            allow_final_report=False,
            intent="stats"
        )
        
        writer = InsufficientReportWriter(ctx)
        steps = writer._generate_next_steps()
        
        assert len(steps) > 0
        assert any("OECD" in step for step in steps)
        assert any("World Bank" in step for step in steps)
        assert any("IMF" in step for step in steps)
        assert any("backfill" in step.lower() for step in steps)
    
    def test_troubleshooting_tips(self):
        """Test generation of troubleshooting tips."""
        ctx = RunContext(
            outdir=self.tmp_path,
            query="test",
            metrics=Metrics(
                cards=10,
                union_triangulation=0.15,
                primary_share=0.10,
                top_domain_share=0.60
            ),
            allow_final_report=False,
            providers_used=["tavily"]
        )
        
        writer = InsufficientReportWriter(ctx)
        tips = writer._generate_troubleshooting_tips()
        
        assert len(tips) > 0
        assert any("Low triangulation" in tip for tip in tips)
        assert any("Low primary share" in tip for tip in tips)
        assert any("High domain concentration" in tip for tip in tips)
        assert any("Limited providers" in tip for tip in tips)


class TestSourceStrategyWriter:
    """Test source strategy report generation."""
    
    def test_source_strategy_with_providers(self, tmp_path):
        """Test source strategy generation with provider info."""
        ctx = RunContext(
            outdir=tmp_path,
            query="test",
            metrics=Metrics(cards=50, union_triangulation=0.60, primary_share=0.40),
            allow_final_report=True,
            providers_used=["tavily", "brave", "oecd", "fred"],
            intent="stats"
        )
        
        writer = SourceStrategyWriter(ctx)
        writer.write()
        
        report_path = tmp_path / "source_strategy.md"
        assert report_path.exists()
        
        content = report_path.read_text()
        assert "# Source Strategy" in content
        assert "## Providers Used in This Run" in content
        assert "### Specialized Data Sources" in content
        assert "oecd" in content
        assert "fred" in content
        assert "### General Search Providers" in content
        assert "tavily" in content
        assert "## Backfill Policy" in content
        assert "Quality Gates Met" in content
    
    def test_source_strategy_with_failed_gates(self, tmp_path):
        """Test source strategy when gates fail."""
        ctx = RunContext(
            outdir=tmp_path,
            query="test",
            metrics=Metrics(cards=10, union_triangulation=0.20, primary_share=0.15),
            allow_final_report=False,
            reason_final_report_blocked="quality gates not met",
            providers_used=["tavily"],
            intent="generic"
        )
        
        writer = SourceStrategyWriter(ctx)
        writer.write()
        
        report_path = tmp_path / "source_strategy.md"
        content = report_path.read_text()
        
        assert "Quality Gates Not Met" in content
        assert "Backfill strategy enabled" in content
        assert "Expand provider set" in content


class TestIntegration:
    """Integration tests for the complete reporting system."""
    
    def test_complete_workflow_passing_gates(self, tmp_path):
        """Test complete workflow when quality gates pass."""
        # Set up good metrics
        metrics_data = {
            "cards": 100,
            "union_triangulation": 0.70,
            "primary_share": 0.50,
            "unique_domains": 25,
            "credible_cards": 80
        }
        (tmp_path / "metrics.json").write_text(json.dumps(metrics_data))
        
        # Set up evidence cards
        cards = []
        for i in range(10):
            cards.append({
                "url": f"https://source{i}.org/article",
                "snippet": f"Finding {i}: Value increased by {i*10}%",
                "provider": "tavily",
                "credibility_score": 0.8,
                "triangulated": i < 7
            })
        
        with open(tmp_path / "evidence_cards.jsonl", "w") as f:
            for card in cards:
                f.write(json.dumps(card) + "\n")
        
        # Create context
        ctx = RunContext(
            outdir=tmp_path,
            query="comprehensive test query",
            metrics=Metrics.from_file(tmp_path / "metrics.json"),
            allow_final_report=True,
            providers_used=["tavily", "brave", "oecd"],
            intent="stats"
        )
        
        # Generate all reports
        FinalReportWriter(ctx).write()
        SourceStrategyWriter(ctx).write()
        
        # Verify outputs
        assert (tmp_path / "final_report.md").exists()
        assert (tmp_path / "source_strategy.md").exists()
        assert not (tmp_path / "insufficient_evidence_report.md").exists()
        
        # Check final report content
        final_content = (tmp_path / "final_report.md").read_text()
        assert "comprehensive test query" in final_content
        assert "Evidence Cards:** 100" in final_content
    
    def test_complete_workflow_failing_gates(self, tmp_path):
        """Test complete workflow when quality gates fail."""
        # Set up poor metrics
        metrics_data = {
            "cards": 10,
            "union_triangulation": 0.20,
            "primary_share": 0.15,
            "unique_domains": 3
        }
        (tmp_path / "metrics.json").write_text(json.dumps(metrics_data))
        
        # Create context
        ctx = RunContext(
            outdir=tmp_path,
            query="insufficient test query",
            metrics=Metrics.from_file(tmp_path / "metrics.json"),
            allow_final_report=False,
            reason_final_report_blocked="multiple gate failures",
            providers_used=["tavily"],
            intent="generic"
        )
        
        # Generate reports
        InsufficientReportWriter(ctx).write()
        SourceStrategyWriter(ctx).write()
        
        # Verify outputs
        assert not (tmp_path / "final_report.md").exists()
        assert (tmp_path / "insufficient_evidence_report.md").exists()
        assert (tmp_path / "source_strategy.md").exists()
        
        # Check insufficient report content
        insuff_content = (tmp_path / "insufficient_evidence_report.md").read_text()
        assert "insufficient test query" in insuff_content
        assert "multiple gate failures" in insuff_content
        assert "Next Steps" in insuff_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])