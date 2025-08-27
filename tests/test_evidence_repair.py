"""Test evidence repair and validation enhancements."""
import pytest
from research_system.tools.evidence_io import _repair_minimal, validate_evidence_dict


class TestEvidenceRepair:
    """Test evidence repair chain functionality."""
    
    def test_repairs_empty_snippet_from_quote(self):
        """Test snippet repair from best_quote."""
        doc = {
            "id": "test1",
            "title": "Test Title",
            "url": "https://example.com",
            "snippet": "",  # Empty snippet
            "best_quote": "Tourism arrivals reached 1.5 billion in 2024",
            "provider": "test",
            "credibility_score": 0.8,
            "relevance_score": 0.7,
            "confidence": 0.75
        }
        
        repaired = _repair_minimal(doc)
        assert repaired["snippet"] == "Tourism arrivals reached 1.5 billion in 2024"
        assert repaired["supporting_text"] == "Tourism arrivals reached 1.5 billion in 2024"
    
    def test_repairs_empty_snippet_from_quotes_list(self):
        """Test snippet repair from quotes list."""
        doc = {
            "id": "test2",
            "title": "Test Title",
            "url": "https://example.com",
            "snippet": "",
            "quotes": [
                "Short",  # Too short
                "Global tourism recovery showed strong momentum in Q1 2025 with 15% growth"
            ],
            "provider": "test",
            "credibility_score": 0.8,
            "relevance_score": 0.7,
            "confidence": 0.75
        }
        
        repaired = _repair_minimal(doc)
        assert "Global tourism recovery" in repaired["snippet"]
    
    def test_repairs_empty_snippet_from_abstract(self):
        """Test snippet repair from abstract."""
        doc = {
            "id": "test3",
            "title": "Test Title",
            "url": "https://example.com",
            "snippet": "",
            "abstract": "This study examines tourism recovery patterns across regions",
            "provider": "test",
            "credibility_score": 0.8,
            "relevance_score": 0.7,
            "confidence": 0.75
        }
        
        repaired = _repair_minimal(doc)
        assert repaired["snippet"] == "This study examines tourism recovery patterns across regions"
    
    def test_repairs_empty_snippet_from_title(self):
        """Test snippet repair falls back to title."""
        doc = {
            "id": "test4",
            "title": "Tourism Recovery Report 2025",
            "url": "https://example.com",
            "snippet": "",
            "provider": "test",
            "credibility_score": 0.8,
            "relevance_score": 0.7,
            "confidence": 0.75
        }
        
        repaired = _repair_minimal(doc)
        assert repaired["snippet"] == "Tourism Recovery Report 2025"
    
    def test_repairs_whitespace_only_snippet(self):
        """Test repair handles whitespace-only snippets."""
        doc = {
            "id": "test5",
            "title": "Test Title",
            "url": "https://example.com",
            "snippet": "   \n\t  ",  # Whitespace only
            "supporting_text": "Actual content here",
            "provider": "test",
            "credibility_score": 0.8,
            "relevance_score": 0.7,
            "confidence": 0.75
        }
        
        repaired = _repair_minimal(doc)
        assert repaired["snippet"] == "Actual content here"
    
    def test_truncates_long_snippets(self):
        """Test snippet truncation to 500 chars."""
        long_text = "x" * 1000
        doc = {
            "id": "test6",
            "title": "Test",
            "url": "https://example.com",
            "snippet": "",
            "best_quote": long_text,
            "provider": "test",
            "credibility_score": 0.8,
            "relevance_score": 0.7,
            "confidence": 0.75
        }
        
        repaired = _repair_minimal(doc)
        assert len(repaired["snippet"]) == 500
    
    def test_validation_accepts_repaired_snippets(self):
        """Test validation passes after repair."""
        doc = {
            "id": "test7",
            "title": "Test Title",
            "url": "https://example.com",
            "snippet": "",  # Empty
            "best_quote": "Valid content",
            "provider": "tavily",  # Must be from enum
            "source_domain": "example.com",
            "credibility_score": 0.8,
            "relevance_score": 0.7,
            "confidence": 0.75,
            "collected_at": "2025-01-01T00:00:00Z",
            "claim": "Test claim",
            "supporting_text": "Test supporting text",
            "subtopic_name": "Test Subtopic",
            "is_primary_source": False
        }
        
        repaired = _repair_minimal(doc)
        # Should not raise after repair
        validate_evidence_dict(repaired)
    
    def test_handles_missing_all_fields(self):
        """Test graceful handling when all text fields missing."""
        doc = {
            "id": "test8",
            "url": "https://example.com",
            "provider": "test",
            "credibility_score": 0.8,
            "relevance_score": 0.7,
            "confidence": 0.75
        }
        
        repaired = _repair_minimal(doc)
        assert repaired["snippet"] == "Evidence snippet unavailable"
        assert repaired["claim"] == "Evidence snippet unavailable"