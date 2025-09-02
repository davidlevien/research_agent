#!/usr/bin/env python3
"""Test script to verify v8.26.0 fixes for research system."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_intent_classification():
    """Test that travel queries are properly classified."""
    from research_system.intent.classifier import classify, Intent
    
    test_cases = [
        ("latest travel & tourism trends", Intent.TRAVEL),
        ("travel industry outlook 2024", Intent.TRAVEL),
        ("tourism recovery forecast", Intent.TRAVEL),
        ("global macro trends", Intent.MACRO_TRENDS),
        ("economic trends 2024", Intent.MACRO_TRENDS),
        ("yellowstone national park", Intent.ENCYCLOPEDIA),
    ]
    
    print("\n=== Testing Intent Classification ===")
    for query, expected in test_cases:
        actual = classify(query)
        status = "✓" if actual == expected else "✗"
        print(f"{status} '{query}' -> {actual.value} (expected {expected.value})")
    print()

def test_provider_mapping():
    """Test that intents map to correct providers."""
    from research_system.intent.classifier import Intent
    from research_system.providers.intent_registry import expand_providers_for_intent
    
    print("=== Testing Provider Mapping ===")
    
    # Test TRAVEL intent
    travel_providers = expand_providers_for_intent(Intent.TRAVEL)
    print(f"TRAVEL providers: {travel_providers[:5]}")
    assert "wikivoyage" in travel_providers or "tavily" in travel_providers, "Travel should have travel-related providers"
    
    # Test MACRO_TRENDS intent (now should have providers)
    macro_providers = expand_providers_for_intent(Intent.MACRO_TRENDS)
    print(f"MACRO_TRENDS providers: {macro_providers[:5]}")
    assert len(macro_providers) > 0, "MACRO_TRENDS should have providers"
    assert any(p in macro_providers for p in ["tavily", "brave", "serper", "wikipedia"]), "Should include search or knowledge providers"
    print()

def test_canonical_id_import():
    """Test that canonical_id is properly accessible."""
    print("=== Testing canonical_id Import ===")
    try:
        from research_system.evidence.canonicalize import canonical_id
        from research_system.utils.ids import canonical_id as util_canonical_id
        
        # Test the function works
        test_str = "test_string"
        result1 = canonical_id(type('Card', (), {'url': 'http://example.com'})())
        result2 = util_canonical_id(test_str)
        
        print(f"✓ canonical_id imported successfully from evidence.canonicalize")
        print(f"✓ canonical_id imported successfully from utils.ids")
        print(f"  Sample output: {result2[:8]}...")
    except ImportError as e:
        print(f"✗ Import error: {e}")
    print()

def test_oecd_endpoints():
    """Test that OECD endpoints are updated."""
    from research_system.providers.oecd import DATAFLOW_URLS
    
    print("=== Testing OECD Endpoints ===")
    print(f"Primary URL: {DATAFLOW_URLS[0]}")
    
    # Check that new endpoints are present
    assert any("sdmx.oecd.org" in url for url in DATAFLOW_URLS), "Should include new sdmx.oecd.org endpoint"
    
    # Check that invalid mirror is removed
    assert not any("stats-nxd.oecd.org" in url for url in DATAFLOW_URLS), "Invalid mirror should be removed"
    
    print(f"✓ OECD endpoints updated correctly")
    print(f"  Total endpoints: {len(DATAFLOW_URLS)}")
    for i, url in enumerate(DATAFLOW_URLS, 1):
        print(f"  {i}. {url}")
    print()

def test_robots_allowlist():
    """Test that API subdomains are in robots allowlist."""
    from research_system.net.robots import PUBLIC_ALLOWLIST
    
    print("=== Testing Robots Allowlist ===")
    
    required_domains = [
        "data.worldbank.org",
        "api.worldbank.org",
        "sdmx.oecd.org",
        "stats.oecd.org",
        "dataservices.imf.org"
    ]
    
    for domain in required_domains:
        if domain in PUBLIC_ALLOWLIST:
            print(f"✓ {domain} in allowlist")
        else:
            print(f"✗ {domain} NOT in allowlist")
    
    print(f"\nTotal domains in allowlist: {len(PUBLIC_ALLOWLIST)}")
    print()

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Testing v8.26.0 Fixes for Research System")
    print("="*60)
    
    test_intent_classification()
    test_provider_mapping()
    test_canonical_id_import()
    test_oecd_endpoints()
    test_robots_allowlist()
    
    print("="*60)
    print("All tests completed!")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()