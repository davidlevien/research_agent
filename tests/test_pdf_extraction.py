"""Test PDF extraction functionality."""

import pytest
from unittest.mock import patch, Mock
from research_system.tools.fetch import extract_article


def test_pdf_detection_by_url():
    """Test that PDFs are detected by URL extension and properly extracted."""
    url = "https://example.com/report.pdf"
    
    # Create comprehensive mocks
    mock_settings = Mock()
    mock_settings.ENABLE_WARC = False
    mock_settings.ENABLE_PDF_TABLES = False
    mock_settings.ENABLE_LANGDETECT = False
    mock_settings.ENABLE_POLITENESS = False
    mock_settings.ENABLE_HTTP_CACHE = False
    
    with patch('research_system.tools.fetch.get_settings', return_value=mock_settings):
        with patch('research_system.net.robots.is_allowed', return_value=True):
            with patch('research_system.net.circuit.CIRCUIT.allow', return_value=True):
                with patch('research_system.net.cache.get', return_value=None):
                    with patch('research_system.net.cache.set'):
                        with patch('research_system.time_budget.get_timeout', return_value=30):
                            # Mock the HTTP response
                            mock_response = Mock()
                            mock_response.status_code = 200
                            mock_response.headers = {"content-type": "application/pdf"}
                            # For PDFs, httpx would return binary as text, make it long enough
                            mock_response.text = "x" * 600
                            mock_response.url = url
                            
                            with patch('research_system.tools.fetch.httpx.get', return_value=mock_response):
                                with patch('research_system.net.circuit.CIRCUIT.ok'):
                                    with patch('research_system.tools.paywall_resolver.looks_gated', return_value=False):
                                        # Mock httpx.Client context manager
                                        mock_client = Mock()
                                        with patch('research_system.tools.fetch.httpx.Client', return_value=mock_client):
                                            mock_client.__enter__ = Mock(return_value=mock_client)
                                            mock_client.__exit__ = Mock(return_value=None)
                                            
                                            # Mock PDF download
                                            with patch('research_system.net.pdf_fetch.download_pdf', return_value=b"PDF content"):
                                                # Mock PDF text extraction
                                                pdf_result = {
                                                    "title": "Test PDF",
                                                    "text": "This is a test PDF document with important information."
                                                }
                                                with patch('research_system.tools.fetch.extract_pdf_text', return_value=pdf_result):
                                                    # Mock claim selection
                                                    with patch('research_system.tools.fetch.select_claim_sentences', return_value=["Important claim"]):
                                                        
                                                        result = extract_article(url)
                                                        
                                                        assert result is not None
                                                        assert result.get("title") == "Test PDF"
                                                        assert "important information" in result.get("text", "")


def test_pdf_detection_by_content_type():
    """Test that PDFs are detected by content-type header."""
    url = "https://e-unwto.org/doi/pdf/10.18111/wtobarometereng.2025"
    
    # Create comprehensive mocks
    mock_settings = Mock()
    mock_settings.ENABLE_WARC = False
    mock_settings.ENABLE_PDF_TABLES = False
    mock_settings.ENABLE_LANGDETECT = False
    mock_settings.ENABLE_POLITENESS = False
    mock_settings.ENABLE_HTTP_CACHE = False
    
    with patch('research_system.tools.fetch.get_settings', return_value=mock_settings):
        with patch('research_system.net.robots.is_allowed', return_value=True):
            with patch('research_system.net.circuit.CIRCUIT.allow', return_value=True):
                with patch('research_system.net.cache.get', return_value=None):
                    with patch('research_system.net.cache.set'):
                        with patch('research_system.time_budget.get_timeout', return_value=30):
                            # Mock the HTTP response indicating PDF
                            mock_response = Mock()
                            mock_response.status_code = 200
                            mock_response.headers = {"content-type": "application/pdf"}
                            # Make text long enough to avoid paywall check
                            mock_response.text = "x" * 600
                            mock_response.url = url
                            
                            with patch('research_system.tools.fetch.httpx.get', return_value=mock_response):
                                with patch('research_system.net.circuit.CIRCUIT.ok'):
                                    with patch('research_system.tools.paywall_resolver.looks_gated', return_value=False):
                                        # Mock paywall resolver to prevent DOI resolution
                                        with patch('research_system.tools.paywall_resolver.resolve', return_value=None):
                                            # Mock httpx.Client context manager
                                            mock_client = Mock()
                                            with patch('research_system.tools.fetch.httpx.Client', return_value=mock_client):
                                                mock_client.__enter__ = Mock(return_value=mock_client)
                                                mock_client.__exit__ = Mock(return_value=None)
                                                
                                                # Mock PDF download
                                                with patch('research_system.net.pdf_fetch.download_pdf', return_value=b"PDF content"):
                                                    # Mock PDF text extraction
                                                    pdf_result = {
                                                        "title": "UNWTO Barometer",
                                                        "text": "International tourist arrivals grew by 5% in Q1 2025."
                                                    }
                                                    with patch('research_system.tools.fetch.extract_pdf_text', return_value=pdf_result):
                                                        # Mock claim selection
                                                        with patch('research_system.tools.fetch.select_claim_sentences', return_value=["5% growth"]):
                                                            
                                                            result = extract_article(url)
                                                            
                                                            assert result is not None
                                                            assert result.get("title") == "UNWTO Barometer"
                                                            assert "5%" in result.get("text", "")
                                                            assert "Q1 2025" in result.get("text", "")


def test_html_extraction_not_affected():
    """Test that regular HTML extraction still works."""
    url = "https://example.com/article"
    
    # Create mock settings
    mock_settings = Mock()
    mock_settings.ENABLE_POLITENESS = False
    mock_settings.ENABLE_HTTP_CACHE = False
    
    with patch('research_system.tools.fetch.get_settings', return_value=mock_settings):
        with patch('research_system.net.robots.is_allowed', return_value=True):
            with patch('research_system.net.circuit.CIRCUIT.allow', return_value=True):
                with patch('research_system.net.cache.get', return_value=None):
                    with patch('research_system.net.cache.set'):
                        with patch('research_system.time_budget.get_timeout', return_value=30):
                            # Mock HTML response
                            mock_response = Mock()
                            mock_response.status_code = 200
                            mock_response.headers = {"content-type": "text/html"}
                            mock_response.text = "<html><body>Test HTML content</body></html>"
                            mock_response.url = url
                            
                            with patch('research_system.tools.fetch.httpx.get', return_value=mock_response):
                                with patch('research_system.net.circuit.CIRCUIT.ok'):
                                    with patch('research_system.tools.paywall_resolver.looks_gated', return_value=False):
                                        # Mock trafilatura extraction
                                        with patch('research_system.tools.fetch.trafilatura.extract', return_value="Extracted text from HTML"):
                                            # Mock metadata extraction
                                            mock_meta = Mock()
                                            mock_meta.title = None
                                            with patch('research_system.tools.fetch.trafilatura.extract_metadata', return_value=mock_meta):
                                                # Mock extruct
                                                with patch('research_system.tools.fetch.extruct.extract', return_value={'json-ld': [], 'opengraph': []}):
                                                    # Mock claim selection
                                                    with patch('research_system.tools.fetch.select_claim_sentences', return_value=["Test claim"]):
                                                        
                                                        result = extract_article(url)
                                                        
                                                        assert result is not None
                                                        assert result.get("text") == "Extracted text from HTML"


def test_paywalled_url_returns_minimal_content():
    """Test that paywalled URLs still attempt extraction but get minimal content."""
    url = "https://statista.com/statistics/tourism"
    
    # Create mock settings
    mock_settings = Mock()
    mock_settings.ENABLE_POLITENESS = False
    mock_settings.ENABLE_HTTP_CACHE = False
    
    with patch('research_system.tools.fetch.get_settings', return_value=mock_settings):
        with patch('research_system.net.robots.is_allowed', return_value=True):
            with patch('research_system.net.circuit.CIRCUIT.allow', return_value=True):
                with patch('research_system.net.cache.get', return_value=None):
                    with patch('research_system.net.cache.set'):
                        with patch('research_system.time_budget.get_timeout', return_value=30):
                            # Mock response that redirects to login
                            mock_response = Mock()
                            mock_response.status_code = 200
                            mock_response.headers = {"content-type": "text/html"}
                            mock_response.text = "<html>Login required</html>"
                            # URL shows redirect to login page
                            mock_response.url = "https://statista.com/login?redirect=/statistics/tourism"
                            
                            with patch('research_system.tools.fetch.httpx.get', return_value=mock_response):
                                with patch('research_system.net.circuit.CIRCUIT.ok'):
                                    # Mock looks_gated to detect paywall
                                    with patch('research_system.tools.paywall_resolver.looks_gated', return_value=True):
                                        # Mock paywall resolver returning None (no alternative found)
                                        with patch('research_system.tools.paywall_resolver.resolve', return_value=None):
                                            # Mock trafilatura extraction of the login page
                                            with patch('research_system.tools.fetch.trafilatura.extract', return_value="Login required"):
                                                # Mock metadata extraction
                                                with patch('research_system.tools.fetch.trafilatura.extract_metadata', return_value=None):
                                                    # Mock extruct
                                                    with patch('research_system.tools.fetch.extruct.extract', return_value={'json-ld': [], 'opengraph': []}):
                                                        # Mock claim selection
                                                        with patch('research_system.tools.fetch.select_claim_sentences', return_value=[]):
                                                            
                                                            result = extract_article(url)
                                                            
                                                            # When paywalled with no alternative, we still get the login page content
                                                            assert result is not None
                                                            assert "Login required" in result.get("text", "")
                                                            assert result.get("quotes") == []