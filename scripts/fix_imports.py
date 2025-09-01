#!/usr/bin/env python3
"""
Import normalization script to fix all import paths to use canonical modules.
This ensures single source of truth across the codebase.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Import path replacements (pattern -> replacement)
TARGETS = [
    # Config imports
    (r'from\s+\.config\s+import\s+Settings', 'from research_system.config.settings import Settings'),
    (r'from\s+research_system\.config\s+import\s+Settings', 'from research_system.config.settings import Settings'),
    
    # Seeding imports
    (r'from\s+research_system\.utils\.seeding\s+import\s+set_global_seeds', 
     'from research_system.utils.deterministic import set_global_seeds'),
    
    # DateTime imports
    (r'from\s+research_system\.utils\.dtime\s+import\s+safe_strftime', 
     'from research_system.utils.datetime_safe import safe_strftime'),
    
    # Tool registry imports
    (r'from\s+research_system\.tools\.registry\s+import\s+tool_registry', 
     'from research_system.tools.registry import get_registry'),
    (r'from\s+\.registry\s+import\s+tool_registry',
     'from .registry import get_registry'),
    
    # CacheManager imports
    (r'from\s+research_system\.core\.performance\s+import\s+CacheManager', 
     'from research_system.data.cache import CacheManager'),
    
    # AlertManager imports (should use alerting.py, not metrics.py)
    (r'from\s+research_system\.monitoring\.metrics\s+import\s+AlertManager', 
     'from research_system.monitoring.alerting import AlertManager'),
    
    # Provider router imports
    (r'from\s+research_system\.routing\.topic_router\s+import\s+choose_providers', 
     'from research_system.routing.provider_router import choose_providers'),
]

# Additional replacements for tool_registry usage
CODE_REPLACEMENTS = [
    # Replace tool_registry usage with get_registry()
    (r'\btool_registry\b(?!\.)', 'get_registry()'),
    
    # Fix duplicate checks in tool registration
    (r'if\s+"[^"]+"\s+not\s+in\s+tool_registry\._tools:', '# Duplicate check removed - handled by registry'),
    (r'if\s+"[^"]+"\s+not\s+in\s+get_registry\(\)\._tools:', '# Duplicate check removed - handled by registry'),
]

def rewrite(file: pathlib.Path, dry_run: bool = False):
    """Rewrite a Python file with normalized imports."""
    try:
        s = file.read_text(encoding="utf-8")
        orig = s
        
        # Apply import replacements
        for pat, rep in TARGETS:
            s = re.sub(pat, rep, s)
        
        # Apply code replacements (but be careful with tool_registry)
        for pat, rep in CODE_REPLACEMENTS:
            # Only apply if the file imports from registry
            if 'from' in s and 'registry' in s:
                s = re.sub(pat, rep, s)
        
        if s != orig:
            if dry_run:
                print(f"Would update: {file.relative_to(ROOT)}")
            else:
                file.write_text(s, encoding="utf-8")
                print(f"Updated: {file.relative_to(ROOT)}")
            return True
    except Exception as e:
        print(f"Error processing {file}: {e}", file=sys.stderr)
    return False

def main():
    """Main function to process all Python files."""
    print("Normalizing imports in research_system/...")
    
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("DRY RUN MODE - no files will be changed")
    
    updated_count = 0
    for py in ROOT.rglob("*.py"):
        # Skip virtual environments and build directories
        if any(part in str(py) for part in ["/venv/", "/.venv/", "/build/", "/__pycache__/"]):
            continue
        
        # Skip this script itself
        if py == pathlib.Path(__file__):
            continue
            
        if rewrite(py, dry_run):
            updated_count += 1
    
    print(f"\n{'Would update' if dry_run else 'Updated'} {updated_count} files")
    
    if not dry_run:
        print("\nImports normalized successfully!")
        print("Next steps:")
        print("1. Run tests: pytest -q")
        print("2. Check for any remaining issues: grep -r 'from.*config import Settings' research_system/")

if __name__ == "__main__":
    main()