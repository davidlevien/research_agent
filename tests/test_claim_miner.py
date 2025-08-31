"""Tests for claim mining from text."""

import pytest
from research_system.extraction.claim_miner import mine_claims, normalize_num
from research_system.extraction.claims import ClaimKey

def test_mine_arrivals_pct_qtr():
    """Test mining percentage claims with quarter."""
    text = "International tourist arrivals increased by 5% in Q1 2025, reaching 300 million."
    claims = mine_claims(text, "https://unwto.org/barometer", is_primary=True)
    
    assert len(claims) >= 1
    
    # Find the percentage claim
    pct_claim = next((c for c in claims if c.value == 5.0), None)
    assert pct_claim is not None
    assert pct_claim.key.metric == "international_tourist_arrivals"
    assert pct_claim.key.period == "2025-Q1"
    assert pct_claim.key.unit == "percent"
    assert pct_claim.is_primary == True

def test_mine_absolute_number():
    """Test mining absolute number claims."""
    text = "Tourism jobs reached 12.5 million in 2024, a record high."
    claims = mine_claims(text, "https://wttc.org/research")
    
    jobs_claim = next((c for c in claims if "jobs" in c.key.metric), None)
    assert jobs_claim is not None
    assert jobs_claim.value == 12.5
    assert jobs_claim.key.period == "2024"
    assert jobs_claim.key.unit == "value"

def test_mine_with_geo_hint():
    """Test geographic hint in claim mining."""
    text = "Tourist arrivals grew by 8% in Q2 2024."
    claims = mine_claims(text, "https://visitbritain.org", geo_hint="GBR")
    
    assert len(claims) >= 1
    claim = claims[0]
    assert claim.key.geo == "GBR"

def test_mine_detects_geography():
    """Test automatic geography detection."""
    text = "United States tourism revenue increased by 6% in 2024."
    claims = mine_claims(text, "https://travel.state.gov")
    
    usa_claim = next((c for c in claims if c.key.geo == "USA"), None)
    assert usa_claim is not None

def test_normalize_num():
    """Test number normalization."""
    assert normalize_num("1,234.56") == 1234.56
    assert normalize_num("1 234.56") == 1234.56
    assert normalize_num("-42") == -42.0

def test_mine_multiple_claims():
    """Test extracting multiple claims from text."""
    text = """
    International tourist arrivals increased by 5% in Q1 2025.
    Hotel occupancy reached 75% in the same period.
    Tourism revenue grew by 8% year-over-year.
    """
    claims = mine_claims(text, "https://unwto.org/report")
    
    # Should find multiple distinct claims
    metrics = set(c.key.metric for c in claims)
    assert len(metrics) >= 2  # At least arrivals and occupancy/revenue

def test_no_claims_without_temporal():
    """Test that claims without temporal context are skipped."""
    text = "Tourism is an important industry contributing 10% to GDP."
    claims = mine_claims(text, "https://example.com")
    
    # Without a year/quarter, this shouldn't produce a claim
    assert len(claims) == 0

def test_quote_span_truncation():
    """Test that long quotes are truncated."""
    long_text = "Tourism revenue increased by 5% in 2024. " + "x" * 500
    claims = mine_claims(long_text, "https://example.com")
    
    if claims:
        assert len(claims[0].quote_span) <= 320