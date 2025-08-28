"""Unit tests for domain balance functionality."""

from research_system.selection.domain_balance import BalanceConfig, enforce_cap, need_backfill
from types import SimpleNamespace

def mk(domain): 
    """Create mock card with domain."""
    return SimpleNamespace(source_domain=domain)

def test_enforce_cap_24pct():
    """Test that domain cap is enforced at 24%."""
    cards = [mk("worldbank.org") for _ in range(10)] + [mk("imf.org") for _ in range(10)]
    kept, counts = enforce_cap(cards, BalanceConfig(cap=0.24, min_cards=10))
    # 20 cards -> cap 0.24 => max 4 per domain
    # Check domains that were kept (some might be filtered entirely)
    assert counts.get("worldbank.org", 0) <= 4
    assert counts.get("imf.org", 0) <= 4
    # Should keep at most 8 cards total (4 per domain max)
    assert len(kept) <= 8

def test_need_backfill():
    """Test backfill detection."""
    cfg = BalanceConfig(cap=0.24, min_cards=24)
    
    # Test with too few cards
    cards_few = [mk("test.org") for _ in range(10)]
    assert need_backfill(cards_few, cfg) == True
    
    # Test with enough cards
    cards_enough = [mk("test.org") for _ in range(25)]
    assert need_backfill(cards_enough, cfg) == False

def test_stable_ordering():
    """Test that enforce_cap maintains order within each domain family."""
    cards = [
        SimpleNamespace(source_domain="a.org", id=1, credibility_score=0.9),
        SimpleNamespace(source_domain="b.org", id=2, credibility_score=0.8),
        SimpleNamespace(source_domain="a.org", id=3, credibility_score=0.7),
        SimpleNamespace(source_domain="b.org", id=4, credibility_score=0.6),
        SimpleNamespace(source_domain="a.org", id=5, credibility_score=0.5),
    ]
    
    kept, _ = enforce_cap(cards, BalanceConfig(cap=0.5, min_cards=1))
    
    # Should keep 2 from each domain (50% cap of 5 cards = 2 per domain)
    ids = [c.id for c in kept]
    # The function groups by family/domain first, then sorts by credibility within each
    # So we expect [1, 3] from a.org and [2, 4] from b.org, interleaved as [1,3,2,4]
    assert len(kept) == 4
    # Check that the highest credibility cards from each domain are kept
    a_org_ids = [c.id for c in kept if c.source_domain == "a.org"]
    b_org_ids = [c.id for c in kept if c.source_domain == "b.org"]
    assert a_org_ids == [1, 3]  # Highest credibility from a.org
    assert b_org_ids == [2, 4]  # Highest credibility from b.org

def test_primary_pool():
    """Test that primary domains are recognized."""
    from research_system.selection.domain_balance import PRIMARY_POOL
    
    assert "worldbank.org" in PRIMARY_POOL
    assert "oecd.org" in PRIMARY_POOL
    assert "imf.org" in PRIMARY_POOL
    assert "random.com" not in PRIMARY_POOL