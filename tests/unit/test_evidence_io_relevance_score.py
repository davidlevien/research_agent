"""Regression test for relevance_score=0.0 validation bug."""

import pytest
from research_system.tools.evidence_io import validate_evidence_dict


def test_relevance_score_zero_is_valid():
    """Test that relevance_score=0.0 is considered valid (not missing)."""
    card = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "title": "Test Article",
        "url": "https://example.com/article",
        "snippet": "This is a test snippet with some content.",
        "provider": "tavily",
        "credibility_score": 0.75,
        "relevance_score": 0.0,  # This should be valid!
        "confidence": 0.5,
        "source_domain": "example.com",
        "is_primary_source": False,
        "claim": "Test claim",
        "claim_id": "test_claim_1",
        "supporting_text": "Supporting text",
        "subtopic_name": "test",
        "collected_at": "2025-08-24T00:00:00Z"
    }
    
    # This should NOT raise
    validate_evidence_dict(card)


def test_relevance_score_missing_is_invalid():
    """Test that actually missing relevance_score is invalid."""
    card = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "title": "Test Article",
        "url": "https://example.com/article",
        "snippet": "This is a test snippet with some content.",
        "provider": "tavily",
        "credibility_score": 0.75,
        # relevance_score is missing!
        "confidence": 0.5,
        "source_domain": "example.com",
        "is_primary_source": False,
        "claim": "Test claim",
        "claim_id": "test_claim_2",
        "supporting_text": "Supporting text",
        "subtopic_name": "test",
        "collected_at": "2025-08-24T00:00:00Z"
    }
    
    with pytest.raises(ValueError, match="validation failed"):
        validate_evidence_dict(card)


def test_all_scores_at_boundary():
    """Test boundary values for all score fields."""
    # Test 0.0 values
    card_zero = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "title": "Test",
        "url": "https://example.com",
        "snippet": "Test snippet",
        "provider": "brave",
        "credibility_score": 0.0,
        "relevance_score": 0.0,
        "confidence": 0.0,
        "source_domain": "example.com",
        "is_primary_source": False,
        "claim": "Test",
        "claim_id": "test_3",
        "supporting_text": "Test",
        "subtopic_name": "test",
        "collected_at": "2025-08-24T00:00:00Z"
    }
    validate_evidence_dict(card_zero)  # Should pass
    
    # Test 1.0 values
    card_one = dict(card_zero)
    card_one.update({
        "credibility_score": 1.0,
        "relevance_score": 1.0,
        "confidence": 1.0,
    })
    validate_evidence_dict(card_one)  # Should pass
    
    # Test out of bounds
    card_invalid = dict(card_zero)
    card_invalid["relevance_score"] = 1.1
    
    with pytest.raises(ValueError, match="validation failed"):
        validate_evidence_dict(card_invalid)