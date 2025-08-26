#!/usr/bin/env python3
"""
Comprehensive installation verification script for Research System v8.5.2
Ensures all components are properly wired and functional.
"""

import sys
import tempfile
from pathlib import Path
from typing import List, Tuple


def check_module(module_name: str, items: List[str] = None) -> Tuple[bool, str]:
    """Check if a module can be imported and specific items exist."""
    try:
        module = __import__(module_name, fromlist=items or [])
        if items:
            for item in items:
                if not hasattr(module, item):
                    return False, f"Missing {item} in {module_name}"
        return True, f"✓ {module_name}"
    except ImportError as e:
        return False, f"✗ {module_name}: {str(e)}"


def main():
    print("=" * 60)
    print("Research System v8.5.2 - Installation Verification")
    print("=" * 60)
    
    all_passed = True
    
    # 1. Core modules
    print("\n1. Core Modules:")
    core_checks = [
        ("research_system.orchestrator", ["Orchestrator", "OrchestratorSettings"]),
        ("research_system.config", ["Settings"]),
        ("research_system.models", ["EvidenceCard"]),
    ]
    
    for module, items in core_checks:
        passed, msg = check_module(module, items)
        print(f"   {msg}")
        all_passed = all_passed and passed
    
    # 2. Text processing modules (NEW in v8.5.2)
    print("\n2. Text Processing Modules (v8.5.2):")
    text_checks = [
        ("research_system.text", ["jaccard", "text_jaccard", "calculate_claim_similarity"]),
        ("research_system.text.extract", ["extract_text", "clean_html", "extract_metadata"]),
        ("research_system.text.normalize", ["clean_text", "tokenize", "normalize_whitespace"]),
        ("research_system.text.similarity", ["word_overlap_ratio", "token_overlap_count"]),
    ]
    
    for module, items in text_checks:
        passed, msg = check_module(module, items)
        print(f"   {msg}")
        all_passed = all_passed and passed
    
    # 3. Registry system
    print("\n3. Registry System:")
    registry_checks = [
        ("research_system.tools.registry", ["tool_registry", "Registry", "ToolSpec"]),
        ("research_system.tools.search_registry", ["register_search_tools"]),
    ]
    
    for module, items in registry_checks:
        passed, msg = check_module(module, items)
        print(f"   {msg}")
        all_passed = all_passed and passed
    
    # 4. Tool modules
    print("\n4. Tool Modules:")
    tool_checks = [
        ("research_system.tools.content_processor", ["ContentProcessor"]),
        ("research_system.tools.parse_tools", ["ParseTools"]),
        ("research_system.core.quality_assurance", ["QualityAssurance"]),
    ]
    
    for module, items in tool_checks:
        passed, msg = check_module(module, items)
        print(f"   {msg}")
        all_passed = all_passed and passed
    
    # 5. Search providers
    print("\n5. Search Providers:")
    provider_checks = [
        ("research_system.tools.search_tavily", None),
        ("research_system.tools.search_brave", None),
        ("research_system.tools.search_serper", None),
        ("research_system.collection", ["parallel_provider_search"]),
        ("research_system.collection_enhanced", ["collect_from_free_apis"]),
    ]
    
    for module, items in provider_checks:
        passed, msg = check_module(module, items)
        print(f"   {msg}")
        all_passed = all_passed and passed
    
    # 6. Functional tests
    print("\n6. Functional Tests:")
    
    try:
        # Test orchestrator initialization
        from research_system.orchestrator import Orchestrator, OrchestratorSettings
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = OrchestratorSettings(
                topic="test",
                depth="rapid",
                output_dir=Path(tmpdir)
            )
            orch = Orchestrator(settings)
            assert not hasattr(orch, 'registry'), "Orchestrator should use global registry"
            print("   ✓ Orchestrator initialization")
    except Exception as e:
        print(f"   ✗ Orchestrator initialization: {e}")
        all_passed = False
    
    try:
        # Test global registry
        from research_system.tools.registry import tool_registry
        assert 'search_tavily' in tool_registry._tools
        print("   ✓ Global registry contains search tools")
    except Exception as e:
        print(f"   ✗ Global registry: {e}")
        all_passed = False
    
    try:
        # Test text utilities
        from research_system.text import text_jaccard
        sim = text_jaccard("hello world", "world hello")
        assert sim == 1.0, f"Expected 1.0, got {sim}"
        print("   ✓ Text similarity calculations")
    except Exception as e:
        print(f"   ✗ Text similarity: {e}")
        all_passed = False
    
    try:
        # Test HTML extraction
        from research_system.text.extract import extract_text
        html = "<p>Test <b>content</b></p>"
        text = extract_text(html)
        assert text == "Test content", f"Expected 'Test content', got '{text}'"
        print("   ✓ HTML text extraction")
    except Exception as e:
        print(f"   ✗ HTML extraction: {e}")
        all_passed = False
    
    try:
        # Test content processor integration
        from research_system.tools.content_processor import ContentProcessor
        processor = ContentProcessor()
        cleaned = processor.clean_text("Hello <b>world</b> https://example.com")
        assert "https://" not in cleaned
        assert "<b>" not in cleaned
        print("   ✓ Content processor integration")
    except Exception as e:
        print(f"   ✗ Content processor: {e}")
        all_passed = False
    
    # 7. Dependencies check
    print("\n7. Critical Dependencies:")
    deps = [
        ("pydantic", "pydantic"),
        ("httpx", "httpx"),
        ("beautifulsoup4", "bs4"),  # Import name differs from package name
        ("nltk", "nltk"),
        ("bleach", "bleach"),
        ("psutil", "psutil"),
        ("structlog", "structlog"),
        ("numpy", "numpy"),
        ("scikit-learn", "sklearn")  # Import name differs from package name
    ]
    
    for package_name, import_name in deps:
        try:
            __import__(import_name)
            print(f"   ✓ {package_name}")
        except ImportError:
            print(f"   ✗ {package_name} (missing - install with pip)")
            all_passed = False
    
    # Final result
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL CHECKS PASSED - System is ready!")
        print("\nYou can now run:")
        print('  ./run_full_features.sh "your research topic"')
        return 0
    else:
        print("❌ SOME CHECKS FAILED - Please fix issues above")
        print("\nCommon fixes:")
        print("  1. Install missing dependencies: pip install -r requirements.txt")
        print("  2. Check Python version: python3 --version (need 3.11+)")
        return 1


if __name__ == "__main__":
    sys.exit(main())