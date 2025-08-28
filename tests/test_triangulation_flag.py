"""Tests for triangulation flag on EvidenceCard model."""

import pytest
from research_system.models import EvidenceCard
from research_system.selection.domain_balance import enforce_cap, enforce_domain_cap, BalanceConfig
from types import SimpleNamespace


def test_evidence_card_has_triangulated_flag():
    """Test that EvidenceCard model includes is_triangulated field."""
    card = EvidenceCard(
        id="test-1",
        url="https://example.com/article",
        title="Test Article",
        snippet="Test content",
        provider="test",
        credibility_score=0.8,
        relevance_score=0.7
    )
    
    # Field should exist and default to False
    assert hasattr(card, 'is_triangulated')
    assert card.is_triangulated is False
    
    # Should be settable
    card.is_triangulated = True
    assert card.is_triangulated is True


def test_evidence_card_has_cluster_fields():
    """Test that EvidenceCard includes clustering fields."""
    card = EvidenceCard(
        id="test-2",
        url="https://example.com/article2",
        title="Test Article 2",
        snippet="Test content 2",
        provider="test",
        credibility_score=0.8,
        relevance_score=0.7
    )
    
    # Check clustering fields exist
    assert hasattr(card, 'cluster_id')
    assert hasattr(card, 'family')
    
    # Should default to None
    assert card.cluster_id is None
    assert card.family is None
    
    # Should be settable
    card.cluster_id = "cluster-1"
    card.family = "news"
    assert card.cluster_id == "cluster-1"
    assert card.family == "news"


def test_triangulated_cards_prioritized_in_capping():
    """Test that triangulated cards are preserved during domain capping."""
    # Create test cards
    cards = []
    for i in range(10):
        card = EvidenceCard(
            id=f"card-{i}",
            url=f"https://example.com/article{i}",
            title=f"Article {i}",
            snippet=f"Content {i}",
            provider="test",
            source_domain="example.com",
            credibility_score=0.5 + (i * 0.05),  # Varying credibility
            relevance_score=0.7
        )
        # Mark some as triangulated
        card.is_triangulated = (i % 3 == 0)  # Cards 0, 3, 6, 9 are triangulated
        cards.append(card)
    
    # Apply domain cap (should keep triangulated cards first)
    cfg = BalanceConfig(cap=0.4, min_cards=4)  # Allow 40% from one domain
    capped, kept = enforce_cap(cards, cfg)
    
    # With 10 cards and 40% cap, should keep 4 cards
    assert len(capped) == 4
    
    # All triangulated cards should be kept (there are 4 of them)
    triangulated_ids = {"card-0", "card-3", "card-6", "card-9"}
    kept_ids = {c.id for c in capped}
    assert triangulated_ids.issubset(kept_ids), "All triangulated cards should be preserved"


def test_enforce_domain_cap_with_triangulation():
    """Test enforce_domain_cap prioritizes triangulated cards."""
    # Create cards from multiple domains
    cards = []
    domains = ["example.com", "test.org", "sample.net"]
    
    for domain_idx, domain in enumerate(domains):
        for i in range(6):  # 6 cards per domain
            card = EvidenceCard(
                id=f"{domain}-{i}",
                url=f"https://{domain}/article{i}",
                title=f"Article {i} from {domain}",
                snippet=f"Content {i}",
                provider="test",
                source_domain=domain,
                credibility_score=0.5 + (i * 0.05),
                relevance_score=0.7
            )
            # Mark first 2 cards from each domain as triangulated
            card.is_triangulated = (i < 2)
            cards.append(card)
    
    # Apply 30% cap to ensure we keep enough cards per domain (18 * 0.30 = 5.4 cards per domain max)
    capped = enforce_domain_cap(cards, cap=0.30, use_families=False)
    
    # Check that triangulated cards are prioritized
    total_triangulated_before = sum(1 for c in cards if c.is_triangulated)
    total_triangulated_after = sum(1 for c in capped if c.is_triangulated)
    
    # At least some triangulated cards should be kept
    assert total_triangulated_after > 0, "Should keep at least some triangulated cards"
    
    # For each domain that has cards, check if triangulated ones are prioritized
    for domain in domains:
        domain_cards = [c for c in capped if c.source_domain == domain]
        if len(domain_cards) > 0:
            # Get the IDs to check ordering
            kept_ids = [c.id for c in domain_cards]
            # Check if triangulated cards (id ending in -0 or -1) appear in the kept cards
            triangulated_ids = [f"{domain}-0", f"{domain}-1"]
            
            # If we kept any cards from this domain, triangulated ones should be prioritized
            # Note: With credibility sorting, higher credibility cards might override triangulation
            # This is the actual behavior we're testing
            triangulated_kept = [id for id in triangulated_ids if id in kept_ids]
            
            # At minimum, if we kept 2+ cards, at least one should be triangulated
            if len(domain_cards) >= 2:
                assert len(triangulated_kept) >= 1, \
                    f"Should keep at least one triangulated card from {domain} when keeping multiple cards"


def test_jsonl_output_includes_triangulation():
    """Test that JSONL output includes triangulation fields."""
    card = EvidenceCard(
        id="test-3",
        url="https://example.com/article3",
        title="Test Article 3",
        snippet="Test content 3",
        provider="test",
        credibility_score=0.8,
        relevance_score=0.7,
        is_triangulated=True,
        cluster_id="cluster-123",
        family="academic"
    )
    
    jsonl_dict = card.to_jsonl_dict()
    
    # Check that triangulation fields are included in output
    assert "is_triangulated" in jsonl_dict
    assert jsonl_dict["is_triangulated"] is True
    assert "cluster_id" in jsonl_dict
    assert jsonl_dict["cluster_id"] == "cluster-123"
    assert "family" in jsonl_dict
    assert jsonl_dict["family"] == "academic"


def test_boolean_triangulation_values():
    """Test that is_triangulated uses boolean values correctly."""
    card = EvidenceCard(
        id="test-4",
        url="https://example.com/article4",
        title="Test Article 4",
        snippet="Test content 4",
        provider="test",
        credibility_score=0.8,
        relevance_score=0.7
    )
    
    # Should handle boolean assignment
    card.is_triangulated = True
    assert card.is_triangulated is True
    assert isinstance(card.is_triangulated, bool)
    
    card.is_triangulated = False
    assert card.is_triangulated is False
    assert isinstance(card.is_triangulated, bool)
    
    # Should not raise error
    card.is_triangulated = bool(1)  # Explicit bool conversion
    assert card.is_triangulated is True


def test_model_validation_with_triangulation():
    """Test that model validation works with new fields."""
    # Should create successfully with all fields
    card = EvidenceCard(
        id="test-5",
        url="https://example.com/article5",
        title="Test Article 5",
        snippet="Test content 5",
        provider="test",
        credibility_score=0.8,
        relevance_score=0.7,
        is_triangulated=True,
        cluster_id="cluster-456",
        family="news"
    )
    
    # Verify all fields are set correctly
    assert card.id == "test-5"
    assert card.is_triangulated is True
    assert card.cluster_id == "cluster-456"
    assert card.family == "news"
    
    # Model dump should include new fields
    dumped = card.model_dump()
    assert "is_triangulated" in dumped
    assert "cluster_id" in dumped
    assert "family" in dumped


if __name__ == "__main__":
    pytest.main([__file__, "-v"])