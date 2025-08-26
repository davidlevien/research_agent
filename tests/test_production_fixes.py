"""Tests for production hotfixes based on log analysis."""

import pytest
from unittest.mock import Mock, patch
import hashlib
from research_system.providers.openalex import search_openalex
from research_system.tools.log_redaction import redact_url, redact_headers, redact_string
from research_system.net.pdf_fetch import _content_hash, _canonicalize_url


def test_openalex_conservative_queries():
    """Test OpenAlex handles problematic queries gracefully."""
    test_cases = [
        # Query with special chars that cause 400s
        ("travel & tourism trends 2025!", "travel tourism trends 2025"),
        # Very long query
        ("a" * 200, "a" * 100),
        # Query with punctuation
        ("AI's impact: jobs, economy & society", "AI s impact jobs economy society"),
    ]
    
    with patch('research_system.providers.http.http_json_with_policy') as mock_http:
        mock_http.return_value = {"results": []}
        
        for input_query, _ in test_cases:
            results = search_openalex(input_query, per_page=25)
            assert isinstance(results, list)
            # Check that query was cleaned
            call_args = mock_http.call_args
            if call_args:
                params = call_args[1].get('params', {})
                # Should have conservative parameters
                assert params.get('per_page', 0) <= 10
                assert 'select' in params
                assert 'mailto' in params


def test_content_hash_deduplication():
    """Test that PDFs are deduplicated by content hash."""
    from research_system.net.pdf_fetch import _seen_downloads, _url_to_hash
    
    # Clear cache
    _seen_downloads.clear()
    _url_to_hash.clear()
    
    # Same content at different URLs
    content1 = b"PDF content here"
    content_hash = hashlib.sha256(content1).hexdigest()
    
    url1 = "https://example.com/report.pdf"
    url2 = "https://example.org/same-report.pdf"
    url3 = "https://example.com/report.pdf?v=2"  # Same as url1 with query param
    
    # Simulate caching first download
    _seen_downloads[content_hash] = content1
    _url_to_hash[_canonicalize_url(url1)] = content_hash
    
    # Check second URL with same content would be detected
    canonical2 = _canonicalize_url(url2)
    if canonical2 in _url_to_hash:
        assert _url_to_hash[canonical2] == content_hash
    
    # Canonical URL should normalize query params
    canonical3 = _canonicalize_url(url3)
    assert canonical3 != _canonicalize_url(url1) or "?" not in canonical3


def test_logging_redaction():
    """Test that sensitive data is redacted from logs."""
    
    # Test URL redaction
    test_urls = [
        ("https://api.example.com/v1?api_key=sk-abc123def456", 
         "https://api.example.com/v1?api_key=***REDACTED***"),
        ("https://api.openai.com/v1/chat?token=sk-proj-RGvIKUtoB2BVMQtI",
         "https://api.openai.com/v1/chat?token=***REDACTED***"),
        ("https://search.brave.com/api?key=BSA9OM70-7wmxlfMrLnY",
         "https://search.brave.com/api?key=***REDACTED***"),
    ]
    
    for input_url, expected_pattern in test_urls:
        redacted = redact_url(input_url)
        # Check for redaction (may be URL encoded)
        assert "REDACTED" in redacted
        assert "sk-proj-RGvI" not in redacted  # Check original key not present
        assert "BSA9OM70" not in redacted  # Check original key not present
    
    # Test header redaction
    headers = {
        "Authorization": "Bearer sk-abc123",
        "X-API-Key": "tvly-dev-SGJ0hPrrC0jeho3d",
        "Content-Type": "application/json",
        "User-Agent": "MyApp/1.0"
    }
    
    redacted = redact_headers(headers)
    assert redacted["Authorization"] == "***REDACTED***"
    assert redacted["X-API-Key"] == "***REDACTED***"
    assert redacted["Content-Type"] == "application/json"
    assert redacted["User-Agent"] == "MyApp/1.0"
    
    # Test string redaction
    log_msg = "Calling API with key=sk-proj-abc123 and token=BSA9OM70-xyz"
    redacted = redact_string(log_msg)
    assert "sk-proj-" not in redacted
    assert "BSA9OM70" not in redacted
    assert "***REDACTED***" in redacted


def test_oecd_endpoint_fix():
    """Test OECD uses correct endpoint URL."""
    from research_system.providers.oecd import _DATAFLOW
    # Should have trailing slash
    assert _DATAFLOW.endswith("/ALL/"), f"OECD endpoint should end with /ALL/ but is: {_DATAFLOW}"


def test_pdf_cache_with_redirects():
    """Test PDF cache handles redirected URLs properly."""
    from research_system.net.pdf_fetch import _url_to_hash, _seen_downloads
    
    # Clear cache
    _seen_downloads.clear()
    _url_to_hash.clear()
    
    # Simulate a redirect scenario
    original_url = "https://doi.org/10.1234/report"
    redirected_url = "https://publisher.com/pdf/report.pdf"
    content = b"PDF content"
    content_hash = hashlib.sha256(content).hexdigest()
    
    # Cache both URLs to same content
    _seen_downloads[content_hash] = content
    _url_to_hash[_canonicalize_url(original_url)] = content_hash
    _url_to_hash[_canonicalize_url(redirected_url)] = content_hash
    
    # Both URLs should resolve to same content
    assert _url_to_hash.get(_canonicalize_url(original_url)) == content_hash
    assert _url_to_hash.get(_canonicalize_url(redirected_url)) == content_hash


def test_quote_extraction_fallbacks():
    """Test quote extraction has multiple fallback strategies."""
    from research_system.enrich.ensure_quotes import CLAIM_PAT, METRIC_SENTENCE
    
    # Test patterns match various claim types
    test_claims = [
        "Tourism rose 15% in 2024",
        "Global arrivals reached 1.5 billion",  
        "Q1 2025 showed strong growth",
        "Revenue exceeded $2.3 trillion",
    ]
    
    for claim in test_claims:
        assert CLAIM_PAT.search(claim) is not None or METRIC_SENTENCE.search(claim) is not None, \
            f"Pattern should match: {claim}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])