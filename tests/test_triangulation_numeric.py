"""Tests for numeric triangulation with tolerances."""

import pytest
from research_system.extraction.claims import Claim, ClaimKey
from research_system.triangulation.numeric import triangulate, _agree, find_contradictions

def test_triangulate_agreement():
    """Test triangulation with agreeing values."""
    key = ClaimKey(metric="international_tourist_arrivals", unit="percent", period="2025-Q1", geo="WORLD")
    
    # Create claims with similar values (within tolerance)
    claim1 = Claim(key=key, value=5.0, source_url="https://unwto.org", is_primary=True, source_domain="unwto.org")
    claim2 = Claim(key=key, value=5.1, source_url="https://wttc.org", is_primary=True, source_domain="wttc.org")
    claim3 = Claim(key=key, value=9.0, source_url="https://blog.com", is_primary=False, source_domain="blog.com")
    
    result = triangulate([claim1, claim2, claim3])
    
    assert key in result
    grp = result[key]
    
    # Consensus should be around 5.1 (median)
    assert 5.0 <= grp["consensus"] <= 5.2
    
    # Two sources should agree (within 3% tolerance for arrivals)
    assert len(grp["support"]) == 2
    assert len(grp["dissent"]) == 1
    assert grp["support_ratio"] > 0.5
    assert grp["triangulated"] == True
    assert grp["source_count"] == 3

def test_triangulate_no_consensus():
    """Test triangulation with no consensus."""
    key = ClaimKey(metric="gdp_contribution", unit="percent", period="2024", geo="USA")
    
    # Create widely varying claims
    claim1 = Claim(key=key, value=2.0, source_url="https://a.com", source_domain="a.com")
    claim2 = Claim(key=key, value=5.0, source_url="https://b.com", source_domain="b.com")
    claim3 = Claim(key=key, value=8.0, source_url="https://c.com", source_domain="c.com")
    
    result = triangulate([claim1, claim2, claim3])
    
    grp = result[key]
    # With 2% tolerance for GDP, these should all disagree
    assert grp["support_ratio"] < 0.5
    assert grp["triangulated"] == False

def test_agree_function():
    """Test the agree function with different tolerances."""
    # Exact match
    assert _agree(5.0, 5.0, 0.03) == True
    
    # Within 3% tolerance
    assert _agree(100.0, 102.0, 0.03) == True
    assert _agree(100.0, 97.0, 0.03) == True
    
    # Outside 3% tolerance
    assert _agree(100.0, 104.0, 0.03) == False
    
    # Zero handling
    assert _agree(0.0, 0.0, 0.03) == True

def test_find_contradictions():
    """Test finding contradictory claims."""
    key = ClaimKey(metric="hotel_occupancy", unit="percent", period="2024-Q3", geo="EU27")
    
    # Create contradictory claims
    claim1 = Claim(key=key, value=75.0, source_url="https://str.com", source_domain="str.com")
    claim2 = Claim(key=key, value=65.0, source_url="https://eurostat.eu", source_domain="eurostat.eu")
    
    contradictions = find_contradictions([claim1, claim2], strict_tolerance=0.05)
    
    # 75 vs 65 is more than 5% difference
    assert len(contradictions) == 1
    assert (claim1, claim2) in contradictions or (claim2, claim1) in contradictions

def test_triangulate_single_source():
    """Test triangulation with single source."""
    key = ClaimKey(metric="airline_capacity", unit="value", period="2025-Q1", geo="WORLD")
    claim = Claim(key=key, value=1000000, source_url="https://iata.org", source_domain="iata.org")
    
    result = triangulate([claim])
    
    grp = result[key]
    assert grp["consensus"] == 1000000
    assert grp["support_ratio"] == 1.0
    assert grp["triangulated"] == False  # Need multiple sources for triangulation
    assert grp["source_count"] == 1

def test_triangulate_median_calculation():
    """Test that consensus uses median correctly."""
    key = ClaimKey(metric="tourism_spend", unit="value", period="2024", geo="WORLD")
    
    # Odd number of values
    claims_odd = [
        Claim(key=key, value=1.0, source_url="https://a.com", source_domain="a.com"),
        Claim(key=key, value=2.0, source_url="https://b.com", source_domain="b.com"),
        Claim(key=key, value=3.0, source_url="https://c.com", source_domain="c.com"),
    ]
    
    result_odd = triangulate(claims_odd)
    assert result_odd[key]["consensus"] == 2.0  # Middle value
    
    # Even number of values
    claims_even = claims_odd + [
        Claim(key=key, value=4.0, source_url="https://d.com", source_domain="d.com"),
    ]
    
    result_even = triangulate(claims_even)
    assert result_even[key]["consensus"] == 2.5  # Average of two middle values