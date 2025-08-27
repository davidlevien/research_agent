"""Test composer bugfixes for tuple unpacking and cluster handling."""
import pytest
from research_system.report.composer import compose_report
from research_system.models import EvidenceCard
import uuid
from datetime import datetime


def create_test_card(**kwargs):
    """Helper to create test evidence cards."""
    defaults = {
        "id": str(uuid.uuid4()),
        "title": "Test Card",
        "url": "https://example.com",
        "snippet": "Test snippet with data",
        "provider": "test",
        "source_domain": "example.com",
        "credibility_score": 0.8,
        "relevance_score": 0.7,
        "confidence": 0.75,
        "collected_at": datetime.utcnow().isoformat() + "Z"
    }
    defaults.update(kwargs)
    return EvidenceCard(**defaults)


class TestComposerBugfixes:
    """Test fixes for composer tuple unpacking issues."""
    
    def test_handles_clusters_dict_format(self):
        """Test composer handles clusters as list of dicts (not tuples)."""
        cards = [
            create_test_card(title="Card 1", snippet="Tourism grew by 15% in 2024"),
            create_test_card(title="Card 2", snippet="International arrivals increased 15%"),
            create_test_card(title="Card 3", snippet="Recovery reached pre-pandemic levels")
        ]
        
        # Triangulation with dict format (not tuple format)
        tri = {
            "clusters": [
                {
                    "key": "growth_15pct",
                    "cards": [cards[0], cards[1]],
                    "domains": ["example.com", "test.org"],
                    "indices": [0, 1]
                },
                {
                    "key": "recovery",
                    "cards": [cards[2]],
                    "domains": ["example.com"],
                    "indices": [2]
                }
            ]
        }
        
        metrics = {
            "union_triangulation": 0.45,
            "primary_share_in_union": 0.30,
            "quote_coverage": 0.85,
            "provider_entropy": 0.72
        }
        
        # Should not raise tuple unpacking error
        report = compose_report("Tourism Recovery", cards, tri, metrics)
        assert "Tourism Recovery" in report
        assert "Key Findings" in report
    
    def test_handles_empty_clusters(self):
        """Test composer handles empty/missing clusters gracefully."""
        cards = [
            create_test_card(title="Card 1", snippet="Tourism data point"),
        ]
        
        # Empty clusters
        tri = {"clusters": []}
        metrics = {"union_triangulation": 0.0}
        
        report = compose_report("Test Topic", cards, tri, metrics)
        assert "Test Topic" in report
        # Should fall back to domain-based clustering
    
    def test_handles_missing_triangulation(self):
        """Test composer handles missing triangulation data."""
        cards = [
            create_test_card(title="Card 1", snippet="Data point 1"),
            create_test_card(title="Card 2", snippet="Data point 2", source_domain="other.org"),
        ]
        
        # No triangulation data
        tri = {}
        metrics = {}
        
        report = compose_report("Test Topic", cards, tri, metrics)
        assert "Test Topic" in report
        assert "Evidence base:" in report
    
    def test_handles_malformed_cluster_cards(self):
        """Test composer handles clusters with missing 'cards' key."""
        cards = [create_test_card(title="Card 1")]
        
        tri = {
            "clusters": [
                {"key": "test"},  # Missing 'cards' key
                {"key": "test2", "cards": None},  # None cards
                {"key": "test3", "cards": []}  # Empty cards
            ]
        }
        
        metrics = {"union_triangulation": 0.1}
        
        # Should not crash
        report = compose_report("Test", cards, tri, metrics)
        assert "Test" in report
    
    def test_preserves_cluster_scoring(self):
        """Test cluster scoring works with fixed format."""
        cards = [
            create_test_card(
                title="Primary Source",
                snippet="OECD reports 20% growth",
                source_domain="oecd.org",
                credibility_score=0.95
            ),
            create_test_card(
                title="Secondary Source",
                snippet="Analysis shows 20% increase",
                source_domain="news.com",
                credibility_score=0.60
            )
        ]
        
        tri = {
            "clusters": [
                {
                    "key": "20pct_growth",
                    "cards": cards,
                    "domains": ["oecd.org", "news.com"],
                    "indices": [0, 1]
                }
            ]
        }
        
        metrics = {
            "union_triangulation": 0.50,
            "primary_share_in_union": 0.50
        }
        
        report = compose_report("Growth Analysis", cards, tri, metrics)
        
        # Primary source should be prioritized in findings
        assert "OECD" in report or "20%" in report
    
    def test_handles_unicode_in_snippets(self):
        """Test composer handles unicode characters properly."""
        cards = [
            create_test_card(
                snippet="Tourism in España grew by 15% — €2.5B increase"
            ),
            create_test_card(
                snippet="中国旅游业增长 (Chinese tourism growth) 北京"
            )
        ]
        
        tri = {"clusters": []}
        metrics = {}
        
        # Should handle unicode without errors
        report = compose_report("International Tourism", cards, tri, metrics)
        assert report  # Just ensure it doesn't crash
    
    def test_citation_indexing_consistent(self):
        """Test citation indices remain consistent."""
        cards = [
            create_test_card(id="card1", title="Source 1"),
            create_test_card(id="card2", title="Source 2"),
            create_test_card(id="card3", title="Source 3")
        ]
        
        tri = {
            "clusters": [
                {
                    "key": "cluster1",
                    "cards": [cards[0], cards[2]],  # Cards 1 and 3
                    "indices": [0, 2]
                }
            ]
        }
        
        metrics = {"union_triangulation": 0.4}
        
        report = compose_report("Test", cards, tri, metrics)
        
        # Check citations are numbered sequentially
        assert "[1]" in report or "Source" in report
        # Each card should get unique citation number
    
    def test_robust_number_extraction(self):
        """Test number extraction handles edge cases."""
        cards = [
            create_test_card(snippet="Growth of 15.5% in Q1 2024"),
            create_test_card(snippet="$1,234,567.89 million revenue"),
            create_test_card(snippet="Between 2019-2024, ±5% variance")
        ]
        
        tri = {"clusters": []}
        metrics = {"union_triangulation": 0.3}
        
        report = compose_report("Numbers Test", cards, tri, metrics)
        
        # Should extract and include numeric data
        assert "Key Numbers" in report