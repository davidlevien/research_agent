"""Tests for OECD adapter with correct endpoint and fallback."""

import pytest
from unittest.mock import patch, Mock
from research_system.providers import oecd

def test_oecd_dataflows_lowercase_first():
    """Test that OECD tries lowercase endpoints first."""
    from research_system.providers.oecd import _DATAFLOW_CANDIDATES
    
    # First 4 should be lowercase
    assert "sdmx-json" in _DATAFLOW_CANDIDATES[0]
    assert "sdmx-json" in _DATAFLOW_CANDIDATES[1]
    assert "sdmx-json" in _DATAFLOW_CANDIDATES[2]
    assert "sdmx-json" in _DATAFLOW_CANDIDATES[3]
    
    # Should have 12 total endpoints
    assert len(_DATAFLOW_CANDIDATES) == 12

def test_oecd_dataflows_fallback():
    """Test OECD fallback through multiple endpoints."""
    with patch('research_system.providers.oecd.http_json') as mock_http:
        # First 3 fail, 4th succeeds
        mock_http.side_effect = [
            Exception("404 Not Found"),
            Exception("404 Not Found"),
            Exception("404 Not Found"),
            {"Dataflows": {"Dataflow": [
                {"id": "GDP", "Name": [{"value": "Gross Domestic Product"}]}
            ]}}
        ]
        
        result = oecd._dataflows()
        
        # Should have tried multiple times
        assert mock_http.call_count == 4
        # Should return normalized data
        assert isinstance(result, dict)
        assert "GDP" in result
        assert result["GDP"]["name"] == "Gross Domestic Product"

def test_oecd_circuit_breaker():
    """Test OECD circuit breaker on repeated failures."""
    from research_system.providers.oecd import _circuit_state, CIRCUIT_THRESHOLD
    
    # Reset circuit
    _circuit_state["is_open"] = False
    _circuit_state["consecutive_failures"] = 0
    _circuit_state["catalog_cache"] = None
    
    with patch('research_system.providers.oecd.http_json') as mock_http:
        # All endpoints fail
        mock_http.side_effect = Exception("Network error")
        
        # First call should fail and increment counter
        result1 = oecd._dataflows()
        assert result1 == {}
        
        # After threshold failures, circuit should trip
        for _ in range(CIRCUIT_THRESHOLD - 1):
            oecd._dataflows()
        
        assert _circuit_state["is_open"] == True

def test_oecd_search():
    """Test OECD search functionality."""
    with patch('research_system.providers.oecd._dataflows') as mock_dataflows:
        mock_dataflows.return_value = {
            "TOURISM": {"name": "Tourism Statistics"},
            "GDP": {"name": "Gross Domestic Product"},
            "TRADE": {"name": "International Trade"}
        }
        
        results = oecd.search_oecd("tourism", limit=2)
        
        assert len(results) <= 2
        assert results[0]["code"] == "TOURISM"  # Should be first by relevance
        assert "Tourism" in results[0]["name"]

def test_oecd_to_cards():
    """Test OECD result to card conversion."""
    rows = [
        {"code": "TOURISM", "name": "Tourism Statistics", "score": 5},
        {"code": "GDP", "name": "Gross Domestic Product", "score": 3}
    ]
    
    cards = oecd.to_cards(rows)
    
    assert len(cards) == 2
    assert cards[0]["title"] == "OECD: Tourism Statistics"
    assert cards[0]["url"] == "https://stats.oecd.org/Index.aspx?DataSetCode=TOURISM"
    assert cards[0]["source_domain"] == "oecd.org"
    assert cards[0]["metadata"]["provider"] == "oecd"