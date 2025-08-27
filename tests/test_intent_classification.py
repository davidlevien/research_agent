"""Tests for intent classification system."""

import pytest
from research_system.intent.classifier import (
    Intent, classify, detect_geographic_ambiguity, get_confidence_threshold
)


class TestIntentClassification:
    """Test intent classification functionality."""
    
    def test_encyclopedia_intent(self):
        """Test encyclopedia intent detection."""
        queries = [
            "origins of the platypus",
            "history of European church",
            "what is quantum computing",
            "who is Albert Einstein",
            "evolution of the internet"
        ]
        
        for query in queries:
            intent = classify(query)
            assert intent == Intent.ENCYCLOPEDIA, f"Failed for: {query}"
    
    def test_product_intent(self):
        """Test product/shopping intent detection."""
        queries = [
            "best desk fans",
            "top laptops under $1000",
            "iPhone vs Samsung review",
            "cheapest flights to Paris",
            "is MacBook Pro worth it"
        ]
        
        for query in queries:
            intent = classify(query)
            assert intent == Intent.PRODUCT, f"Failed for: {query}"
    
    def test_local_intent(self):
        """Test local search intent detection."""
        queries = [
            "coffee shops near me",
            "restaurants in Portland, OR",
            "pharmacy open now",
            "closest gas station",
            "hotels nearby"
        ]
        
        for query in queries:
            intent = classify(query)
            assert intent == Intent.LOCAL, f"Failed for: {query}"
    
    def test_news_intent(self):
        """Test news intent detection."""
        queries = [
            "latest AI developments",
            "breaking news today",
            "current events in Europe",
            "what happened yesterday in tech",
            "recent climate change news"
        ]
        
        for query in queries:
            intent = classify(query)
            assert intent == Intent.NEWS, f"Failed for: {query}"
    
    def test_academic_intent(self):
        """Test academic intent detection."""
        queries = [
            "systematic review of COVID vaccines",
            "meta-analysis sleep quality",
            "peer-reviewed studies on meditation",
            "doi:10.1038/nature12373",
            "arxiv:2301.08727"
        ]
        
        for query in queries:
            intent = classify(query)
            assert intent == Intent.ACADEMIC, f"Failed for: {query}"
    
    def test_stats_intent(self):
        """Test statistics/data intent detection."""
        queries = [
            "GDP growth rate 2024",
            "unemployment statistics USA",
            "CPI index trends",
            "dataset on climate change",
            "time series analysis stock market"
        ]
        
        for query in queries:
            intent = classify(query)
            assert intent == Intent.STATS, f"Failed for: {query}"
    
    def test_travel_intent(self):
        """Test travel intent detection."""
        queries = [
            "itinerary for Japan trip",
            "best beaches in Thailand",
            "where to stay in Paris",
            "visa requirements for Brazil",
            "tourist attractions Rome"
        ]
        
        for query in queries:
            intent = classify(query)
            assert intent == Intent.TRAVEL, f"Failed for: {query}"
    
    def test_howto_intent(self):
        """Test how-to intent detection."""
        queries = [
            "how to build a website",
            "tutorial Python programming",
            "step by step cake recipe",
            "guide to investing",
            "DIY home renovation"
        ]
        
        for query in queries:
            intent = classify(query)
            assert intent == Intent.HOWTO, f"Failed for: {query}"
    
    def test_regulatory_intent(self):
        """Test regulatory/compliance intent detection."""
        queries = [
            "Apple 10-k filing",
            "SEC regulations",
            "compliance requirements",
            "latest 8-k filings",
            "sec.gov disclosure"
        ]
        
        for query in queries:
            intent = classify(query)
            assert intent == Intent.REGULATORY, f"Failed for: {query}"
    
    def test_medical_intent(self):
        """Test medical intent detection."""
        queries = [
            "symptoms of diabetes",
            "treatment for hypertension",
            "side effects of aspirin",
            "diagnosis criteria autism",
            "cure for cancer research"
        ]
        
        for query in queries:
            intent = classify(query)
            assert intent == Intent.MEDICAL, f"Failed for: {query}"
    
    def test_generic_fallback(self):
        """Test generic intent fallback."""
        queries = [
            "random thoughts",
            "interesting facts",
            "general information",
            "something about nothing",
            "miscellaneous query"
        ]
        
        for query in queries:
            intent = classify(query)
            assert intent == Intent.GENERIC, f"Failed for: {query}"


class TestGeographicAmbiguity:
    """Test geographic ambiguity detection."""
    
    def test_portland_ambiguity(self):
        """Test Portland OR/ME ambiguity detection."""
        locations = detect_geographic_ambiguity("best beaches in portland")
        assert locations is not None
        assert "Portland, OR" in locations or "Portland, Oregon" in locations
        assert "Portland, ME" in locations or "Portland, Maine" in locations
    
    def test_portland_no_ambiguity_with_state(self):
        """Test no ambiguity when state is specified."""
        locations = detect_geographic_ambiguity("best beaches in Portland, OR")
        assert locations is None
    
    def test_cambridge_ambiguity(self):
        """Test Cambridge MA/UK ambiguity detection."""
        locations = detect_geographic_ambiguity("universities in cambridge")
        assert locations is not None
        assert "Cambridge, MA" in locations or "Cambridge, Massachusetts" in locations
        assert "Cambridge, UK" in locations
    
    def test_no_ambiguity_for_unique_cities(self):
        """Test no ambiguity for unique city names."""
        locations = detect_geographic_ambiguity("restaurants in Tokyo")
        assert locations is None


class TestConfidenceThresholds:
    """Test intent-specific confidence thresholds."""
    
    def test_product_thresholds(self):
        """Test product intent has lower thresholds."""
        min_tri, min_sources = get_confidence_threshold(Intent.PRODUCT)
        assert min_tri == 0.20
        assert min_sources == 3
    
    def test_local_thresholds(self):
        """Test local intent has lowest thresholds."""
        min_tri, min_sources = get_confidence_threshold(Intent.LOCAL)
        assert min_tri == 0.15
        assert min_sources == 2
    
    def test_academic_thresholds(self):
        """Test academic intent has higher thresholds."""
        min_tri, min_sources = get_confidence_threshold(Intent.ACADEMIC)
        assert min_tri == 0.35
        assert min_sources == 3
    
    def test_medical_thresholds(self):
        """Test medical intent has highest thresholds."""
        min_tri, min_sources = get_confidence_threshold(Intent.MEDICAL)
        assert min_tri == 0.35
        assert min_sources == 3
    
    def test_generic_thresholds(self):
        """Test generic intent has moderate thresholds."""
        min_tri, min_sources = get_confidence_threshold(Intent.GENERIC)
        assert min_tri == 0.25
        assert min_sources == 2