"""Unit tests for DOI metadata rescue functionality."""

import pytest
from unittest.mock import patch, MagicMock
from research_system.tools.doi_fallback import (
    crossref_meta,
    unpaywall_meta,
    doi_rescue,
    extract_doi_from_url
)


def test_extract_doi_from_url():
    """Test DOI extraction from various URL formats."""
    # Standard doi.org URL
    assert extract_doi_from_url("https://doi.org/10.1234/example") == "10.1234/example"
    
    # dx.doi.org URL
    assert extract_doi_from_url("https://dx.doi.org/10.1234/example") == "10.1234/example"
    
    # DOI in path
    assert extract_doi_from_url("https://example.com/article/10.1234/test-paper") == "10.1234/test-paper"
    
    # With query params
    assert extract_doi_from_url("https://doi.org/10.1234/example?version=1") == "10.1234/example"
    
    # No DOI
    assert extract_doi_from_url("https://example.com/article") is None


@patch('httpx.get')
def test_crossref_meta_success(mock_get):
    """Test successful Crossref metadata retrieval."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": {
            "title": ["Test Article Title"],
            "abstract": "This is a test abstract with some content.",
            "publisher": "Test Publisher",
            "issued": {
                "date-parts": [[2024, 3, 15]]
            }
        }
    }
    mock_get.return_value = mock_response
    
    result = crossref_meta("10.1234/test", email="test@example.com")
    
    assert result is not None
    assert result["title"] == "Test Article Title"
    assert result["abstract"] == "This is a test abstract with some content."
    assert result["date"] == "2024-03-15"
    assert result["publisher"] == "Test Publisher"
    assert result["source"] == "crossref"
    
    # Check User-Agent header was set
    mock_get.assert_called_once()
    call_args = mock_get.call_args
    assert "User-Agent" in call_args[1]["headers"]
    assert "test@example.com" in call_args[1]["headers"]["User-Agent"]


@patch('httpx.get')
def test_crossref_meta_failure(mock_get):
    """Test Crossref metadata retrieval failure."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response
    
    result = crossref_meta("10.1234/nonexistent")
    
    assert result is None


@patch('httpx.get')
def test_crossref_meta_cleans_html(mock_get):
    """Test that Crossref metadata cleaning removes HTML."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": {
            "title": ["Test Title"],
            "abstract": "<p>Abstract with <b>HTML</b> tags &amp; entities.</p>"
        }
    }
    mock_get.return_value = mock_response
    
    result = crossref_meta("10.1234/test")
    
    # HTML should be cleaned
    assert result["abstract"] == "Abstract with HTML tags & entities."


@patch('httpx.get')
def test_unpaywall_meta_success(mock_get):
    """Test successful Unpaywall metadata retrieval."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "title": "Open Access Article",
        "year": 2023,
        "oa_locations": [
            {
                "host_type": "repository",
                "url": "https://arxiv.org/pdf/2023.12345.pdf"
            }
        ]
    }
    mock_get.return_value = mock_response
    
    result = unpaywall_meta("10.1234/test", email="test@example.com")
    
    assert result is not None
    assert result["title"] == "Open Access Article"
    assert result["date"] == "2023-01-01"
    assert result["oa_url"] == "https://arxiv.org/pdf/2023.12345.pdf"
    assert result["source"] == "unpaywall"
    
    # Check email parameter was passed
    mock_get.assert_called_once()
    call_args = mock_get.call_args
    assert call_args[1]["params"]["email"] == "test@example.com"


@patch('httpx.get')
def test_unpaywall_prefers_repository_urls(mock_get):
    """Test that Unpaywall prefers repository URLs over publisher URLs."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "title": "Test Article",
        "oa_locations": [
            {
                "host_type": "publisher",
                "url": "https://publisher.com/article.pdf"
            },
            {
                "host_type": "repository",
                "url": "https://repository.edu/article.pdf"
            }
        ]
    }
    mock_get.return_value = mock_response
    
    result = unpaywall_meta("10.1234/test")
    
    # Should prefer repository URL
    assert result["oa_url"] == "https://repository.edu/article.pdf"


@patch('research_system.tools.doi_fallback.unpaywall_meta')
@patch('research_system.tools.doi_fallback.crossref_meta')
def test_doi_rescue_tries_both(mock_crossref, mock_unpaywall):
    """Test that doi_rescue tries Unpaywall when Crossref has no abstract."""
    # Crossref returns partial data with no abstract
    mock_crossref.return_value = {
        "title": "",  # Empty title means insufficient
        "abstract": "",
        "date": None,
        "source": "crossref"
    }
    
    # Unpaywall returns complementary data
    mock_unpaywall.return_value = {
        "title": "Test Title",
        "date": "2023-01-01",
        "oa_url": "https://oa.example.com/paper.pdf",
        "source": "unpaywall"
    }
    
    result = doi_rescue("10.1234/test")
    
    # Should have tried both
    mock_crossref.assert_called_once()
    mock_unpaywall.assert_called_once()
    
    # Should use Unpaywall data since Crossref was insufficient
    assert result["title"] == "Test Title"
    assert result["date"] == "2023-01-01"
    assert result["oa_url"] == "https://oa.example.com/paper.pdf"


@patch('research_system.tools.doi_fallback.unpaywall_meta')
@patch('research_system.tools.doi_fallback.crossref_meta')
def test_doi_rescue_crossref_sufficient(mock_crossref, mock_unpaywall):
    """Test that doi_rescue returns Crossref data if sufficient."""
    # Crossref returns good data with abstract
    mock_crossref.return_value = {
        "title": "Complete Article",
        "abstract": "This is a complete abstract with content.",
        "date": "2024-01-01",
        "source": "crossref"
    }
    
    result = doi_rescue("10.1234/test")
    
    # Should return Crossref data
    assert result["title"] == "Complete Article"
    assert result["abstract"] == "This is a complete abstract with content."
    assert result["source"] == "crossref"
    
    # Should have tried Crossref
    mock_crossref.assert_called_once()
    # Should NOT have tried Unpaywall since Crossref was sufficient
    mock_unpaywall.assert_not_called()


@patch('research_system.tools.doi_fallback.unpaywall_meta')
@patch('research_system.tools.doi_fallback.crossref_meta')
def test_doi_rescue_both_fail(mock_crossref, mock_unpaywall):
    """Test doi_rescue when both services fail."""
    mock_crossref.return_value = None
    mock_unpaywall.return_value = None
    
    result = doi_rescue("10.1234/nonexistent")
    
    assert result is None