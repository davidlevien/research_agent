"""Test PDF extraction functionality."""

import pytest
from unittest.mock import patch, MagicMock
from research_system.tools.fetch import extract_article


def test_pdf_detection_by_url():
    """Test that PDFs are detected by URL extension."""
    with patch('research_system.tools.fetch.httpx.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"PDF content"
        mock_get.return_value = mock_response
        
        with patch('research_system.tools.fetch.extract_pdf_text') as mock_pdf:
            mock_pdf.return_value = {
                "title": "Test PDF",
                "text": "This is a test PDF document with important information."
            }
            
            result = extract_article("https://example.com/report.pdf")
            
            assert result["title"] == "Test PDF"
            assert "important information" in result["text"]
            mock_pdf.assert_called_once()


def test_pdf_detection_by_content_type():
    """Test that PDFs are detected by content-type header."""
    with patch('research_system.tools.fetch.fetch_html') as mock_fetch:
        mock_fetch.return_value = (None, "application/pdf")
        
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
    with patch('research_system.tools.fetch.httpx.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.url = "https://statista.com/login"
        mock_get.return_value = mock_response
        
        result = extract_article("https://statista.com/statistics/tourism")
        
        assert result == {}