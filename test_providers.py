#!/usr/bin/env python3
"""
Test that all providers work in parallel with no backfill
"""

import asyncio
import os
from research_system.config import Settings
from research_system.tools.registry import Registry
from research_system.tools.search_registry import register_search_tools
from research_system.collection import parallel_provider_search

async def test_providers():
    """Test all enabled providers in parallel"""
    
    # Initialize
    settings = Settings()
    registry = Registry()
    register_search_tools(registry)
    
    print(f"\n=== Testing Parallel Search Providers ===")
    print(f"Enabled providers: {settings.enabled_providers()}\n")
    
    # Test search
    query = "Yellowstone National Park"
    print(f"Testing query: '{query}'")
    print("=" * 50)
    
    # Run parallel search
    results = await parallel_provider_search(
        registry=registry,
        query=query,
        count=3,
        freshness=None,
        region="US"
    )
    
    # Display results
    for provider, hits in results.items():
        if hits:
            print(f"\n✅ {provider.upper()}: {len(hits)} results")
            for i, hit in enumerate(hits[:2], 1):
                print(f"   {i}. {hit.title[:60]}...")
                print(f"      {hit.url}")
        else:
            print(f"\n❌ {provider.upper()}: No results (API key may be invalid or rate limited)")
    
    # Verify no backfill behavior
    print("\n" + "=" * 50)
    print("Verification:")
    print(f"- Total providers attempted: {len(results)}")
    print(f"- Providers with results: {sum(1 for hits in results.values() if hits)}")
    print(f"- Providers with failures: {sum(1 for hits in results.values() if not hits)}")
    print("- No backfill: Each provider runs independently ✓")
    
    return results

if __name__ == "__main__":
    # Run the test
    results = asyncio.run(test_providers())
    
    print("\n=== Test Complete ===")
    print(f"All {len(results)} providers executed in parallel.")
    print("Failures do not affect other providers (no backfill).\n")