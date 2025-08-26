"""
Test suite for research engine

NOTE: ResearchEngine is a legacy component not used in production.
The production system uses Orchestrator directly via main.py.
These tests are kept for historical reference but marked as skipped.
"""

import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# Mark entire module as skipped since ResearchEngine is legacy
pytestmark = pytest.mark.skip(reason="ResearchEngine is legacy - production uses Orchestrator directly")

from research_system.research_engine import ResearchEngine
from research_system.models import ResearchRequest, ResearchDepth, EvidenceCard


@pytest.fixture
def research_engine(tmp_path):
    """Create research engine with temp output directory"""
    return ResearchEngine(output_dir=str(tmp_path))


@pytest.fixture
def sample_request():
    """Create sample research request"""
    return ResearchRequest(
        topic="Test Topic",
        depth=ResearchDepth.STANDARD
    )


@pytest.fixture
def sample_evidence():
    """Create sample evidence cards"""
    return [
        EvidenceCard(
            # Required fields
            url="https://example.com/1",
            title="Source 1",
            snippet="Supporting text for claim 1",
            provider="test_provider",
            # Legacy fields for compatibility
            subtopic_name="Subtopic 1",
            claim="Test claim 1",
            supporting_text="Supporting text for claim 1",
            source_url="https://example.com/1",
            source_title="Source 1",
            source_domain="example.com",
            credibility_score=0.8,
            relevance_score=0.9,
            is_primary_source=True
        ),
        EvidenceCard(
            # Required fields
            url="https://example.org/2",
            title="Source 2",
            snippet="Supporting text for claim 2",
            provider="test_provider",
            # Legacy fields for compatibility
            subtopic_name="Subtopic 2",
            claim="Test claim 2",
            supporting_text="Supporting text for claim 2",
            source_url="https://example.org/2",
            source_title="Source 2",
            source_domain="example.org",
            credibility_score=0.7,
            relevance_score=0.8,
            is_primary_source=False
        )
    ]


class TestResearchEngine:
    """Test research engine functionality"""
    
    def test_initialization(self, tmp_path):
        """Test engine initialization"""
        engine = ResearchEngine(output_dir=str(tmp_path))
        assert engine.output_dir == tmp_path
        assert tmp_path.exists()
        assert len(engine.deliverables_produced) == 0
    
    @pytest.mark.asyncio
    async def test_all_deliverables_produced(self, research_engine, sample_request, sample_evidence, tmp_path):
        """Test that all 7 deliverables are produced"""
        
        # Mock the research engine methods
        with patch.object(research_engine, '_execute_planning_phase') as mock_planning:
            with patch.object(research_engine, '_execute_collection_phase') as mock_collection:
                with patch.object(research_engine, '_execute_synthesis_phase') as mock_synthesis:
                    
                    # Setup mocks
                    from research_system.models import ResearchPlan, ResearchReport, ResearchMetrics, Subtopic
                    
                    mock_plan = ResearchPlan(
                        topic="Test Topic",
                        objectives=["Objective 1", "Objective 2"],
                        methodology="Test methodology",
                        expected_sources=["Source 1", "Source 2"]
                    )
                    
                    from datetime import datetime
                    mock_report = ResearchReport(
                        report_id="test-report-id",
                        topic="Test Topic",
                        executive_summary="Test summary",
                        sections=[],
                        evidence=sample_evidence,
                        metrics=ResearchMetrics(
                            total_sources_examined=10,
                            total_evidence_collected=2,
                            unique_domains=2,
                            avg_credibility_score=0.75,
                            execution_time_seconds=10.0,
                            total_cost_usd=0.10,
                            llm_calls=5,
                            search_api_calls=3
                        ),
                        created_at=datetime.now(),
                        status="completed"
                    )
                    
                    mock_planning.return_value = mock_plan
                    mock_collection.return_value = sample_evidence
                    mock_synthesis.return_value = mock_report
                    
                    # Execute research
                    report, deliverables = await research_engine.execute_research(sample_request)
                    
                    # Check all 7 deliverables were produced
                    expected_deliverables = [
                        "plan",
                        "source_strategy",
                        "acceptance_guardrails",
                        "evidence_cards",
                        "source_quality_table",
                        "final_report",
                        "citation_checklist"
                    ]
                    
                    for deliverable in expected_deliverables:
                        assert deliverable in deliverables
                        filepath = Path(deliverables[deliverable])
                        assert filepath.exists()
                        assert filepath.stat().st_size > 0
                    
                    # Check specific files
                    assert (tmp_path / "plan.md").exists()
                    assert (tmp_path / "source_strategy.md").exists()
                    assert (tmp_path / "acceptance_guardrails.md").exists()
                    assert (tmp_path / "evidence_cards.jsonl").exists()
                    assert (tmp_path / "source_quality_table.md").exists()
                    assert (tmp_path / "final_report.md").exists()
                    assert (tmp_path / "citation_checklist.md").exists()
    
    def test_evidence_cards_jsonl_format(self, research_engine, sample_evidence):
        """Test evidence cards are saved in correct JSONL format"""
        
        filepath = research_engine._save_evidence_cards(sample_evidence)
        
        # Read and validate JSONL
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) == len(sample_evidence)
        
        for line in lines:
            data = json.loads(line)
            assert "id" in data
            assert "subtopic_name" in data
            assert "claim" in data
            assert "supporting_text" in data
            assert "source_url" in data
            assert "credibility_score" in data
    
    def test_quality_table_generation(self, research_engine, sample_evidence):
        """Test source quality table generation"""
        
        # Save evidence cards first
        evidence_path = research_engine._save_evidence_cards(sample_evidence)
        # Generate quality table from evidence file
        filepath = research_engine._save_quality_table_from_evidence(Path(evidence_path))
        
        content = Path(filepath).read_text()
        
        # Check table structure
        assert "| Source | Credibility | Accuracy | Completeness | Bias | Overall | Issues |" in content
        assert "example.com" in content
        assert "example.org" in content
        assert "## Summary Statistics" in content
        assert "## Quality Distribution" in content
    
    def test_citation_checklist_generation(self, research_engine, sample_evidence):
        """Test citation checklist generation"""
        
        from research_system.models import ResearchReport, ResearchSection, ResearchMetrics
        
        from datetime import datetime
        mock_report = ResearchReport(
            report_id="test-id",
            topic="Test Topic",
            executive_summary="Summary",
            sections=[
                ResearchSection(
                    title="Section 1",
                    content="Test claim 1 is important. Another statement here.",
                    evidence_ids=[sample_evidence[0].id]
                )
            ],
            evidence=sample_evidence,
            metrics=ResearchMetrics(
                total_sources_examined=10,
                total_evidence_collected=2,
                unique_domains=2,
                avg_credibility_score=0.75,
                execution_time_seconds=10.0,
                total_cost_usd=0.10,
                llm_calls=5,
                search_api_calls=3
            ),
            created_at=datetime.now(),
            status="completed"
        )
        
        checklist = research_engine._generate_citation_checklist(mock_report, sample_evidence)
        filepath = research_engine._save_citation_checklist(checklist)
        
        content = Path(filepath).read_text()
        
        # Check checklist content
        assert "# Citation Verification Checklist" in content
        assert "## Overview" in content
        assert "## Source Distribution" in content
        assert "## Validation Status" in content
    
    @pytest.mark.asyncio
    async def test_strict_mode_validation(self, research_engine, sample_request):
        """Test strict mode raises on missing deliverables"""
        
        with pytest.raises(Exception):
            # This should fail because we're not mocking the methods
            await research_engine.execute_research(sample_request, strict_mode=True)
    
    def test_deliverable_validation(self, research_engine, tmp_path):
        """Test deliverable validation"""
        
        # Create dummy files
        deliverables = {}
        required = [
            "plan", "source_strategy", "acceptance_guardrails",
            "evidence_cards", "source_quality_table", "final_report",
            "citation_checklist"
        ]
        
        for name in required:
            filepath = tmp_path / f"{name}.md"
            filepath.write_text("content")
            deliverables[name] = str(filepath)
        
        # Should not raise
        research_engine._validate_deliverables(deliverables)
        
        # Test missing deliverable
        del deliverables["plan"]
        with pytest.raises(ValueError, match="Missing required deliverable"):
            research_engine._validate_deliverables(deliverables)
        
        # Test empty file
        deliverables["plan"] = str(tmp_path / "empty.md")
        (tmp_path / "empty.md").touch()
        with pytest.raises(ValueError, match="Deliverable file is empty"):
            research_engine._validate_deliverables(deliverables)