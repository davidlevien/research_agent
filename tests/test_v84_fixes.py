"""Sanity tests for v8.4 PE-grade fixes."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from research_system.models import EvidenceCard
from research_system.report.composer import _best_text
from research_system.enrich.ensure_quotes import ensure_quotes_for_primaries, CLAIM_PAT
from research_system.providers.openalex import search_openalex, to_cards as openalex_to_cards
from research_system.providers.oecd import _dataflows, search_oecd
from research_system.connectors.crossref import search_crossref
from research_system.tools.domain_policies import get_headers_for_domain, should_skip_domain
from research_system.net.pdf_fetch import download_pdf, _canonicalize_url, _seen_downloads, _url_to_hash
import httpx
import json


def test_composer_handles_missing_best_quote():
    """Test composer doesn't crash on missing best_quote field."""
    # Card with no best_quote field
    card = Mock(spec=EvidenceCard)
    card.best_quote = None  # Explicitly None
    card.quotes = ["Some quote from the document"]
    card.claim = "A claim"
    card.supporting_text = "Supporting text"
    card.snippet = "A snippet"
    card.title = "Title"
    
    # Should not crash - _best_text checks snippet first (changed priority)
    result = _best_text(card)
    assert result == "A snippet"  # snippet is checked before claim now
    
    # Test with no claim (snippet still takes priority)
    card.claim = None
    result = _best_text(card)
    assert result == "A snippet"  # snippet is still checked first
    
    # Test with minimal fields
    card.supporting_text = None
    card.quotes = []
    result = _best_text(card)
    assert result == "A snippet"  # snippet is next
    
    # Test with only title
    card.snippet = None
    result = _best_text(card)
    assert result == "Title"


def test_quote_extraction_heuristics():
    """Test enhanced quote extraction patterns."""
    # Test tourism/economic patterns
    test_cases = [
        ("Tourism arrivals rose 15% in 2024", True),
        ("Global spend declined 3.5% last quarter", True),
        ("Occupancy rates rebounded to 75%", True),
        ("2024 saw tourism nights exceed 1 billion", True),
        ("Revenue reached $2.3 trillion", True),
        ("Q1 2024 showed strong growth", True),
        ("This is just normal text", False),
    ]
    
    for text, should_match in test_cases:
        match = CLAIM_PAT.search(text)
        assert bool(match) == should_match, f"Failed for: {text}"


def test_ensure_quotes_with_pdf_text():
    """Test that quote extraction doesn't crash with missing fields."""
    # Simple test that the function exists and can handle cards
    from research_system.enrich.ensure_quotes import sentence_window, CLAIM_PAT
    
    pdf_text = '''
    "International tourist arrivals reached 1.5 billion in 2024, 
    surpassing pre-pandemic levels by 3%" said the report.
    '''
    
    # Test sentence_window function
    result = sentence_window(pdf_text)
    assert result is not None  # Should extract something
    
    # Test CLAIM_PAT matches tourism patterns  
    assert CLAIM_PAT.search("Tourism rose 15% in 2024") is not None


def test_openalex_fallback_on_400():
    """Test OpenAlex has fallback logic for 400 errors."""
    # Simple test that function handles errors gracefully
    with patch('research_system.providers.http.http_json_with_policy') as mock:
        mock.side_effect = Exception("400 Bad Request")
        results = search_openalex("test query")
        # Should return empty on error instead of crashing
        assert results == []


def test_oecd_dataflow_with_trailing_slash():
    """Test OECD SDMX endpoint URL has trailing slash."""
    # Check the constant is defined correctly
    from research_system.providers.oecd import _DATAFLOW
    assert _DATAFLOW.endswith("dataflow/ALL/"), "OECD dataflow URL should have trailing slash"


def test_crossref_with_mailto():
    """Test Crossref includes mailto parameter."""
    with patch('httpx.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "items": [{
                    "title": ["Test Paper"],
                    "DOI": "10.1234/test",
                    "URL": "http://example.com"
                }]
            }
        }
        mock_get.return_value = mock_response
        
        results = search_crossref("test query")
        
        # Check request includes mailto
        call_kwargs = mock_get.call_args[1]
        assert "mailto" in call_kwargs["params"]
        assert "@" in call_kwargs["params"]["mailto"]
        # Check User-Agent
        assert "ResearchAgent" in call_kwargs["headers"]["User-Agent"]


def test_sec_domain_policy():
    """Test SEC requires proper User-Agent with contact info."""
    headers = get_headers_for_domain("www.sec.gov")
    assert "User-Agent" in headers
    assert "research@example.com" in headers["User-Agent"]
    assert "academic research" in headers["User-Agent"]
    
    # Test skip on 403
    should_skip = should_skip_domain("www.sec.gov", response_code=403)
    assert should_skip is True


def test_wef_domain_policy():
    """Test WEF requires Referer header."""
    headers = get_headers_for_domain("reports.weforum.org")
    assert "Referer" in headers
    assert headers["Referer"] == "https://reports.weforum.org/"


def test_statista_login_wall_detection():
    """Test Statista login wall early exit."""
    should_skip = should_skip_domain("www.statista.com")
    assert should_skip is True


def test_no_duplicate_pdf_downloads():
    """Test same URL requested twice yields one download."""
    # Clear any previous downloads
    _seen_downloads.clear()
    _url_to_hash.clear()
    
    url = "http://example.com/report.pdf"
    canonical = _canonicalize_url(url)
    
    with patch('httpx.Client') as MockClient:
        client = MockClient()
        
        # Mock successful PDF download
        mock_response = Mock()
        mock_response.iter_bytes = Mock(return_value=[b"PDF content"])
        mock_response.raise_for_status = Mock()
        
        client.stream.return_value.__enter__ = Mock(return_value=mock_response)
        client.stream.return_value.__exit__ = Mock(return_value=None)
        
        # First download
        pdf1 = download_pdf(client, url)
        # Check that URL is tracked in _url_to_hash
        assert canonical in _url_to_hash
        # And content is cached by hash
        content_hash = _url_to_hash[canonical]
        assert content_hash in _seen_downloads
        
        # Second download should return cached
        pdf2 = download_pdf(client, url)
        
        # Should only have made one network call
        assert client.stream.call_count == 1
        # Should return same content
        assert pdf1 == pdf2


def test_url_canonicalization():
    """Test URL canonicalization for deduplication."""
    test_cases = [
        ("http://example.com/path", "http://example.com/path"),
        ("http://example.com/path/", "http://example.com/path"),
        ("http://Example.COM/Path", "http://example.com/path"),
        ("http://example.com/path#fragment", "http://example.com/path"),
        ("http://example.com/path?b=2&a=1", "http://example.com/path?a=1&b=2"),
    ]
    
    for input_url, expected in test_cases:
        result = _canonicalize_url(input_url)
        assert result == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])