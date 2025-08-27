"""Test PDF extraction functionality."""

import pytest
from unittest.mock import patch, MagicMock
from research_system.tools.fetch import extract_article


def test_pdf_detection_by_url():
    """Test that PDFs are detected by URL extension and properly extracted."""
    # This tests the actual PDF extraction flow in extract_article
    
    url = "https://example.com/report.pdf"
    
    # Mock robots check to allow access
    with patch('research_system.tools.fetch.robots_allowed') as mock_robots:
        mock_robots.return_value = True
        
        # Mock fetch_html to return None (indicates binary content)
        with patch('research_system.tools.fetch.fetch_html') as mock_fetch_html:
            mock_fetch_html.return_value = (None, "application/pdf")
            
            # Since it's a PDF URL and fetch_html returns None, extract_article
            # should detect it's a PDF and download it directly
            with patch('research_system.tools.fetch.httpx.get') as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.content = b"PDF content bytes"
                mock_get.return_value = mock_response
                
                # Mock PDF text extraction
                with patch('research_system.tools.fetch.extract_pdf_text') as mock_pdf:
                    mock_pdf.return_value = {
                        "title": "Test PDF",
                        "text": "This is a test PDF document with important information."
                    }
                    
                    result = extract_article(url)
                    
                    # Verify the PDF was detected and extracted correctly
                    assert result["title"] == "Test PDF"
                    assert "important information" in result["text"]
                    # Verify httpx was used to download the PDF
                    mock_get.assert_called()
                    # Verify extract_pdf_text was called with the PDF bytes
                    mock_pdf.assert_called_once_with(b"PDF content bytes")


def test_pdf_detection_by_content_type():
    """Test that PDFs are detected by content-type header."""
    with patch('research_system.tools.fetch.fetch_html') as mock_fetch:
        mock_fetch.return_value = (None, "application/pdf")
        
        # Patch paywall resolver extract_doi to avoid MagicMock issue
        with patch('research_system.tools.paywall_resolver.extract_doi_from_html') as mock_doi:
            mock_doi.return_value = None  # No DOI found
            
            with patch('research_system.tools.fetch.httpx.get') as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.content = b"PDF content"
                mock_get.return_value = mock_response
                
                with patch('research_system.tools.fetch.extract_pdf_text') as mock_pdf:
                    mock_pdf.return_value = {
                        "title": "UNWTO Barometer",
                        "text": "International tourist arrivals grew by 5% in Q1 2025."
                    }
                    
                    result = extract_article("https://e-unwto.org/doi/pdf/10.18111/wtobarometereng.2025")
                    
                    assert result["title"] == "UNWTO Barometer"
                    assert "5%" in result["text"]
                    assert "Q1 2025" in result["text"]


def test_html_extraction_not_affected():
    """Test that regular HTML extraction still works."""
    with patch('research_system.tools.fetch.fetch_html') as mock_fetch:
        mock_fetch.return_value = ("<html><body>Test HTML</body></html>", "text/html")
        
        with patch('research_system.tools.fetch.trafilatura.extract') as mock_traf:
            mock_traf.return_value = "Extracted text from HTML"
            
            result = extract_article("https://example.com/article")
            
            assert result["text"] == "Extracted text from HTML"
            mock_traf.assert_called_once()


def test_paywalled_url_returns_empty():
    """Test that paywalled URLs return empty when blocked."""
    with patch('research_system.tools.fetch.fetch_html') as mock_fetch_html:
        # Return paywall page HTML
        mock_fetch_html.return_value = ("<html>Login required</html>", "text/html")
        
        # Patch DOI extraction to avoid issues
        with patch('research_system.tools.paywall_resolver.extract_doi_from_html') as mock_doi:
            mock_doi.return_value = None  # No DOI found
            
            with patch('research_system.tools.fetch.httpx.get') as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 403
                mock_response.url = "https://statista.com/login"
                mock_get.return_value = mock_response
                
                # Also patch trafilatura to return None
                with patch('research_system.tools.fetch.trafilatura.extract') as mock_traf:
                    mock_traf.return_value = None
                    
                    result = extract_article("https://statista.com/statistics/tourism")
            
            assert result == {}