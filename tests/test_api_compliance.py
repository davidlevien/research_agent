"""Tests for API compliance including headers, rate limiting, and licensing."""

import pytest
import time
import os
from unittest.mock import patch, MagicMock
from research_system.providers.http import _apply_policy, POLICY
from research_system.providers.registry import PROVIDERS
from research_system.models import EvidenceCard

class TestAPIHeaders:
    """Test that all providers include required headers."""
    
    def test_openalex_headers(self):
        """OpenAlex requires User-Agent and mailto."""
        params, headers = _apply_policy("openalex", "GET", "test_url")
        
        assert "User-Agent" in headers
        assert "research-agent" in headers["User-Agent"]
        assert "mailto" in headers
    
    def test_crossref_headers(self):
        """Crossref requires User-Agent with mailto."""
        params, headers = _apply_policy("crossref", "GET", "test_url")
        
        assert "User-Agent" in headers
        assert "mailto:" in headers["User-Agent"]
    
    def test_pubmed_params(self):
        """PubMed requires tool and email parameters."""
        params, headers = _apply_policy("pubmed", "GET", "test_url")
        
        assert "tool" in params
        assert params["tool"] == "research-agent"
        assert "email" in params
    
    def test_unpaywall_params(self):
        """Unpaywall requires email parameter."""
        params, headers = _apply_policy("unpaywall", "GET", "test_url")
        
        assert "email" in params

class TestRateLimiting:
    """Test rate limiting enforcement."""
    
    def test_arxiv_minimum_interval(self):
        """arXiv requires 3 seconds between requests."""
        start = time.time()
        
        # First call should not sleep
        _apply_policy("arxiv", "GET", "test_url1")
        
        # Second call should sleep to maintain 3s interval
        _apply_policy("arxiv", "GET", "test_url2")
        
        elapsed = time.time() - start
        assert elapsed >= 3.0, f"arXiv calls must be 3s apart, only {elapsed:.2f}s elapsed"
    
    def test_overpass_conservative_rate(self):
        """Overpass should be limited to 1 RPS."""
        start = time.time()
        
        # Make two rapid calls
        _apply_policy("overpass", "GET", "test_url1")
        _apply_policy("overpass", "GET", "test_url2")
        
        elapsed = time.time() - start
        assert elapsed >= 1.0, f"Overpass calls must be 1s apart, only {elapsed:.2f}s elapsed"
    
    def test_openalex_daily_limit(self):
        """OpenAlex has a 100k daily limit."""
        # Mock the daily counter to be near limit
        from research_system.providers.http import _daily_counts
        _daily_counts["openalex"] = 99999
        
        # First call should succeed
        _apply_policy("openalex", "GET", "test_url1")
        
        # Next call should raise
        with pytest.raises(Exception, match="Daily limit reached"):
            _apply_policy("openalex", "GET", "test_url2")

class TestLicensing:
    """Test licensing metadata is properly set."""
    
    def test_wikipedia_license(self):
        """Wikipedia content should be tagged CC BY-SA 3.0."""
        card = EvidenceCard(
            url="https://en.wikipedia.org/wiki/Test",
            title="Test",
            snippet="Test content",
            provider="wikipedia",
            credibility_score=0.8,
            relevance_score=0.8
        )
        
        jsonl = card.to_jsonl_dict()
        assert "metadata" in jsonl
        assert jsonl["metadata"]["license"] == "CC BY-SA 3.0"
    
    def test_openalex_license(self):
        """OpenAlex content should be tagged CC0."""
        card = EvidenceCard(
            url="https://openalex.org/W123",
            title="Test",
            snippet="Test content",
            provider="openalex",
            credibility_score=0.8,
            relevance_score=0.8
        )
        
        jsonl = card.to_jsonl_dict()
        assert "metadata" in jsonl
        assert jsonl["metadata"]["license"] == "CC0"
    
    def test_worldbank_license(self):
        """World Bank content should be tagged CC BY-4.0."""
        card = EvidenceCard(
            url="https://data.worldbank.org/indicator/TEST",
            title="Test",
            snippet="Test content",
            provider="worldbank",
            credibility_score=0.8,
            relevance_score=0.8
        )
        
        jsonl = card.to_jsonl_dict()
        assert "metadata" in jsonl
        assert jsonl["metadata"]["license"] == "CC BY-4.0"

class TestProviderCompliance:
    """Test overall provider compliance."""
    
    def test_all_providers_have_policy(self):
        """All providers should have a rate limit policy."""
        for provider_name in PROVIDERS.keys():
            if provider_name in ["unpaywall", "wayback", "wikidata"]:
                continue  # These are enrichment providers
            
            assert provider_name in POLICY or provider_name == "fred", \
                f"Provider {provider_name} missing from POLICY"
    
    def test_contact_email_used(self):
        """Contact email should be used when set."""
        # Reset the daily counters before testing
        from research_system.providers.http import _daily_counts, _daily_reset
        _daily_counts.clear()
        _daily_reset.clear()
        
        os.environ["CONTACT_EMAIL"] = "test@example.com"
        
        # Test OpenAlex uses it
        params, headers = _apply_policy("openalex", "GET", "test_url")
        assert "test@example.com" in headers.get("mailto", "")
        
        # Test PubMed uses it
        params, headers = _apply_policy("pubmed", "GET", "test_url")
        assert params.get("email") == "test@example.com"
        
        # Clean up
        del os.environ["CONTACT_EMAIL"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])