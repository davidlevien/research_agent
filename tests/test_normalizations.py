"""
Test normalization functions for metrics, periods, and numbers
"""

import pytest
from research_system.tools.metrics_lexicon import canon_metric_name
from research_system.tools.period_norm import normalize_period
from research_system.tools.num_norm import parse_number_with_unit, numbers_compatible
from research_system.tools.claim_struct import extract_struct_claim, struct_key


def test_metric_normalization():
    """Test that metric aliases collapse to canonical IDs"""
    # Tourism metrics
    assert canon_metric_name("arrivals") == "international_tourist_arrivals"
    assert canon_metric_name("tourist arrivals") == "international_tourist_arrivals"
    assert canon_metric_name("visitor inflows") == "international_tourist_arrivals"
    assert canon_metric_name("international arrivals") == "international_tourist_arrivals"
    
    # Hotel metrics
    assert canon_metric_name("hotel occupancy") == "hotel_occupancy_rate"
    assert canon_metric_name("occupancy rate") == "hotel_occupancy_rate"
    assert canon_metric_name("room occupancy") == "hotel_occupancy_rate"
    
    # GDP metrics
    assert canon_metric_name("tourism GDP") == "gdp_contribution_travel"
    assert canon_metric_name("travel GDP") == "gdp_contribution_travel"
    assert canon_metric_name("GDP contribution of tourism") == "gdp_contribution_travel"
    
    # Non-matching
    assert canon_metric_name("random metric") is None


def test_period_normalization():
    """Test that various period formats normalize correctly"""
    # Quarters
    assert normalize_period("Q1 2025") == "Q1 2025"
    assert normalize_period("q1 2025") == "Q1 2025"
    assert normalize_period("first quarter 2025") == "Q1 2025"
    assert normalize_period("1st quarter 2025") == "Q1 2025"
    
    # Month ranges to quarters
    assert normalize_period("Jan-Mar 2025") == "Q1 2025"
    assert normalize_period("January to March 2025") == "Q1 2025"
    assert normalize_period("Apr-Jun 2025") == "Q2 2025"
    assert normalize_period("Jul-Sep 2025") == "Q3 2025"
    assert normalize_period("Oct-Dec 2025") == "Q4 2025"
    
    # Half years
    assert normalize_period("H1 2025") == "H1 2025"
    assert normalize_period("h1 2025") == "H1 2025"
    assert normalize_period("H2 2025") == "H2 2025"
    
    # Fiscal years
    assert normalize_period("FY 2025") == "FY 2025"
    assert normalize_period("FY2025") == "FY 2025"
    
    # Years
    assert normalize_period("2025") == "2025"
    assert normalize_period("in 2025") == "2025"


def test_number_parsing():
    """Test number and unit extraction"""
    # Percentages
    assert parse_number_with_unit("5%") == (5.0, "%")
    assert parse_number_with_unit("5.5%") == (5.5, "%")
    assert parse_number_with_unit("grew by 10%") == (10.0, "%")
    
    # Percentage points
    assert parse_number_with_unit("5 pp") == (5.0, "PP")
    assert parse_number_with_unit("5 percentage points") == (5.0, "PP")
    assert parse_number_with_unit("increased 3 ppts") == (3.0, "PP")
    
    # Large numbers
    assert parse_number_with_unit("5 billion") == (5.0, "B")
    assert parse_number_with_unit("5bn") == (5.0, "B")
    assert parse_number_with_unit("3.5 million") == (3.5, "M")
    assert parse_number_with_unit("3.5m") == (3.5, "M")
    assert parse_number_with_unit("2 trillion") == (2.0, "T")
    assert parse_number_with_unit("1.5k") == (1.5, "K")
    
    # Plain numbers
    assert parse_number_with_unit("42") == (42.0, None)
    assert parse_number_with_unit("3.14159") == (3.14159, None)
    assert parse_number_with_unit("1,234,567") == (1234567.0, None)


def test_number_compatibility():
    """Test number compatibility checking"""
    # Same units
    assert numbers_compatible((5.0, "%"), (5.5, "%"), pct_tol=0.10) == True
    assert numbers_compatible((5.0, "%"), (6.0, "%"), pct_tol=0.10) == False
    
    # Different units incompatible
    assert numbers_compatible((5.0, "%"), (5.0, "PP"), pct_tol=0.10) == False
    
    # Million vs Billion conversion
    assert numbers_compatible((1000.0, "M"), (1.0, "B"), pct_tol=0.10) == True
    assert numbers_compatible((500.0, "M"), (1.0, "B"), pct_tol=0.10) == False
    
    # None values always compatible
    assert numbers_compatible((None, None), (5.0, "%"), pct_tol=0.10) == True
    assert numbers_compatible((5.0, "%"), (None, None), pct_tol=0.10) == True


def test_structured_claim_extraction():
    """Test full structured claim extraction with normalizations"""
    # Tourism claim
    text1 = "Global tourist arrivals reached 1.5 billion in Q1 2025"
    sc1 = extract_struct_claim(text1)
    assert sc1.entity == "global"
    assert sc1.metric == "international_tourist_arrivals"  # Normalized
    assert sc1.period == "Q1 2025"  # Normalized
    assert sc1.value == 1.5
    assert sc1.unit == "B"
    
    # Period normalization in claim
    text2 = "Europe hotel occupancy was 75% in Jan-Mar 2025"
    sc2 = extract_struct_claim(text2)
    assert sc2.entity == "european union"  # Normalized from europe
    assert sc2.metric == "hotel_occupancy_rate"  # Normalized
    assert sc2.period == "Q1 2025"  # Normalized from Jan-Mar
    assert sc2.value == 75.0
    assert sc2.unit == "%"
    
    # Structured keys should match for same claim
    key1 = struct_key(sc1)
    assert key1 == "global|international_tourist_arrivals|Q1 2025"
    
    key2 = struct_key(sc2)
    assert key2 == "european union|hotel_occupancy_rate|Q1 2025"  # Normalized entity


def test_contradiction_detection():
    """Test that contradictions are properly detected"""
    from research_system.tools.contradictions import find_numeric_conflicts
    
    texts = [
        "Global tourist arrivals reached 1.5 billion in Q1 2025",
        "International arrivals were 1.2 billion in first quarter 2025",  # Same metric/period, different value
        "Europe hotel occupancy was 75% in Q1 2025",
        "European hotel occupancy rate hit 74% in Jan-Mar 2025",  # Within tolerance
    ]
    
    conflicts = find_numeric_conflicts(texts, tol=0.10)
    
    # Should find conflict between 1.5B and 1.2B (20% difference > 10% tolerance)
    assert len(conflicts) >= 1
    
    conflict = conflicts[0]
    assert conflict["key"] == "global|international_tourist_arrivals|Q1 2025"
    assert set(conflict["values"]) == {1.5, 1.2}
    
    # 75% vs 74% should NOT be a conflict (1.3% difference < 10% tolerance)
    europe_conflicts = [c for c in conflicts if "europe" in c["key"]]
    assert len(europe_conflicts) == 0


def test_arex_query_generation():
    """Test AREX query generation for uncorroborated claims"""
    from research_system.tools.arex import build_arex_queries
    
    # Test with specific structured claim components
    queries = build_arex_queries(
        entity="global",
        metric="tourist arrivals",
        period="Q1 2025",
        primary_domains=["unwto.org", "wttc.org", "oecd.org"]
    )
    
    # Should prioritize primary domains
    assert any("site:unwto.org" in q for q in queries)
    
    # Should include base query
    assert "global tourist arrivals Q1 2025" in queries
    
    # Should have bounded number of queries
    assert len(queries) <= 6


if __name__ == "__main__":
    # Run tests
    test_metric_normalization()
    print("✓ Metric normalization tests passed")
    
    test_period_normalization()
    print("✓ Period normalization tests passed")
    
    test_number_parsing()
    print("✓ Number parsing tests passed")
    
    test_number_compatibility()
    print("✓ Number compatibility tests passed")
    
    test_structured_claim_extraction()
    print("✓ Structured claim extraction tests passed")
    
    test_contradiction_detection()
    print("✓ Contradiction detection tests passed")
    
    test_arex_query_generation()
    print("✓ AREX query generation tests passed")
    
    print("\n✅ All normalization tests passed!")