"""Test DOI fallback functionality."""

import pytest
from research_system.tools.doi_tools import extract_doi, crossref_meta


def test_extract_doi():
    """Test DOI extraction from various URL formats."""
    # Standard e-unwto.org format
    url = "https://www.e-unwto.org/doi/abs/10.18111/wtobarometereng.2025.23.1.1"
    assert extract_doi(url) == "10.18111/wtobarometereng.2025.23.1.1"
    
    # PDF variant
    url = "https://www.e-unwto.org/doi/pdf/10.18111/wtobarometereng.2025.23.1.1"
    assert extract_doi(url) == "10.18111/wtobarometereng.2025.23.1.1"
    
    # Full text variant
    url = "https://example.com/doi/full/10.1234/test.2024"
    assert extract_doi(url) == "10.1234/test.2024"
    
    # No DOI
    url = "https://example.com/article/123"
    assert extract_doi(url) is None
    
    # Empty URL
    assert extract_doi("") is None
    assert extract_doi(None) is None


def test_crossref_meta_structure():
    """Test Crossref metadata extraction structure."""
    # Test with a known DOI (mock in production)
    # This is a structural test - in production you'd mock the HTTP call
    meta = crossref_meta("invalid-doi")
    assert isinstance(meta, dict)
    assert "title" in meta or len(meta) == 0
    assert "abstract" in meta or len(meta) == 0
    assert "date" in meta or len(meta) == 0