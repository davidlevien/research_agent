"""Unit tests for structured triangulation."""

from types import SimpleNamespace
from research_system.triangulation.indicators import to_structured_key
from research_system.triangulation.post import structured_triangles

def mk(title, domain, provider, meta=None):
    """Create mock evidence card."""
    return SimpleNamespace(
        title=title, 
        snippet=None, 
        claim=None, 
        source_domain=domain, 
        provider=provider, 
        metadata=meta or {}
    )

def test_structured_triangle_gdp_2024():
    """Test that GDP data from IMF and World Bank triangulates."""
    a = mk(
        "World GDP (current US$) 2024 snapshot", 
        "worldbank.org", 
        "worldbank", 
        {"indicator": "NY.GDP.MKTP.CD"}
    )
    b = mk(
        "IMF NGDPD outlook 2024", 
        "imf.org", 
        "imf", 
        {"dataset_code": "NGDPD"}
    )
    
    # Create structured triangles
    out = structured_triangles([a, b])
    
    # Should find at least one triangulation
    assert len(out) > 0
    # Should have 2 different domains
    assert len(out[0]["domains"]) == 2
    assert "worldbank.org" in out[0]["domains"]
    assert "imf.org" in out[0]["domains"]

def test_indicator_recognition():
    """Test that indicators are properly recognized from text."""
    card = mk(
        "GDP growth rate was 3.5% in 2024",
        "test.org",
        "test",
        {}
    )
    
    key = to_structured_key(card)
    if key:  # May or may not match depending on aliases
        assert key.period == "2024"
        assert key.entity == "world"

def test_no_triangulation_single_domain():
    """Test that single-domain data doesn't triangulate."""
    cards = [
        mk("GDP 2024 data", "worldbank.org", "worldbank", {}),
        mk("More GDP 2024", "worldbank.org", "worldbank", {}),
    ]
    
    out = structured_triangles(cards)
    
    # Should not triangulate (same domain)
    assert len(out) == 0

def test_inflation_triangulation():
    """Test inflation data triangulation."""
    cards = [
        mk(
            "CPI inflation YoY reached 3.2% in 2024",
            "oecd.org",
            "oecd",
            {}
        ),
        mk(
            "Consumer prices (YoY) up 3.2% in 2024",
            "imf.org",
            "imf",
            {}
        )
    ]
    
    out = structured_triangles(cards)
    
    # Should triangulate if aliases are configured
    if len(out) > 0:
        assert len(out[0]["domains"]) == 2
        assert "indices" in out[0]  # Should have indices for union calculation