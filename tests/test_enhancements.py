"""
Unit tests for enhancement components
"""

import pytest
from datetime import datetime
from unittest.mock import Mock
from research_system.collection import _provider_policy
from research_system.tools.aggregates import canonical_domain, source_quality, triangulate_claims
from research_system.tools.evidence_io import validate_evidence_dict
from research_system.models import EvidenceCard


class TestProviderPolicy:
    """Test provider policy filtering"""
    
    def test_excludes_nps_for_general_queries(self):
        providers = ["tavily", "brave", "serper", "nps"]
        result = _provider_policy("latest technology trends", providers)
        assert "nps" not in result
        assert set(result) == {"tavily", "brave", "serper"}
    
    def test_includes_nps_for_park_queries(self):
        providers = ["tavily", "brave", "serper", "nps"]
        
        # Test various park-related queries
        queries = [
            "yellowstone national park",
            "best hiking trails 2025",
            "camping permits needed",
            "civil war memorial sites"
        ]
        
        for query in queries:
            result = _provider_policy(query, providers)
            assert "nps" in result, f"NPS should be included for: {query}"
    
    def test_handles_missing_nps(self):
        """Test that NPS is added even when not in original providers for park queries."""
        providers = ["tavily", "brave"]
        result = _provider_policy("national park visits", providers)
        assert "nps" in result  # Should include NPS for park queries
        assert "tavily" in result
        assert "brave" in result


class TestEvidenceValidation:
    """Test enhanced evidence validation"""
    
    def test_validates_required_fields(self):
        valid_card = {
            "id": "12345678-1234-1234-1234-123456789012",
            "title": "Test Article",
            "url": "https://example.com",
            "snippet": "Test content here",
            "provider": "tavily",
            "credibility_score": 0.8,
            "relevance_score": 0.7,
            "confidence": 0.75,
            "subtopic_name": "Test Subtopic",
            "claim": "Test claim here",
            "supporting_text": "Supporting evidence text",
            "source_domain": "example.com",
            "is_primary_source": False,
            "collected_at": "2024-01-01T12:00:00Z",
            "stance": "neutral"
        }
        
        # Should not raise
        validate_evidence_dict(valid_card)
    
    def test_rejects_missing_fields(self):
        invalid_card = {
            "id": "12345678-1234-1234-1234-123456789012",
            "title": "Test Article",
            "url": "https://example.com",
            # Missing snippet, provider, and other required fields
            "credibility_score": 0.8,
            "relevance_score": 0.7,
            "confidence": 0.75
        }
        
        with pytest.raises(ValueError, match="validation failed"):
            validate_evidence_dict(invalid_card)
    
    def test_rejects_empty_snippet(self):
        invalid_card = {
            "id": "12345678-1234-1234-1234-123456789012",
            "title": "Test Article",
            "url": "https://example.com",
            "snippet": "   ",  # Empty/whitespace
            "provider": "tavily",
            "credibility_score": 0.8,
            "relevance_score": 0.7,
            "confidence": 0.75,
            "subtopic_name": "Test Subtopic",
            "claim": "Test claim here",
            "supporting_text": "Supporting evidence text",
            "source_domain": "example.com",
            "is_primary_source": False,
            "collected_at": "2024-01-01T12:00:00Z",
            "stance": "neutral"
        }
        
        with pytest.raises(ValueError, match="snippet cannot be empty"):
            validate_evidence_dict(invalid_card)
    
    def test_validates_score_bounds(self):
        invalid_card = {
            "id": "12345678-1234-1234-1234-123456789012",
            "title": "Test Article",
            "url": "https://example.com",
            "snippet": "Test content",
            "provider": "tavily",
            "credibility_score": 1.5,  # Out of bounds
            "relevance_score": 0.7,
            "confidence": 0.75,
            "subtopic_name": "Test Subtopic",
            "claim": "Test claim here",
            "supporting_text": "Supporting evidence text",
            "source_domain": "example.com",
            "is_primary_source": False,
            "collected_at": "2024-01-01T12:00:00Z",
            "stance": "neutral"
        }
        
        with pytest.raises(ValueError, match="validation failed"):
            validate_evidence_dict(invalid_card)


class TestAggregates:
    """Test aggregation functions"""
    
    def test_canonical_domain(self):
        assert canonical_domain("https://www.example.com/page") == "example.com"
        assert canonical_domain("http://subdomain.example.org:8080") == "subdomain.example.org"
        assert canonical_domain("https://WWW.TEST.COM") == "test.com"
        assert canonical_domain("invalid-url") == "unknown"
    
    def test_source_quality_calculation(self):
        # Create mock cards
        cards = [
            Mock(
                url="https://trusted.gov/article1",
                credibility_score=0.9,
                relevance_score=0.8,
                claim="Climate change impacts",
                provider="tavily",
                date=datetime(2025, 1, 15)
            ),
            Mock(
                url="https://trusted.gov/article2",
                credibility_score=0.85,
                relevance_score=0.9,
                claim="Economic forecast 2025",
                provider="brave",
                date=datetime(2025, 1, 10)
            ),
            Mock(
                url="https://news.com/story",
                credibility_score=0.6,
                relevance_score=0.7,
                claim="Climate change impacts",  # Same claim, different source
                provider="tavily",
                date=None
            )
        ]
        
        results = source_quality(cards)
        
        # Check structure
        assert len(results) == 2  # Two unique domains
        
        # Check trusted.gov metrics
        gov_result = next(r for r in results if r["domain"] == "trusted.gov")
        assert gov_result["total_cards"] == 2
        assert gov_result["unique_claims"] == 2
        assert 0.85 <= gov_result["avg_credibility"] <= 0.9
        assert gov_result["providers"] == ["brave", "tavily"] or gov_result["providers"] == ["tavily", "brave"]
    
    def test_triangulation(self):
        cards = [
            Mock(
                claim="AI will transform healthcare",
                url="https://source1.com",
                provider="tavily",
                date="2025-01-01",
                stance="neutral"
            ),
            Mock(
                claim="AI will transform healthcare",
                url="https://source2.org",
                provider="brave",
                date="2025-01-02",
                stance="supports"
            ),
            Mock(
                claim="Quantum computing breakthrough",
                url="https://source3.edu",
                provider="serper",
                date="2025-01-03",
                stance="neutral"
            )
        ]
        
        results = triangulate_claims(cards)
        
        # Check AI claim is triangulated (2 sources)
        ai_claim = results["ai will transform healthcare"]
        assert ai_claim["is_triangulated"] == True
        assert ai_claim["num_sources"] == 2
        assert ai_claim["num_providers"] == 2
        
        # Check quantum claim is not triangulated (1 source)
        quantum_claim = results["quantum computing breakthrough"]
        assert quantum_claim["is_triangulated"] == False
        assert quantum_claim["num_sources"] == 1


class TestOrchestrator:
    """Test orchestrator enhancements"""
    
    def test_dedup_removes_duplicates(self):
        from research_system.orchestrator import Orchestrator, OrchestratorSettings
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = OrchestratorSettings(
                topic="test",
                depth="standard",
                output_dir=Path(tmpdir),
                strict=False
            )
            
            orch = Orchestrator(settings)
            
            # Create cards with duplicate URLs
            cards = [
                EvidenceCard(
                    url="https://example.com/article",
                    title="Article 1",
                    snippet="Content 1",
                    provider="tavily",
                    claim="Test claim",
                    supporting_text="Support",
                    source_url="https://example.com/article",
                    source_title="Article 1",
                    source_domain="example.com"
                ),
                EvidenceCard(
                    url="https://example.com/article",  # Duplicate
                    title="Article 1 Duplicate",
                    snippet="Content 1 again",
                    provider="brave",
                    claim="Test claim",
                    supporting_text="Support",
                    source_url="https://example.com/article",
                    source_title="Article 1 Duplicate",
                    source_domain="example.com"
                ),
                EvidenceCard(
                    url="https://different.com/page",
                    title="Different Article",
                    snippet="Different content",
                    provider="serper",
                    claim="Different claim",
                    supporting_text="Different",
                    source_url="https://different.com/page",
                    source_title="Different Article",
                    source_domain="different.com"
                )
            ]
            
            deduped = orch._dedup(cards)
            assert len(deduped) == 2
            urls = [c.url for c in deduped]
            assert "https://example.com/article" in urls
            assert "https://different.com/page" in urls
    
    def test_relevance_filter(self):
        from research_system.orchestrator import Orchestrator, OrchestratorSettings
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = OrchestratorSettings(
                topic="test",
                depth="standard",
                output_dir=Path(tmpdir),
                strict=False
            )
            
            orch = Orchestrator(settings)
            
            cards = [
                Mock(relevance_score=0.8),
                Mock(relevance_score=0.6),
                Mock(relevance_score=0.4),
                Mock(relevance_score=0.2)
            ]
            
            # Filter with threshold 0.5
            filtered = orch._filter_relevance(cards, threshold=0.5)
            assert len(filtered) == 2
            assert all(c.relevance_score >= 0.5 for c in filtered)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])