#!/usr/bin/env python3
"""
Test the domain-agnostic routing system
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_routing():
    """Test topic routing to disciplines"""
    logger.info("\n=== Testing Topic Routing ===")
    
    from research_system.router import route_topic
    from research_system.models import Discipline
    
    test_topics = [
        ("COVID-19 vaccine efficacy clinical trials", Discipline.MEDICINE),
        ("quantum computing arxiv papers 2024", Discipline.SCIENCE),
        ("SEC filing 10-K analysis Tesla", Discipline.FINANCE_ECON),
        ("CVE-2024-1234 vulnerability exploit", Discipline.SECURITY),
        ("global tourism recovery post-pandemic UNWTO", Discipline.TRAVEL_TOURISM),
        ("EU directive data privacy regulation", Discipline.LAW_POLICY),
        ("climate change IPCC report emissions", Discipline.CLIMATE_ENV),
        ("GitHub API performance benchmarks", Discipline.TECH_SOFTWARE),
        ("best restaurants in Paris", Discipline.GENERAL),
    ]
    
    passed = 0
    for topic, expected in test_topics:
        result = route_topic(topic)
        if result == expected:
            logger.info(f"✓ '{topic[:40]}...' -> {result.value}")
            passed += 1
        else:
            logger.error(f"✗ '{topic[:40]}...' -> {result.value} (expected {expected.value})")
    
    logger.info(f"\nRouting: {passed}/{len(test_topics)} passed")
    return passed == len(test_topics)


def test_policy_loading():
    """Test policy configurations"""
    logger.info("\n=== Testing Policy Loading ===")
    
    from research_system.policy import get_policy, POLICIES
    from research_system.models import Discipline
    
    success = True
    for discipline in Discipline:
        policy = get_policy(discipline)
        if policy:
            logger.info(f"✓ {discipline.value}: {len(policy.connectors)} connectors, "
                       f"{len(policy.anchor_templates)} templates, "
                       f"triangulation min: {policy.triangulation_min:.0%}")
        else:
            logger.error(f"✗ Failed to load policy for {discipline.value}")
            success = False
    
    return success


def test_anchor_building():
    """Test anchor query generation"""
    logger.info("\n=== Testing Anchor Query Building ===")
    
    from research_system.tools.anchor import build_anchors
    
    test_cases = [
        "COVID-19 vaccine effectiveness",
        "quantum computing advances",
        "tourism recovery trends 2025",
    ]
    
    success = True
    for topic in test_cases:
        anchors, discipline, policy = build_anchors(topic)
        if anchors:
            logger.info(f"✓ '{topic}' ({discipline.value}): {len(anchors)} anchors")
            for anchor in anchors[:3]:
                logger.info(f"  - {anchor}")
        else:
            logger.error(f"✗ No anchors generated for '{topic}'")
            success = False
    
    return success


def test_connectors():
    """Test connector registry"""
    logger.info("\n=== Testing Connector Registry ===")
    
    from research_system.connectors import REGISTRY
    
    active_connectors = [
        "crossref", "openalex", "gdelt", "pubmed"
    ]
    
    success = True
    for name in active_connectors:
        if name in REGISTRY:
            logger.info(f"✓ Connector '{name}' registered")
        else:
            logger.error(f"✗ Connector '{name}' not found")
            success = False
    
    logger.info(f"\nTotal connectors in registry: {len(REGISTRY)}")
    return success


def test_domain_priors():
    """Test domain prior scoring"""
    logger.info("\n=== Testing Domain Priors ===")
    
    from research_system.scoring import domain_prior_for
    
    test_cases = [
        ("COVID vaccine research", "https://pubmed.ncbi.nlm.nih.gov/12345", 0.9),  # High for medical
        ("tourism trends", "https://unwto.org/report", 0.9),  # High for tourism
        ("SEC filings", "https://sec.gov/edgar/10k", 0.9),  # High for finance
        ("random blog", "https://myblog.wordpress.com", 0.5),  # Low for any
    ]
    
    success = True
    for topic, url, min_expected in test_cases:
        score = domain_prior_for(topic, url)
        if score >= min_expected:
            logger.info(f"✓ '{topic}' + {url[:30]}... -> {score:.2f}")
        else:
            logger.error(f"✗ '{topic}' + {url[:30]}... -> {score:.2f} (expected >= {min_expected})")
            success = False
    
    return success


def test_integration():
    """Test basic integration"""
    logger.info("\n=== Testing Integration ===")
    
    try:
        from research_system.models import EvidenceCard, Discipline
        from research_system.router import route_topic
        from research_system.policy import get_policy
        
        # Create a test evidence card
        card = EvidenceCard(
            title="Test Article",
            url="https://doi.org/10.1234/test",
            snippet="Test snippet about quantum computing",
            provider="tavily",
            credibility_score=0.8,
            relevance_score=0.7,
            discipline=Discipline.SCIENCE,
            doi="10.1234/test"
        )
        
        # Route topic
        discipline = route_topic("quantum computing research")
        
        # Get policy
        policy = get_policy(discipline)
        
        logger.info(f"✓ Created evidence card with discipline: {card.discipline.value}")
        logger.info(f"✓ Routed topic to: {discipline.value}")
        logger.info(f"✓ Policy has {len(policy.connectors)} connectors")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Integration test failed: {e}")
        return False


def main():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("Testing Domain-Agnostic Routing System")
    logger.info("=" * 60)
    
    tests = [
        ("Topic Routing", test_routing),
        ("Policy Loading", test_policy_loading),
        ("Anchor Building", test_anchor_building),
        ("Connectors", test_connectors),
        ("Domain Priors", test_domain_priors),
        ("Integration", test_integration),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                logger.info(f"\n✓ {test_name} PASSED")
            else:
                failed += 1
                logger.error(f"\n✗ {test_name} FAILED")
        except Exception as e:
            failed += 1
            logger.error(f"\n✗ {test_name} FAILED with exception: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info(f"Results: {passed} passed, {failed} failed")
    logger.info("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())