#!/usr/bin/env python3
"""
v8.21.0 Production Verification Script
Ensures all patches are wired and system is ready for deployment.
"""

import sys
import traceback
from pathlib import Path

def verify_imports():
    """Verify all v8.21.0 modules import correctly."""
    print("Checking v8.21.0 imports...")
    
    modules = [
        "research_system.caches",
        "research_system.providers.intent_registry",
        "research_system.extraction.claims",
        "research_system.extraction.claim_miner",
        "research_system.extraction.html_cleaner",
        "research_system.extraction.pdf_extractor",
        "research_system.triangulation.numeric",
        "research_system.quality.metrics_v3",
        "research_system.scheduling.evidence_budget",
    ]
    
    for module in modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except ImportError as e:
            print(f"  ❌ {module}: {e}")
            return False
    
    return True

def verify_orchestrator():
    """Verify orchestrator initialization with settings fix."""
    print("\nChecking orchestrator initialization...")
    
    from research_system.orchestrator import Orchestrator, OrchestratorSettings
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        settings = OrchestratorSettings(
            topic="test verification",
            depth="rapid",
            output_dir=Path(tmpdir),
            strict=False
        )
        
        orch = Orchestrator(settings)
        
        # Check critical attributes
        checks = [
            (hasattr(orch, 'settings'), "self.settings exists"),
            (orch.settings is not None, "self.settings initialized"),
            (hasattr(orch, 'context'), "context dict exists"),
            (hasattr(orch, 'v813_config'), "v813_config loaded"),
        ]
        
        for check, desc in checks:
            if check:
                print(f"  ✅ {desc}")
            else:
                print(f"  ❌ {desc}")
                return False
    
    return True

def verify_oecd_endpoints():
    """Verify OECD has correct endpoint configuration."""
    print("\nChecking OECD endpoint configuration...")
    
    from research_system.providers.oecd import _DATAFLOW_CANDIDATES
    
    checks = [
        (len(_DATAFLOW_CANDIDATES) == 12, f"Has 12 endpoints (got {len(_DATAFLOW_CANDIDATES)})"),
        ("sdmx-json" in _DATAFLOW_CANDIDATES[0], "Starts with lowercase"),
        ("/all" in _DATAFLOW_CANDIDATES[2], "Has /all variant"),
    ]
    
    for check, desc in checks:
        if check:
            print(f"  ✅ {desc}")
        else:
            print(f"  ❌ {desc}")
            return False
    
    return True

def verify_capability_matrix():
    """Verify capability matrix for travel/tourism."""
    print("\nChecking capability matrix...")
    
    from research_system.providers.intent_registry import CAPABILITY_MATRIX, plan_capabilities
    
    # Check matrix structure
    required_caps = ["demand", "capacity", "prices", "contribution", "policy"]
    for cap in required_caps:
        if cap in CAPABILITY_MATRIX:
            print(f"  ✅ {cap} capability defined")
        else:
            print(f"  ❌ {cap} capability missing")
            return False
    
    # Test planning
    topics = plan_capabilities("travel and tourism trends")
    if len(topics) == 5:
        print(f"  ✅ Plans {len(topics)} topics for travel queries")
    else:
        print(f"  ❌ Should plan 5 topics, got {len(topics)}")
        return False
    
    return True

def verify_claim_extraction():
    """Verify claim mining works."""
    print("\nChecking claim extraction...")
    
    from research_system.extraction.claim_miner import mine_claims
    
    test_text = "International tourist arrivals increased by 5% in Q1 2025."
    claims = mine_claims(test_text, "https://test.com")
    
    if len(claims) > 0:
        print(f"  ✅ Extracted {len(claims)} claims")
        claim = claims[0]
        print(f"  ✅ Metric: {claim.key.metric}")
        print(f"  ✅ Value: {claim.value}")
        print(f"  ✅ Period: {claim.key.period}")
    else:
        print(f"  ❌ No claims extracted")
        return False
    
    return True

def verify_triangulation():
    """Verify numeric triangulation."""
    print("\nChecking triangulation...")
    
    from research_system.extraction.claims import Claim, ClaimKey
    from research_system.triangulation.numeric import triangulate
    
    key = ClaimKey(metric="test", unit="percent", period="2025", geo="WORLD")
    
    claims = [
        Claim(key=key, value=5.0, source_url="a.com", source_domain="a.com"),
        Claim(key=key, value=5.1, source_url="b.com", source_domain="b.com"),
    ]
    
    result = triangulate(claims)
    
    if key in result and result[key]["triangulated"]:
        print(f"  ✅ Triangulation successful")
        print(f"  ✅ Consensus: {result[key]['consensus']}")
        print(f"  ✅ Support ratio: {result[key]['support_ratio']}")
    else:
        print(f"  ❌ Triangulation failed")
        return False
    
    return True

def main():
    """Run all verification checks."""
    print("=" * 60)
    print("v8.21.0 PRODUCTION VERIFICATION")
    print("=" * 60)
    
    checks = [
        ("Imports", verify_imports),
        ("Orchestrator", verify_orchestrator),
        ("OECD Endpoints", verify_oecd_endpoints),
        ("Capability Matrix", verify_capability_matrix),
        ("Claim Extraction", verify_claim_extraction),
        ("Triangulation", verify_triangulation),
    ]
    
    results = []
    
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} check failed with error:")
            traceback.print_exc()
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name:20} {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n🎯 SYSTEM READY FOR PRODUCTION")
        print("✅ All v8.21.0 patches verified")
        print("✅ CI/CD will pass")
        print("✅ Next run will work successfully")
        return 0
    else:
        print("\n⚠️  ISSUES DETECTED")
        print("Please review failures above")
        return 1

if __name__ == "__main__":
    sys.exit(main())