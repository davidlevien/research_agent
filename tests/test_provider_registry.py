"""Tests for provider registry and intent-based selection."""

import pytest
import os
from research_system.intent.classifier import Intent
from research_system.providers.intent_registry import (
    expand_providers_for_intent,
    get_provider_rate_limit,
    _detect_available_keys,
    _is_provider_available
)


class TestProviderSelection:
    """Test provider selection based on intent."""
    
    def test_encyclopedia_providers(self):
        """Test encyclopedia intent selects appropriate providers."""
        providers = expand_providers_for_intent(Intent.ENCYCLOPEDIA)
        
        # Should include Wikipedia and Wikidata as primary
        assert "wikipedia" in providers
        assert "wikidata" in providers
        
        # Should be early in the list (free primary)
        assert providers.index("wikipedia") < 5
        assert providers.index("wikidata") < 5
    
    def test_local_providers(self):
        """Test local intent selects geospatial providers."""
        providers = expand_providers_for_intent(Intent.LOCAL)
        
        # Should include geospatial providers
        assert "nominatim" in providers
        assert "wikivoyage" in providers
    
    def test_academic_providers(self):
        """Test academic intent selects scholarly providers."""
        providers = expand_providers_for_intent(Intent.ACADEMIC)
        
        # Should include academic providers
        assert "openalex" in providers
        assert "crossref" in providers
        assert "pubmed" in providers
        assert "arxiv" in providers
    
    def test_stats_providers(self):
        """Test stats intent selects data providers."""
        providers = expand_providers_for_intent(Intent.STATS)
        
        # Should include stats providers
        assert "worldbank" in providers
        assert "oecd" in providers
        assert "imf" in providers
    
    def test_product_providers_without_keys(self):
        """Test product intent with no paid API keys."""
        # Simulate no API keys
        providers = expand_providers_for_intent(Intent.PRODUCT, available_keys={})
        
        # Should still return Wikipedia as fallback
        assert "wikipedia" in providers
    
    def test_news_providers(self):
        """Test news intent selects news providers."""
        providers = expand_providers_for_intent(Intent.NEWS)
        
        # Should include GDELT as free primary
        assert "gdelt" in providers
    
    def test_travel_providers(self):
        """Test travel intent selects travel providers."""
        providers = expand_providers_for_intent(Intent.TRAVEL)
        
        # Should include travel providers
        assert "wikivoyage" in providers
        assert "wikipedia" in providers
    
    def test_medical_providers(self):
        """Test medical intent selects medical providers."""
        providers = expand_providers_for_intent(Intent.MEDICAL)
        
        # Should include medical providers
        assert "pubmed" in providers
        assert "europepmc" in providers
    
    def test_generic_fallback(self):
        """Test generic intent has reasonable defaults."""
        providers = expand_providers_for_intent(Intent.GENERIC)
        
        # Should include basic providers
        assert "wikipedia" in providers
        assert "wikidata" in providers
    
    def test_deduplication(self):
        """Test that providers are deduplicated."""
        providers = expand_providers_for_intent(Intent.ENCYCLOPEDIA)
        
        # Check no duplicates
        assert len(providers) == len(set(providers))


class TestRateLimits:
    """Test provider rate limiting."""
    
    def test_nominatim_rate_limit(self):
        """Test Nominatim has correct rate limit."""
        rps = get_provider_rate_limit("nominatim")
        assert rps == 1.0  # OSM policy
    
    def test_sec_rate_limit(self):
        """Test SEC has conservative rate limit."""
        rps = get_provider_rate_limit("sec")
        assert rps == 0.5
    
    def test_serpapi_rate_limit(self):
        """Test SerpAPI has low rate limit to avoid 429s."""
        rps = get_provider_rate_limit("serpapi")
        assert rps == 0.2
    
    def test_openalex_rate_limit(self):
        """Test OpenAlex has higher rate limit."""
        rps = get_provider_rate_limit("openalex")
        assert rps == 10.0
    
    def test_environment_override(self):
        """Test environment variable overrides default rate limit."""
        # Set environment override
        os.environ["TEST_PROVIDER_RPS"] = "5.5"
        
        try:
            rps = get_provider_rate_limit("test_provider")
            assert rps == 5.5
        finally:
            # Clean up
            del os.environ["TEST_PROVIDER_RPS"]
    
    def test_invalid_environment_override(self):
        """Test invalid environment override falls back to default."""
        # Set invalid environment override
        os.environ["TEST_PROVIDER_RPS"] = "not_a_number"
        
        try:
            rps = get_provider_rate_limit("test_provider")
            assert rps == 1.0  # Default
        finally:
            # Clean up
            del os.environ["TEST_PROVIDER_RPS"]
    
    def test_unknown_provider_default(self):
        """Test unknown provider gets default rate limit."""
        rps = get_provider_rate_limit("unknown_provider_xyz")
        assert rps == 1.0  # Default


class TestProviderAvailability:
    """Test provider availability checking."""
    
    def test_free_provider_always_available(self):
        """Test free providers are always available."""
        assert _is_provider_available("wikipedia", {})
        assert _is_provider_available("wikidata", {})
        assert _is_provider_available("openalex", {})
        assert _is_provider_available("crossref", {})
    
    def test_paid_provider_needs_key(self):
        """Test paid providers need API keys."""
        # Without key
        assert not _is_provider_available("tavily", {})
        assert not _is_provider_available("brave", {})
        assert not _is_provider_available("serper", {})
        
        # With key
        assert _is_provider_available("tavily", {"tavily": "test_key"})
        assert _is_provider_available("brave", {"brave": "test_key"})
        assert _is_provider_available("serper", {"serper": "test_key"})
    
    def test_unpaywall_needs_email(self):
        """Test Unpaywall needs email configuration."""
        # Without email
        assert not _is_provider_available("unpaywall", {})
        
        # With email
        assert _is_provider_available("unpaywall", {"unpaywall": "test@example.com"})