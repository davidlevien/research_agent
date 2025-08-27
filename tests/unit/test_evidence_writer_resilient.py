"""Unit tests for resilient evidence writer."""

import pytest
import json
from pathlib import Path
from research_system.tools.evidence_io import write_jsonl, _repair_minimal
from research_system.models import EvidenceCard


def test_writer_skips_invalid_and_returns_counts(tmp_path):
    """Test that writer skips invalid cards and returns correct counts."""
    cards = [
        # Valid card
        EvidenceCard(
            title="Valid card",
            url="https://example.com/valid",
            snippet="This is a valid snippet",
            provider="brave",
            credibility_score=0.5,
            relevance_score=0.5,
            confidence=0.5
        ),
        # Invalid card with empty supporting_text that can't be repaired
        EvidenceCard(
            title="",  # Empty title
            url="https://doi.org/10.18111/xxx",
            snippet="",  # Empty snippet
            provider="serpapi",
            credibility_score=0.5,
            relevance_score=0.5,
            confidence=0.5,
            supporting_text=""  # Empty supporting_text
        ),
        # Another valid card
        EvidenceCard(
            title="Another valid",
            url="https://example.com/valid2",
            snippet="Another snippet",
            provider="tavily",
            credibility_score=0.6,
            relevance_score=0.6,
            confidence=0.6
        )
    ]
    
    # Write with skip_invalid=True
    output_path = tmp_path / "evidence.jsonl"
    errors_path = tmp_path / "errors.jsonl"
    
    ok, bad = write_jsonl(
        str(output_path),
        cards,
        skip_invalid=True,
        errors_path=str(errors_path)
    )
    
    # Should have 2 successful, 1 failed
    assert ok == 2
    assert bad == 1
    
    # Check output file has 2 lines
    with open(output_path) as f:
        lines = f.readlines()
    assert len(lines) == 2
    
    # Check error file has 1 line
    with open(errors_path) as f:
        error_lines = f.readlines()
    assert len(error_lines) == 1
    
    # Parse error and verify it's the DOI card
    error = json.loads(error_lines[0])
    assert "10.18111" in error["url"]


def test_repair_minimal_fixes_empty_fields():
    """Test that _repair_minimal properly fixes empty fields."""
    # Test with empty supporting_text
    doc = {
        "title": "Test title",
        "snippet": "Test snippet",
        "supporting_text": "",
        "claim": ""
    }
    
    repaired = _repair_minimal(doc)
    
    # Should use snippet for supporting_text
    assert repaired["supporting_text"] == "Test snippet"
    # Should use title for claim
    assert repaired["claim"] == "Test title"
    
    # Test with all empty
    doc2 = {
        "title": "",
        "snippet": "",
        "supporting_text": "",
        "claim": ""
    }
    
    repaired2 = _repair_minimal(doc2)
    
    # Should fill empty fields with fallback values
    assert repaired2["snippet"] == "Evidence snippet unavailable"
    assert repaired2["supporting_text"] == "Evidence snippet unavailable"
    assert repaired2["claim"] == "Evidence snippet unavailable"[:200]
    
    # Test with only title
    doc3 = {
        "title": "Only title",
        "snippet": "",
        "supporting_text": "",
        "claim": ""
    }
    
    repaired3 = _repair_minimal(doc3)
    
    # Should use title for both
    assert repaired3["supporting_text"] == "Only title"
    assert repaired3["claim"] == "Only title"


def test_writer_handles_mixed_validity(tmp_path):
    """Test writer handles mix of valid and invalid cards gracefully."""
    cards = []
    
    # Add 10 valid cards
    for i in range(10):
        cards.append(EvidenceCard(
            title=f"Valid card {i}",
            url=f"https://example.com/{i}",
            snippet=f"Snippet {i}",
            provider="brave",
            credibility_score=0.5,
            relevance_score=0.5,
            confidence=0.5
        ))
    
    # Add 3 problematic cards
    cards.append(EvidenceCard(
        title="",
        url="https://bad1.com",
        snippet="",
        provider="test",
        credibility_score=0.5,
        relevance_score=0.5,
        confidence=0.5,
        supporting_text=""
    ))
    
    cards.append(EvidenceCard(
        title="Missing snippet",
        url="https://bad2.com",
        snippet="",  # This will be caught by validation
        provider="test",
        credibility_score=0.5,
        relevance_score=0.5,
        confidence=0.5
    ))
    
    # Write with skip_invalid
    output_path = tmp_path / "mixed.jsonl"
    ok, bad = write_jsonl(str(output_path), cards, skip_invalid=True)
    
    # Should have handled the mix properly
    assert ok >= 10  # At least the 10 valid ones
    assert bad <= 3  # At most 3 bad ones
    assert ok + bad == len(cards)


def test_writer_raises_when_skip_invalid_false(tmp_path):
    """Test that writer raises exception when skip_invalid=False."""
    cards = [
        EvidenceCard(
            title="",
            url="https://bad.com",
            snippet="",
            provider="brave",
            credibility_score=0.5,
            relevance_score=0.5,
            confidence=0.5,
            supporting_text=""
        )
    ]
    
    output_path = tmp_path / "fail.jsonl"
    
    # Should raise ValueError when skip_invalid=False
    with pytest.raises(ValueError):
        write_jsonl(str(output_path), cards, skip_invalid=False)