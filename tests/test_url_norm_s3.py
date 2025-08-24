"""Test URL normalization for S3 and other special cases."""

import pytest
from research_system.tools.url_norm import canonicalize_url


def test_s3_versionid_stripped():
    """Test that S3 VersionId query parameters are stripped."""
    u = "https://bucket.s3.amazonaws.com/file.pdf?VersionId=ABC123"
    result = canonicalize_url(u)
    assert result.endswith("/file.pdf")
    assert "VersionId" not in result
    assert "?" not in result


def test_s3_multiple_params_stripped():
    """Test that all S3 query parameters are stripped."""
    u = "https://mybucket.s3.us-west-2.amazonaws.com/docs/report.pdf?VersionId=XYZ&Signature=abc"
    result = canonicalize_url(u)
    assert result.endswith("/docs/report.pdf")
    assert "?" not in result
    assert "VersionId" not in result
    assert "Signature" not in result


def test_e_unwto_doi_normalized():
    """Test that e-unwto.org DOI URLs are normalized."""
    u = "https://e-unwto.org/doi/pdf/10.18111/wtobarometereng.2025.23.1?download=true"
    result = canonicalize_url(u)
    assert result == "https://e-unwto.org/doi/pdf/10.18111/wtobarometereng.2025.23.1"
    assert "?" not in result
    assert "download" not in result


def test_regular_urls_preserved():
    """Test that regular URLs keep their query parameters."""
    u = "https://www.example.com/search?q=tourism&page=2"
    result = canonicalize_url(u)
    # Regular canonicalization may reorder params but should keep them
    assert "q=tourism" in result
    assert "page=2" in result


def test_standard_canonicalization_applied():
    """Test that standard canonicalization is still applied."""
    u = "HTTP://EXAMPLE.COM:80/path/../file.html"
    result = canonicalize_url(u)
    assert result == "http://example.com/file.html"


def test_fragment_always_removed():
    """Test that fragments are always removed."""
    u = "https://example.com/page#section"
    result = canonicalize_url(u)
    assert "#" not in result
    assert result == "http://example.com/page"


def test_trailing_slash_normalized():
    """Test that trailing slashes are handled consistently."""
    u1 = "https://example.com/path/"
    u2 = "https://example.com/path"
    result1 = canonicalize_url(u1)
    result2 = canonicalize_url(u2)
    # w3lib typically removes trailing slash for non-root paths
    assert result1 == result2