"""Tests for pack-aware primary source detection and metrics."""

import pytest
from unittest.mock import Mock
from research_system.routing.topic_router import classify_topic_multi, classify_topic
from research_system.tools.domain_norm import is_primary_domain, normalize_domain, PRIMARY_CONFIG
from research_system.collect.filter import is_primary_source
from research_system.metrics_compute.triangulation import primary_share_in_triangulated
import re


class TestPackMerging:
    """Tests for multi-pack classification and merging."""
    
    def test_single_pack_classification(self):
        """Test classification with a single dominant pack."""
        query = "banking regulation changes 2025"
        packs = classify_topic_multi(query)
        assert "finance" in packs or "policy" in packs
        
    def test_multi_pack_classification(self):
        """Test classification with multiple relevant packs."""
        query = "cdc policy changes 2025"
        packs = classify_topic_multi(query)
        assert "policy" in packs or "health" in packs
        # Should match at least one, possibly both if complementary
        
    def test_complementary_pack_merging(self):
        """Test that complementary packs are merged."""
        query = "federal reserve monetary policy changes 2025"
        packs = classify_topic_multi(query)
        # Finance and policy are complementary
        assert len(packs) >= 1  # Should get at least one pack
        
    @pytest.mark.parametrize("query,expected_packs", [
        ("cdc policy changes 2025", {"policy", "health"}),
        ("bank capital rule changes 2025", {"policy", "finance"}),
        ("energy regulation updates 2025", {"policy", "energy"}),
        ("education policy reform 2025", {"policy", "education"}),
    ])
    def test_pack_merge_scenarios(self, query, expected_packs):
        """Test various pack merge scenarios."""
        packs = classify_topic_multi(query)
        # Should include at least one of the expected packs
        assert len(packs.intersection(expected_packs)) > 0
        
        
class TestPrimaryDomainDetection:
    """Tests for enhanced primary domain detection."""
    
    def test_canonical_domain_detection(self):
        """Test detection of canonical primary domains."""
        assert is_primary_domain("federalregister.gov")
        assert is_primary_domain("regulations.gov")
        assert is_primary_domain("congress.gov")
        assert is_primary_domain("cdc.gov")
        assert is_primary_domain("who.int")
        
    def test_pattern_based_detection(self):
        """Test pattern-based primary detection."""
        # .gov domains should match pattern
        assert is_primary_domain("example.gov")
        assert is_primary_domain("state.gov")
        assert is_primary_domain("city.gov")
        
        # .mil domains should match
        assert is_primary_domain("army.mil")
        assert is_primary_domain("navy.mil")
        
        # .int domains should match
        assert is_primary_domain("example.int")
        
    def test_pack_specific_domains(self):
        """Test pack-specific primary domains."""
        # Health pack domains
        health_domains = set(PRIMARY_CONFIG.get("health", {}).get("canonical", []))
        if health_domains:
            assert "cdc.gov" in health_domains or "hhs.gov" in health_domains
            assert is_primary_domain("cdc.gov", health_domains)
            
        # Policy pack domains
        policy_domains = set(PRIMARY_CONFIG.get("policy", {}).get("canonical", []))
        if policy_domains:
            assert "federalregister.gov" in policy_domains
            assert is_primary_domain("federalregister.gov", policy_domains)
            
    def test_normalize_domain(self):
        """Test domain normalization."""
        assert normalize_domain("https://www.example.com/page") == "example.com"
        assert normalize_domain("http://example.gov:8080") == "example.gov"
        assert normalize_domain("www.example.org") == "example.org"
        assert normalize_domain("EXAMPLE.COM") == "example.com"
        

class TestPrimaryShareMetrics:
    """Tests for primary share calculation with pack awareness."""
    
    def setup_method(self):
        """Set up test data."""
        self.cards = [
            Mock(source_domain="cdc.gov", id="1"),
            Mock(source_domain="example.com", id="2"),
            Mock(source_domain="federalregister.gov", id="3"),
            Mock(source_domain="news.com", id="4"),
            Mock(source_domain="hhs.gov", id="5"),
        ]
        
        self.para_clusters = [
            {"indices": [0, 1], "domains": ["cdc.gov", "example.com"]},
            {"indices": [2, 3], "domains": ["federalregister.gov", "news.com"]},
        ]
        
        self.structured_matches = [
            {"indices": [0, 4], "domains": ["cdc.gov", "hhs.gov"]},
        ]
        
    def test_primary_share_calculation_default(self):
        """Test primary share calculation with default domains."""
        share = primary_share_in_triangulated(
            self.cards, 
            self.para_clusters, 
            self.structured_matches
        )
        # Should recognize .gov domains as primary
        assert share > 0  # At least some primary sources
        
    def test_primary_share_with_pack_domains(self):
        """Test primary share with pack-specific domains."""
        pack_domains = {"cdc.gov", "hhs.gov", "federalregister.gov", "regulations.gov"}
        
        share = primary_share_in_triangulated(
            self.cards,
            self.para_clusters,
            self.structured_matches,
            primary_domains=pack_domains
        )
        # With pack domains, should recognize more primaries
        assert share >= 0.5  # At least 50% primary
        
    def test_primary_share_with_patterns(self):
        """Test primary share with regex patterns."""
        patterns = [re.compile(r"\.gov$", re.I)]
        
        share = primary_share_in_triangulated(
            self.cards,
            self.para_clusters,
            self.structured_matches,
            primary_patterns=patterns
        )
        # Should match all .gov domains
        assert share > 0
        
    def test_empty_triangulation(self):
        """Test with no triangulated evidence."""
        share = primary_share_in_triangulated([], [], [])
        assert share == 0.0
        
        
class TestBackfillIntegration:
    """Tests for primary backfill with pack awareness."""
    
    def test_backfill_uses_pack_domains(self):
        """Test that backfill uses pack-specific domains for queries."""
        from research_system.enrich.primary_fill import _queries_for_family
        
        family = {"key": "test metric 50%", "domains": ["example.com"]}
        pack_domains = {"cdc.gov", "hhs.gov", "fda.gov"}
        
        queries = _queries_for_family(family, pack_domains)
        
        # Should create site-specific queries
        assert any("site:cdc.gov" in q for q in queries)
        assert any("site:hhs.gov" in q for q in queries)
        
    def test_backfill_primary_detection(self):
        """Test that backfill correctly identifies primary sources."""
        from research_system.tools.domain_norm import is_primary_domain
        
        pack_domains = {"cdc.gov", "federalregister.gov"}
        patterns = [re.compile(r"\.gov$")]
        
        # Test various URLs
        assert is_primary_domain("https://cdc.gov/page", pack_domains, patterns)
        assert is_primary_domain("https://random.gov/doc", pack_domains, patterns)
        assert not is_primary_domain("https://example.com", pack_domains, patterns)
        

class TestRouterIntegration:
    """Integration tests for topic router with pack awareness."""
    
    def test_router_provides_pack_info(self):
        """Test that router provides pack information for downstream use."""
        from research_system.routing.topic_router import route_query
        
        decision = route_query("cdc policy changes 2025")
        assert decision.topic_match.topic_key in ["policy", "health", "general"]
        assert len(decision.providers) > 0
        
    def test_off_topic_filtering_with_pack(self):
        """Test off-topic filtering uses pack configuration."""
        from research_system.routing.topic_router import is_off_topic
        
        # Policy-related content
        content = {
            "title": "New Federal Rule on Healthcare",
            "snippet": "The federal register published a final rule regarding healthcare policy changes effective 2025."
        }
        
        # Should not be off-topic for policy pack
        assert not is_off_topic(content, "policy")
        
        # Unrelated content
        unrelated = {
            "title": "Celebrity News",
            "snippet": "Latest celebrity gossip and entertainment news."
        }
        
        # Should be off-topic for policy pack
        assert is_off_topic(unrelated, "policy")
        

class TestEndToEndPrimaryShare:
    """End-to-end test for primary share improvement."""
    
    @pytest.mark.integration
    def test_cdc_policy_query_primary_share(self):
        """Test that CDC policy query achieves adequate primary share."""
        # This would be an integration test with the full orchestrator
        # Marking as integration so it can be skipped in unit test runs
        pass
        

if __name__ == "__main__":
    pytest.main([__file__, "-v"])