"""
Comprehensive test suite for PE-grade generalized topic router.

Tests topic classification, provider selection, query refinement,
and off-topic filtering across all domain packs.
"""

import pytest
from unittest.mock import patch, MagicMock
from research_system.routing.topic_router import (
    classify_topic, 
    providers_for_topic,
    refine_query,
    is_off_topic,
    route_query,
    TopicMatch,
    RouterDecision,
    TOPIC_PACKS,
    PROVIDERS_CONFIG
)

class TestTopicClassification:
    """Test topic classification accuracy across all domain packs."""
    
    def test_classify_macroeconomics_topic(self):
        """Test macroeconomics topic classification."""
        query = "GDP growth inflation rate 2025 OECD countries"
        result = classify_topic(query)
        
        assert result.topic_key == "macroeconomics"
        assert result.score > 0
        assert result.anchors_hit >= 2  # Should hit "gdp", "inflation", "oecd"
        assert result.confidence > 0.5
        assert "gdp" in result.matched_aliases
        assert "inflation" in result.matched_aliases
    
    def test_classify_health_topic(self):
        """Test health/medical topic classification."""
        query = "COVID-19 incidence prevalence WHO clinical trial randomized"
        result = classify_topic(query)
        
        assert result.topic_key == "health"
        assert result.score > 0
        assert result.anchors_hit >= 2  # Should hit "who", "clinical"
        assert "incidence" in result.matched_aliases
        assert "prevalence" in result.matched_aliases
    
    def test_classify_technology_topic(self):
        """Test technology topic classification."""
        query = "artificial intelligence machine learning AI adoption software cloud computing"
        result = classify_topic(query)
        
        assert result.topic_key == "technology"
        assert result.score > 0
        assert result.anchors_hit >= 2  # Should hit "ai", "software", "cloud"
        assert "ai" in result.matched_aliases
        assert "artificial intelligence" in result.matched_aliases
    
    def test_classify_climate_topic(self):
        """Test climate/environmental topic classification."""
        query = "CO2 emissions temperature anomaly IPCC climate change Paris Agreement"
        result = classify_topic(query)
        
        assert result.topic_key == "climate"  
        assert result.score > 0
        assert result.anchors_hit >= 2  # Should hit "ipcc", "emissions", "co2"
        assert "co2" in result.matched_aliases
        assert "emissions" in result.matched_aliases
    
    def test_classify_tourism_topic(self):
        """Test tourism/travel topic classification."""
        query = "tourism arrivals UNWTO hotel occupancy RevPAR visitor spend recovery"
        result = classify_topic(query)
        
        assert result.topic_key == "travel_tourism"
        assert result.score > 0
        assert result.anchors_hit >= 3  # Should hit "unwto", "tourism", "occupancy", "revpar"
        assert "tourism" in result.matched_aliases
        assert "arrivals" in result.matched_aliases
    
    def test_classify_general_fallback(self):
        """Test fallback to general for unmatched topics."""
        query = "random unmatched query about nothing specific xyz123"
        result = classify_topic(query)
        
        # Should fall back to general with low scores
        assert result.topic_key == "general" or result.score < 1.0
        assert result.confidence < 0.5
    
    def test_classify_empty_query(self):
        """Test handling of empty/None queries."""
        result = classify_topic("")
        assert result.topic_key == "general"
        assert result.score == 0.0
        
        result = classify_topic(None)
        assert result.topic_key == "general"
        assert result.score == 0.0

class TestProviderSelection:
    """Test provider selection strategies across topics."""
    
    def test_providers_for_macroeconomics(self):
        """Test macro providers include WB, OECD, IMF, FRED."""
        providers = providers_for_topic("macroeconomics", "high_precision")
        
        expected_macro = {"worldbank", "oecd", "imf", "fred", "eurostat"}
        selected_set = set(providers)
        
        # Should include most expected macro providers
        assert len(expected_macro & selected_set) >= 3
        assert "worldbank" in providers
        assert "oecd" in providers
    
    def test_providers_for_health(self):
        """Test health providers include PubMed, EuropePMC, academic sources."""
        providers = providers_for_topic("health", "academic_focus")
        
        expected_health = {"pubmed", "europepmc", "openalex", "crossref"}
        selected_set = set(providers)
        
        # Should include health-specific providers
        assert len(expected_health & selected_set) >= 2
        # Academic focus should prioritize scholarly sources
        assert providers[0] in ["openalex", "pubmed", "europepmc", "crossref"]
    
    def test_providers_for_technology(self):
        """Test tech providers include arXiv, OpenAlex, web search."""
        providers = providers_for_topic("technology", "broad_coverage")
        
        expected_tech = {"arxiv", "openalex", "brave", "tavily"}
        selected_set = set(providers)
        
        assert len(expected_tech & selected_set) >= 2
        # Should include both academic and web sources
        assert any(p in providers for p in ["arxiv", "openalex"])
        assert any(p in providers for p in ["brave", "tavily", "serpapi"])
    
    def test_providers_respect_max_limit(self):
        """Test provider count respects strategy max_providers."""
        providers = providers_for_topic("general", "high_precision")
        assert len(providers) <= 6  # high_precision max is 6
        
        providers = providers_for_topic("general", "broad_coverage")
        assert len(providers) <= 8  # broad_coverage max is 8
    
    def test_providers_fallback_for_unknown_topic(self):
        """Test fallback providers for unknown topics."""
        providers = providers_for_topic("unknown_topic_xyz")
        
        # Should still return some providers
        assert len(providers) > 0
        # Should include web search providers as fallback
        assert any(p in providers for p in ["brave", "tavily", "wikipedia"])
    
    def test_providers_different_strategies(self):
        """Test different strategies return different provider mixes."""
        high_precision = providers_for_topic("macroeconomics", "high_precision")
        broad_coverage = providers_for_topic("macroeconomics", "broad_coverage") 
        academic_focus = providers_for_topic("macroeconomics", "academic_focus")
        
        # Strategies should produce different results
        assert high_precision != broad_coverage
        assert high_precision != academic_focus
        
        # High precision should prioritize authoritative sources
        assert high_precision[0] in ["worldbank", "oecd", "imf", "fred"]
        
        # Academic focus should prioritize scholarly sources  
        assert academic_focus[0] in ["openalex", "crossref", "arxiv"]

class TestQueryRefinement:
    """Test query refinement for providers and topics."""
    
    def test_refine_with_topic_expansions(self):
        """Test query expansion with topic-specific terms."""
        original = "economic growth 2025"
        refined = refine_query(original, "worldbank", "macroeconomics")
        
        # Should include expansions from macroeconomics pack
        assert original in refined
        assert "GDP" in refined or "inflation rate" in refined
        assert " AND " in refined  # Should use AND logic
    
    def test_refine_with_provider_sites(self):
        """Test site-specific refinements for providers."""
        original = "climate policy"
        refined = refine_query(original, "oecd", "climate")
        
        # Should include OECD site refiners
        assert "site:oecd.org" in refined
        assert original in refined
    
    def test_refine_no_changes_for_general(self):
        """Test minimal refinement for general providers."""
        original = "test query"
        refined = refine_query(original, "wikipedia", "general")
        
        # General topic has no expansions, wikipedia has site refiner
        assert "site:wikipedia.org" in refined
    
    def test_refine_empty_query(self):
        """Test handling of empty queries."""
        assert refine_query("", "worldbank", "macroeconomics") == ""
        assert refine_query(None, "worldbank", "macroeconomics") is None
    
    def test_refine_combines_expansions_and_sites(self):
        """Test combination of expansions and site refiners."""
        original = "tourism recovery"
        refined = refine_query(original, "worldbank", "travel_tourism")
        
        # Should have both expansions AND site refiners
        assert original in refined
        assert "site:worldbank.org" in refined
        assert "tourism arrivals" in refined or "UNWTO" in refined

class TestOffTopicFiltering:
    """Test off-topic content filtering."""
    
    def test_filter_off_topic_macro(self):
        """Test filtering non-economic content for macro topics."""
        # Relevant content should pass
        relevant = {
            "title": "GDP Growth Rates OECD Countries 2025",
            "snippet": "Economic indicators show GDP growth inflation trends"
        }
        assert not is_off_topic(relevant, "macroeconomics")
        
        # Irrelevant content should be filtered
        irrelevant = {
            "title": "Cat Videos and Entertainment News", 
            "snippet": "Latest celebrity gossip and funny cat compilation"
        }
        assert is_off_topic(irrelevant, "macroeconomics")
    
    def test_filter_off_topic_health(self):
        """Test filtering non-medical content for health topics."""
        relevant = {
            "title": "WHO Clinical Trial Results COVID-19",
            "snippet": "Systematic review of vaccine efficacy and safety data"
        }
        assert not is_off_topic(relevant, "health")
        
        irrelevant = {
            "title": "Sports Car Racing Results",
            "snippet": "Formula 1 championship standings and race highlights"  
        }
        assert is_off_topic(irrelevant, "health")
    
    def test_filter_respects_min_jaccard(self):
        """Test Jaccard similarity threshold filtering."""
        # Content with some overlap but below threshold
        marginal = {
            "title": "Investment Banking Career Advice",
            "snippet": "How to break into finance and banking sector jobs"
        }
        
        # For macroeconomics with min_jaccard 0.10, this should be filtered
        # as it has low similarity to macro aliases
        assert is_off_topic(marginal, "macroeconomics")
    
    def test_filter_empty_content(self):
        """Test filtering of empty content."""
        empty = {"title": "", "snippet": ""}
        assert is_off_topic(empty, "macroeconomics")
        
        missing = {}
        assert is_off_topic(missing, "health")
    
    def test_filter_required_terms(self):
        """Test must_contain_any requirement."""
        # Content without required terms should be filtered
        no_required_terms = {
            "title": "Generic Business Report",
            "snippet": "Corporate quarterly results and market analysis"
        }
        
        # Health topics require health-specific terms
        assert is_off_topic(no_required_terms, "health")

class TestFullRoutingPipeline:
    """Test complete routing pipeline integration."""
    
    def test_route_macroeconomics_query(self):
        """Test complete routing for macroeconomics query."""
        query = "GDP inflation unemployment OECD 2025 economic outlook"
        decision = route_query(query, "high_precision")
        
        assert decision.topic_match.topic_key == "macroeconomics"
        assert decision.topic_match.confidence > 0.5
        assert len(decision.providers) > 0
        assert decision.strategy_used == "high_precision"
        
        # Should have authoritative macro providers
        expected_providers = {"worldbank", "oecd", "imf", "fred"}
        assert len(set(decision.providers) & expected_providers) >= 2
        
        # Should have query refinements
        assert len(decision.query_refinements) > 0
        assert decision.reasoning
    
    def test_route_health_query_academic_focus(self):
        """Test routing health query with academic strategy."""
        query = "COVID-19 vaccine efficacy clinical trial WHO systematic review"
        decision = route_query(query, "academic_focus")
        
        assert decision.topic_match.topic_key == "health"
        assert decision.strategy_used == "academic_focus" 
        
        # Academic focus should prioritize scholarly sources
        academic_providers = {"openalex", "pubmed", "europepmc", "crossref"}
        assert len(set(decision.providers[:3]) & academic_providers) >= 2
    
    def test_route_general_query_broad_coverage(self):
        """Test routing general query with broad coverage."""
        query = "renewable energy trends global market analysis"
        decision = route_query(query, "broad_coverage")
        
        # Should classify and provide broad provider coverage
        assert len(decision.providers) >= 5
        assert decision.strategy_used == "broad_coverage"
        
        # Should include web search providers for broad coverage
        web_providers = {"brave", "tavily", "serpapi"}
        assert len(set(decision.providers) & web_providers) >= 2

class TestBackwardCompatibility:
    """Test backward compatibility with existing codebase."""
    
    def test_choose_providers_legacy_interface(self):
        """Test legacy choose_providers function works."""
        from research_system.routing.topic_router import choose_providers
        
        decision = choose_providers("GDP inflation economic growth")
        
        # Should return legacy RouterDecision format
        assert hasattr(decision, 'categories')
        assert hasattr(decision, 'providers') 
        assert hasattr(decision, 'reason')
        
        assert isinstance(decision.categories, list)
        assert isinstance(decision.providers, list)
        assert len(decision.providers) > 0

class TestConfigurationLoading:
    """Test YAML configuration loading and error handling."""
    
    def test_topic_packs_loaded(self):
        """Test topic packs configuration is loaded."""
        assert TOPIC_PACKS
        assert "general" in TOPIC_PACKS
        assert "macroeconomics" in TOPIC_PACKS
        assert "health" in TOPIC_PACKS
        assert "technology" in TOPIC_PACKS
        
        # Validate pack structure
        for pack_name, pack_config in TOPIC_PACKS.items():
            assert "aliases" in pack_config
            assert isinstance(pack_config["aliases"], list)
            if "anchors" in pack_config:
                assert isinstance(pack_config["anchors"], list)
    
    def test_providers_config_loaded(self):
        """Test provider capabilities configuration is loaded."""
        assert PROVIDERS_CONFIG
        assert "worldbank" in PROVIDERS_CONFIG
        assert "oecd" in PROVIDERS_CONFIG
        assert "brave" in PROVIDERS_CONFIG
        
        # Validate provider structure
        for provider_name, provider_config in PROVIDERS_CONFIG.items():
            assert "topics" in provider_config
            assert isinstance(provider_config["topics"], list)
            if "query_refiners" in provider_config:
                assert isinstance(provider_config["query_refiners"], list)

class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_missing_config_graceful_fallback(self):
        """Test graceful handling when configs are missing."""
        with patch('research_system.routing.topic_router.TOPIC_PACKS', {}):
            result = classify_topic("test query")
            assert result.topic_key == "general"
            assert result.score == 0.0
    
    def test_invalid_strategy_fallback(self):
        """Test fallback for invalid selection strategy."""
        providers = providers_for_topic("macroeconomics", "invalid_strategy_xyz")
        
        # Should fall back to broad_coverage or return some providers
        assert len(providers) > 0
    
    def test_unicode_normalization(self):
        """Test Unicode text normalization."""
        query = "café résumé naïve coöperation"  # Unicode characters
        result = classify_topic(query)
        
        # Should not crash and should classify appropriately
        assert result.topic_key in TOPIC_PACKS or result.topic_key == "general"
    
    @pytest.mark.parametrize("bad_input", [None, "", "   ", "\n\t\r"])
    def test_empty_input_handling(self, bad_input):
        """Test handling of various empty inputs."""
        result = classify_topic(bad_input)
        assert result.topic_key == "general"
        assert result.score == 0.0
        assert result.confidence == 0.0