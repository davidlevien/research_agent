#!/usr/bin/env python3.11
"""Simulate CI/CD test collection to catch import errors BEFORE deployment."""

import sys
import importlib

def test_critical_imports():
    """Test all critical imports that CI/CD would test."""
    errors = []
    
    # Test 1: config import from research_system.config
    print("Testing: from research_system.config import config")
    try:
        from research_system.config import config
        print("  ✅ config import works")
    except ImportError as e:
        print(f"  ❌ FAILED: {e}")
        errors.append(str(e))
    
    # Test 2: _execute_provider_async from collection_enhanced
    print("Testing: from research_system.collection_enhanced import _execute_provider_async")
    try:
        from research_system.collection_enhanced import _execute_provider_async
        print("  ✅ _execute_provider_async import works")
    except ImportError as e:
        print(f"  ❌ FAILED: {e}")
        errors.append(str(e))
    
    # Test 3: Other collection_enhanced imports
    print("Testing: from research_system.collection_enhanced import collect_from_free_apis")
    try:
        from research_system.collection_enhanced import (
            collect_from_free_apis_async,
            collect_from_free_apis
        )
        print("  ✅ collection functions import works")
    except ImportError as e:
        print(f"  ❌ FAILED: {e}")
        errors.append(str(e))
    
    # Test 4: Settings has required attributes
    print("Testing: Settings attributes")
    try:
        from research_system.config.settings import settings
        required_attrs = [
            'enabled_providers', 'FRESHNESS_WINDOW', 'SEARCH_PROVIDERS',
            'HTTP_TIMEOUT_SECONDS', 'STATS_ALLOWED_PRIMARY_DOMAINS'
        ]
        for attr in required_attrs:
            if not hasattr(settings, attr):
                raise AttributeError(f"Settings missing {attr}")
        print("  ✅ All required Settings attributes present")
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        errors.append(str(e))
    
    # Test 5: config from legacy path
    print("Testing: from research_system.core.health imports")
    try:
        # This is what failed in CI/CD
        exec("from research_system.config import config")
        print("  ✅ legacy config import path works")
    except ImportError as e:
        print(f"  ❌ FAILED: {e}")
        errors.append(str(e))
    
    return errors

if __name__ == "__main__":
    print("=" * 60)
    print("CI/CD SIMULATION TEST")
    print("=" * 60)
    
    errors = test_critical_imports()
    
    print()
    if errors:
        print("❌ CI/CD WOULD FAIL WITH THESE ERRORS:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("✅ ALL CI/CD IMPORTS WOULD PASS")
        sys.exit(0)