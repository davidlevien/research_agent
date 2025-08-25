#!/usr/bin/env python3.11
"""Validate that all components are properly integrated."""

import os
import sys

def validate_integration():
    """Check that all components are wired together."""
    
    print("=" * 60)
    print("RESEARCH SYSTEM INTEGRATION VALIDATION")
    print("=" * 60)
    
    errors = []
    warnings = []
    
    # 1. Check imports
    print("\n1. Checking core imports...")
    try:
        from research_system.orchestrator import Orchestrator
        from research_system.routing.provider_router import choose_providers
        from research_system.collection_enhanced import collect_from_free_apis
        from research_system.providers.registry import PROVIDERS
        from research_system.tools.domain_norm import canonical_domain
        print("   ✅ All core modules importable")
    except ImportError as e:
        errors.append(f"Import error: {e}")
        print(f"   ❌ Import error: {e}")
    
    # 2. Check provider count
    print("\n2. Checking provider registry...")
    try:
        from research_system.providers.registry import PROVIDERS
        provider_count = len(PROVIDERS)
        print(f"   ✅ {provider_count} providers registered")
        
        # Check specific providers
        expected = ["openalex", "crossref", "worldbank", "oecd", "imf", 
                   "arxiv", "pubmed", "europepmc", "wikipedia", "gdelt"]
        missing = [p for p in expected if p not in PROVIDERS]
        if missing:
            warnings.append(f"Missing providers: {missing}")
            print(f"   ⚠️  Missing providers: {missing}")
        else:
            print(f"   ✅ All expected providers present")
    except Exception as e:
        errors.append(f"Provider check failed: {e}")
        print(f"   ❌ Provider check failed: {e}")
    
    # 3. Check orchestrator integration
    print("\n3. Checking orchestrator integration...")
    try:
        with open("research_system/orchestrator.py") as f:
            content = f.read()
        
        if "collection_enhanced" in content:
            print("   ✅ collection_enhanced imported")
        else:
            warnings.append("collection_enhanced not imported in orchestrator")
            print("   ⚠️  collection_enhanced not imported")
            
        if "choose_providers" in content:
            print("   ✅ Router integrated")
        else:
            warnings.append("Router not integrated in orchestrator")
            print("   ⚠️  Router not integrated")
            
        if "collect_from_free_apis" in content:
            print("   ✅ Free API collection integrated")
        else:
            warnings.append("Free API collection not integrated")
            print("   ⚠️  Free API collection not integrated")
    except Exception as e:
        errors.append(f"Orchestrator check failed: {e}")
        print(f"   ❌ Orchestrator check failed: {e}")
    
    # 4. Check rate limiting
    print("\n4. Checking rate limiting...")
    try:
        from research_system.providers.http import POLICY
        providers_with_limits = len(POLICY)
        print(f"   ✅ {providers_with_limits} providers have rate limits")
        
        # Check critical providers
        critical = ["openalex", "crossref", "arxiv", "pubmed", "overpass"]
        for p in critical:
            if p in POLICY:
                rps = POLICY[p].get("rps") or POLICY[p].get("min_interval_seconds")
                if rps:
                    print(f"   ✅ {p}: rate limit configured")
                else:
                    warnings.append(f"{p} missing rate limit")
            else:
                warnings.append(f"{p} missing from POLICY")
    except Exception as e:
        errors.append(f"Rate limit check failed: {e}")
        print(f"   ❌ Rate limit check failed: {e}")
    
    # 5. Check environment
    print("\n5. Checking environment...")
    contact_email = os.getenv("CONTACT_EMAIL")
    if contact_email:
        print(f"   ✅ CONTACT_EMAIL set: {contact_email}")
    else:
        warnings.append("CONTACT_EMAIL not set (required for API compliance)")
        print("   ⚠️  CONTACT_EMAIL not set")
    
    # 6. Test router
    print("\n6. Testing router...")
    try:
        from research_system.routing.provider_router import choose_providers
        
        test_topics = {
            "GDP inflation World Bank": ["worldbank", "oecd", "imf"],
            "randomized trial vaccine": ["pubmed", "europepmc"],
            "climate change emissions": ["oecd", "worldbank"]
        }
        
        for topic, expected in test_topics.items():
            decision = choose_providers(topic)
            found = [p for p in expected if p in decision.providers]
            if found:
                print(f"   ✅ '{topic[:20]}...' → {found[0]}")
            else:
                warnings.append(f"Router failed for '{topic}'")
                print(f"   ⚠️  '{topic[:20]}...' → no expected providers")
    except Exception as e:
        errors.append(f"Router test failed: {e}")
        print(f"   ❌ Router test failed: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    if not errors and not warnings:
        print("✅ ALL CHECKS PASSED - System fully integrated!")
        return 0
    
    if warnings:
        print(f"\n⚠️  {len(warnings)} warning(s):")
        for w in warnings:
            print(f"   - {w}")
    
    if errors:
        print(f"\n❌ {len(errors)} error(s):")
        for e in errors:
            print(f"   - {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(validate_integration())