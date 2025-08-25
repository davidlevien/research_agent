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
    assert counts["worldbank.org"] <= 4
    assert counts["imf.org"] <= 4
    assert len(kept) == 8  # 4 + 4

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
    """Test that enforce_cap maintains stable ordering."""
    cards = [
        SimpleNamespace(source_domain="a.org", id=1),
        SimpleNamespace(source_domain="b.org", id=2),
        SimpleNamespace(source_domain="a.org", id=3),
        SimpleNamespace(source_domain="b.org", id=4),
        SimpleNamespace(source_domain="a.org", id=5),
    ]
    
    kept, _ = enforce_cap(cards, BalanceConfig(cap=0.5, min_cards=1))
    
    # Should keep first 2 from each domain
    ids = [c.id for c in kept]
    assert ids == [1, 2, 3, 4]  # Stable order preserved

def test_primary_pool():
    """Test that primary domains are recognized."""
    from research_system.selection.domain_balance import PRIMARY_POOL
    
    assert "worldbank.org" in PRIMARY_POOL
    assert "oecd.org" in PRIMARY_POOL
    assert "imf.org" in PRIMARY_POOL
    assert "random.com" not in PRIMARY_POOL