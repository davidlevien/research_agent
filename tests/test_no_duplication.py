"""
Test to prevent duplication/conflicts from creeping back into the codebase.
This is a guard test that ensures we maintain single source of truth.
"""

from pathlib import Path
import re
import pytest

ROOT = Path(__file__).resolve().parents[1]

def test_no_duplicate_classes_or_functions():
    """Test that critical names are unique across the codebase."""
    
    # Names that must be unique across the tree (except in deprecation shims)
    UNIQUE = [
        (r"class\s+Settings\b", "Settings class"),
        (r"def\s+set_global_seeds\b", "set_global_seeds function"),
        (r"def\s+safe_strftime\b", "safe_strftime function"),
        (r"class\s+CacheManager\b", "CacheManager class"),
        (r"class\s+AlertManager\b", "AlertManager class"),
        (r"def\s+choose_providers\b", "choose_providers function"),
        (r"def\s+_write_jsonl\b", "_write_jsonl function"),
    ]
    
    seen = {pattern: [] for pattern, _ in UNIQUE}
    
    # Scan all Python files
    for p in ROOT.rglob("*.py"):
        # Skip test files and virtual environments
        if any(part in str(p) for part in ["/test", "/venv/", "/.venv/", "/__pycache__/"]):
            continue
            
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            
            for pattern, name in UNIQUE:
                if re.search(pattern, content):
                    # Check if this is a deprecation shim (contains "deprecated" or "DeprecationWarning")
                    is_shim = "deprecated" in content.lower() or "DeprecationWarning" in content
                    seen[pattern].append((p, is_shim))
        except Exception:
            continue
    
    errors = []
    for (pattern, name) in UNIQUE:
        files = seen[pattern]
        
        # Filter out shims from the main count
        non_shim_files = [f for f, is_shim in files if not is_shim]
        shim_files = [f for f, is_shim in files if is_shim]
        
        # Allow exactly one defining file + any number of shims
        if len(non_shim_files) > 1:
            file_list = "\n  - ".join(str(f.relative_to(ROOT)) for f in non_shim_files)
            errors.append(f"{name} defined in multiple non-shim files:\n  - {file_list}")
    
    if errors:
        pytest.fail("Duplication detected:\n" + "\n\n".join(errors))


def test_no_legacy_imports():
    """Test that we're not using deprecated import paths."""
    
    BANNED_IMPORTS = [
        (r"from\s+research_system\.utils\.seeding\s+import", 
         "Use research_system.utils.deterministic instead of utils.seeding"),
        (r"from\s+research_system\.utils\.dtime\s+import", 
         "Use research_system.utils.datetime_safe instead of utils.dtime"),
        (r"from\s+research_system\.core\.performance\s+import\s+CacheManager", 
         "Use research_system.data.cache.CacheManager instead"),
        (r"from\s+research_system\.monitoring\.metrics\s+import\s+AlertManager", 
         "Use research_system.monitoring.alerting.AlertManager instead"),
        (r"from\s+research_system\.routing\.topic_router\s+import\s+choose_providers", 
         "Use research_system.routing.provider_router.choose_providers instead"),
    ]
    
    violations = []
    
    for p in ROOT.rglob("*.py"):
        # Skip test files, virtual environments, and the shim files themselves
        if any(part in str(p) for part in ["/test", "/venv/", "/.venv/", "/__pycache__/",
                                            "seeding.py", "dtime.py", "topic_router.py"]):
            continue
        
        # Skip the performance.py file itself (it's the shim)
        if p.name == "performance.py" and "core" in str(p):
            continue
            
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            
            for pattern, message in BANNED_IMPORTS:
                if re.search(pattern, content):
                    violations.append(f"{p.relative_to(ROOT)}: {message}")
        except Exception:
            continue
    
    if violations:
        pytest.fail("Legacy imports detected:\n" + "\n".join(violations))


def test_single_config_source():
    """Test that all config imports use the canonical path."""
    
    correct_pattern = r"from research_system\.config\.settings import"
    wrong_patterns = [
        r"from research_system\.config import Settings(?!\w)",  # Not from .settings
        r"from \.config import Settings",  # Relative import
    ]
    
    violations = []
    
    for p in ROOT.rglob("*.py"):
        # Skip test files, virtual environments, and the config.py shim itself
        if any(part in str(p) for part in ["/test", "/venv/", "/.venv/", "/__pycache__/"]):
            continue
        if p.name == "config.py" and p.parent.name == "research_system":
            continue
            
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            
            # Check if it imports Settings at all
            if "import Settings" in content or "Settings" in content:
                # Check if using wrong pattern
                for pattern in wrong_patterns:
                    if re.search(pattern, content):
                        violations.append(f"{p.relative_to(ROOT)}: Should use 'from research_system.config.settings import Settings'")
                        break
        except Exception:
            continue
    
    if violations:
        pytest.fail("Non-canonical config imports:\n" + "\n".join(violations))


def test_tool_registry_singleton():
    """Test that tool registry uses singleton pattern consistently."""
    
    violations = []
    
    for p in ROOT.rglob("*.py"):
        # Skip test files and virtual environments
        if any(part in str(p) for part in ["/test", "/venv/", "/.venv/", "/__pycache__/"]):
            continue
            
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            
            # Check for direct Registry() instantiation (should use get_registry())
            if re.search(r"Registry\(\)\s*(?!.*#.*test)", content):
                # Make sure it's not in registry.py itself or in a comment
                if p.name != "registry.py" and "get_registry" not in content:
                    violations.append(f"{p.relative_to(ROOT)}: Creating Registry() directly - use get_registry() instead")
            
            # Check for old duplicate check pattern
            if re.search(r'if\s+"[^"]+"\s+not\s+in\s+.*\._tools', content):
                violations.append(f"{p.relative_to(ROOT)}: Manual duplicate check - registry handles this automatically")
                
        except Exception:
            continue
    
    if violations:
        pytest.fail("Tool registry issues:\n" + "\n".join(violations))


if __name__ == "__main__":
    # Run tests directly
    import sys
    
    print("Running duplication guard tests...")
    
    try:
        test_no_duplicate_classes_or_functions()
        print("✅ No duplicate classes/functions")
    except AssertionError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    try:
        test_no_legacy_imports()
        print("✅ No legacy imports")
    except AssertionError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    try:
        test_single_config_source()
        print("✅ Single config source")
    except AssertionError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    try:
        test_tool_registry_singleton()
        print("✅ Tool registry singleton pattern")
    except AssertionError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    print("\n🎯 All guard tests passed!")