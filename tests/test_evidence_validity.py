"""Tests for evidence validity invariants."""

import pytest
from research_system.models import EvidenceCard
from research_system.orchestrator import Orchestrator, OrchestratorSettings
from pathlib import Path
import tempfile


class TestEvidenceValidity:
    """Test evidence validity invariants."""
    
    def test_snippet_never_empty(self):
        """Test that snippets are never empty."""
        # Create orchestrator with test settings
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = OrchestratorSettings(
                topic="test topic",
                depth="rapid",
                output_dir=Path(tmpdir),
                strict=False
            )
            orch = Orchestrator(settings)
            
            # Test the snippet helper with various inputs
            
            # Normal case
            snippet = orch._ensure_snippet("Valid snippet", "Title", "http://example.com")
            assert snippet == "Valid snippet"
            assert len(snippet) > 0
            
            # Empty snippet
            snippet = orch._ensure_snippet("", "Title", "http://example.com")
            assert snippet == "Content: Title"
            assert len(snippet) > 0
            
            # None snippet
            snippet = orch._ensure_snippet(None, "Title", "http://example.com")
            assert snippet == "Content: Title"
            assert len(snippet) > 0
            
            # Whitespace only
            snippet = orch._ensure_snippet("   ", "Title", "http://example.com")
            assert snippet == "Content: Title"
            assert len(snippet) > 0
            
            # No title either
            snippet = orch._ensure_snippet("", "", "http://example.com")
            assert snippet == "Source content from example.com"
            assert len(snippet) > 0
            
            # Nothing provided
            snippet = orch._ensure_snippet("", "", "")
            assert snippet == "Content available at source"
            assert len(snippet) > 0
    
    def test_evidence_card_validation(self):
        """Test evidence card validation."""
        # Valid card
        card = EvidenceCard(
            id="test-id",
            title="Test Title",
            url="http://example.com",
            snippet="Test snippet content",
            provider="test",
            credibility_score=0.8,
            relevance_score=0.7,
            confidence=0.6
        )
        
        # Check required fields
        assert card.id
        assert card.title
        assert card.url
        assert card.snippet
        assert len(card.snippet) > 0
        
    def test_doi_landing_page_fallback(self):
        """Test that DOI landing pages with blocked content produce non-empty snippets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = OrchestratorSettings(
                topic="test",
                depth="rapid",
                output_dir=Path(tmpdir),
                strict=False
            )
            orch = Orchestrator(settings)
            
            # Simulate a DOI landing page with no content
            snippet = orch._ensure_snippet(
                None,
                "A Systematic Review of Machine Learning Applications",
                "https://doi.org/10.1234/example"
            )
            
            assert snippet
            assert len(snippet) > 0
            assert "Systematic Review" in snippet
    
    def test_multiple_evidence_cards_all_valid(self):
        """Test that all evidence cards in a collection have valid snippets."""
        cards = []
        
        # Create cards with various snippet states
        test_cases = [
            ("Good snippet", "Title 1", "http://example1.com"),
            ("", "Title 2", "http://example2.com"),
            (None, "Title 3", "http://example3.com"),
            ("   ", "Title 4", "http://example4.com"),
            ("Another good snippet", "", "http://example5.com")
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = OrchestratorSettings(
                topic="test",
                depth="rapid",
                output_dir=Path(tmpdir),
                strict=False
            )
            orch = Orchestrator(settings)
            
            for snippet_in, title, url in test_cases:
                snippet_out = orch._ensure_snippet(snippet_in, title, url)
                
                card = EvidenceCard(
                    id=f"test-{len(cards)}",
                    title=title or "Generated Title",
                    url=url,
                    snippet=snippet_out,
                    provider="test",
                    credibility_score=0.8,
                    relevance_score=0.7,
                    confidence=0.6
                )
                cards.append(card)
            
            # Validate all cards have non-empty snippets
            for card in cards:
                assert card.snippet, f"Card {card.id} has empty snippet"
                assert len(card.snippet.strip()) > 0, f"Card {card.id} has whitespace-only snippet"
    
    def test_snippet_length_limits(self):
        """Test that snippets respect length limits."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = OrchestratorSettings(
                topic="test",
                depth="rapid",
                output_dir=Path(tmpdir),
                strict=False
            )
            orch = Orchestrator(settings)
            
            # Very long title
            long_title = "A" * 500
            snippet = orch._ensure_snippet("", long_title, "http://example.com")
            assert len(snippet) <= 280  # Should be truncated
            assert snippet.startswith("Content: ")
            
            # Very long URL
            long_url = "http://example.com/" + "path/" * 100
            snippet = orch._ensure_snippet("", "", long_url)
            assert len(snippet) <= 280
            assert "example.com" in snippet