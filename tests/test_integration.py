"""
Integration tests for the complete research system
"""

import pytest
import json
from pathlib import Path

from research_system.models import EvidenceCard
from research_system.tools.registry import tool_registry
from research_system.core.quality_assurance import QualityAssurance


class TestToolRegistry:
    """Test tool registry with list output validation"""
    
    def test_list_output_validation(self):
        """Test that registry validates List[T] outputs correctly"""
        
        # Register a tool that returns List[str]
        def get_strings() -> list:
            return ["a", "b", "c"]
        
        tool_registry.register(
            name="test_get_strings",
            description="Test tool",
            category="test",
            function=get_strings,
            output_type=list[str]
        )
        
        # Execute and validate
        result = tool_registry.execute_tool("test_get_strings", validate_output=True)
        assert result == ["a", "b", "c"]
        
        # Register a tool that returns List[Dict]
        def get_dicts() -> list:
            return [{"key": "value1"}, {"key": "value2"}]
        
        tool_registry.register(
            name="test_get_dicts",
            description="Test tool",
            category="test", 
            function=get_dicts,
            output_type=list[dict]
        )
        
        result = tool_registry.execute_tool("test_get_dicts", validate_output=True)
        assert len(result) == 2
        assert all(isinstance(item, dict) for item in result)
    
    def test_duplicate_tool_protection(self):
        """Test that duplicate tool names are rejected"""
        
        def dummy_tool():
            return "test"
        
        # First registration should succeed
        tool_registry.register(
            name="unique_tool",
            description="Test",
            category="test",
            function=dummy_tool
        )
        
        # Second registration with same name should fail
        with pytest.raises(ValueError, match="already registered"):
            tool_registry.register(
                name="unique_tool",
                description="Test",
                category="test",
                function=dummy_tool
            )


class TestEvidenceSchema:
    """Test evidence card schema validation"""
    
    def test_evidence_card_serialization(self):
        """Test evidence card can be serialized to JSON"""
        
        card = EvidenceCard(
            url="https://example.com",
            title="Test Source",
            snippet="Supporting text",
            provider="tavily",
            subtopic_name="Test Subtopic",
            claim="Test claim",
            supporting_text="Supporting text",
            source_domain="example.com",
            credibility_score=0.8,
            relevance_score=0.9,
            confidence=0.85,
            is_primary_source=True,
            collected_at="2025-01-01T00:00:00Z"
        )
        
        # Serialize to JSON
        json_str = json.dumps(card.dict(), default=str)
        data = json.loads(json_str)
        
        # Check required fields
        assert data["id"]
        assert data["subtopic_name"] == "Test Subtopic"
        assert data["claim"] == "Test claim"
        assert data["url"] == "https://example.com"
        assert data["credibility_score"] == 0.8
        assert data["relevance_score"] == 0.9
    
    def test_evidence_card_deserialization(self):
        """Test evidence card can be deserialized from JSON"""
        
        json_data = {
            "id": "test-id",
            "url": "https://example.com",
            "title": "Title",
            "snippet": "Text",
            "provider": "test",
            "subtopic_name": "Test",
            "claim": "Test claim",
            "supporting_text": "Text",
            "source_domain": "example.com",
            "credibility_score": 0.5,
            "relevance_score": 0.6,
            "confidence": 0.55,
            "is_primary_source": False,
            "collected_at": "2024-01-01T00:00:00"
        }
        
        card = EvidenceCard(**json_data)
        assert card.id == "test-id"
        assert card.claim == "Test claim"
        assert card.credibility_score == 0.5


class TestQualityAssurance:
    """Test quality assurance system"""
    
    def test_quality_assessment(self):
        """Test evidence quality assessment"""
        
        qa = QualityAssurance()
        
        card = EvidenceCard(
            url="https://academic.edu/paper",
            title="Research Paper",
            snippet="Studies show that 95% of cases demonstrate this pattern.",
            provider="tavily",
            subtopic_name="Test",
            claim="This is always true for everyone.",
            supporting_text="Studies show that 95% of cases demonstrate this pattern.",
            source_domain="academic.edu",
            credibility_score=0.8,
            relevance_score=0.9,
            confidence=0.85,
            is_primary_source=True,
            collected_at="2024-01-01T00:00:00"
        )
        
        score = qa.assess_evidence_quality(card)
        
        assert score.credibility > 0
        assert score.accuracy >= 0
        assert score.completeness >= 0
        assert score.bias_level >= 0
        assert score.overall >= 0
        
        # Should detect absolute claims
        assert any("absolute" in issue.lower() for issue in score.issues)
    
    def test_cross_validation(self):
        """Test cross-validation of multiple evidence"""
        
        qa = QualityAssurance()
        
        evidence = [
            EvidenceCard(
                url="https://example.com/1",
                title="Study 1",
                snippet="Study shows positive correlation",
                provider="tavily",
                subtopic_name="Test",
                claim="Temperature increases productivity",
                supporting_text="Study shows positive correlation",
                source_domain="example.com",
                credibility_score=0.8,
                relevance_score=0.9,
                confidence=0.85,
                is_primary_source=True,
                collected_at="2024-01-01T00:00:00"
            ),
            EvidenceCard(
                url="https://example.org/2",
                title="Study 2",
                snippet="Research confirms positive impact",
                provider="tavily",
                subtopic_name="Test",
                claim="Temperature increases productivity",
                supporting_text="Research confirms positive impact",
                source_domain="example.org",
                credibility_score=0.7,
                relevance_score=0.8,
                confidence=0.75,
                is_primary_source=False,
                collected_at="2024-01-01T00:00:00"
            )
        ]
        
        validation = qa.cross_validate_evidence(evidence)
        
        assert "consensus_level" in validation
        assert "contradictions" in validation
        assert "corroborations" in validation
        assert validation["confidence"] > 0


class TestDeliverables:
    """Test deliverable file generation"""
    
    @pytest.mark.skip(reason="ResearchEngine is legacy - production uses Orchestrator directly")
    def test_plan_md_format(self, tmp_path):
        """Test plan.md has correct format"""
        
        from research_system.research_engine import ResearchEngine
        from research_system.models import ResearchPlan, ResearchDepth, Subtopic, ResearchMethodology
        
        engine = ResearchEngine(output_dir=str(tmp_path))
        
        plan = ResearchPlan(
            topic="Test Topic",
            depth=ResearchDepth.STANDARD,
            subtopics=[
                Subtopic(name="Sub1", rationale="Reason", search_queries=["q1"])
            ],
            methodology=ResearchMethodology(
                search_strategy="Strategy",
                quality_criteria=["criterion"]
            ),
            constraints=None,
            budget={"max_cost_usd": 1.0}
        )
        
        filepath = engine._save_plan(plan)
        content = Path(filepath).read_text()
        
        assert "# Research Plan" in content
        assert "## Topic" in content
        assert "## Subtopics" in content
        assert "## Methodology" in content
        assert "Test Topic" in content
    
    @pytest.mark.skip(reason="ResearchEngine is legacy - production uses Orchestrator directly") 
    def test_evidence_jsonl_format(self, tmp_path):
        """Test evidence_cards.jsonl has correct format"""
        
        from research_system.research_engine import ResearchEngine
        
        engine = ResearchEngine(output_dir=str(tmp_path))
        
        evidence = [
            EvidenceCard(
                subtopic_name="Test",
                claim="Claim 1",
                supporting_text="Text 1",
                source_url="https://example.com/1",
                source_title="Title 1",
                source_domain="example.com",
                credibility_score=0.8,
                relevance_score=0.9,
                is_primary_source=True
            ),
            EvidenceCard(
                subtopic_name="Test",
                claim="Claim 2",
                supporting_text="Text 2",
                source_url="https://example.com/2",
                source_title="Title 2",
                source_domain="example.com",
                credibility_score=0.7,
                relevance_score=0.8,
                is_primary_source=False
            )
        ]
        
        filepath = engine._save_evidence_cards(evidence)
        
        # Read and validate JSONL
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) == 2
        
        for line in lines:
            data = json.loads(line)
            assert all(key in data for key in [
                "id", "subtopic_name", "claim", "supporting_text",
                "source_url", "source_title", "source_domain",
                "credibility_score", "relevance_score", "is_primary_source"
            ])