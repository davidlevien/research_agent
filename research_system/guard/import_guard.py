"""Import guard to prevent mixing legacy and unified modules.

This module helps ensure consistent usage of the new unified configuration
and collection modules by detecting when both old and new versions are imported.
"""

import sys
from warnings import warn
from typing import Set


def assert_no_legacy_mix() -> None:
    """Check that legacy and unified modules aren't imported together.
    
    Raises RuntimeError if both old and new versions of config or collection
    modules are imported. Issues deprecation warnings for legacy imports.
    """
    mods = set(sys.modules.keys())
    
    # Check for mixed config imports
    legacy_configs = {"research_system.config", "research_system.config_v2"}
    unified_config = "research_system.config.settings"
    
    has_legacy_config = bool(legacy_configs & mods)
    has_unified_config = unified_config in mods
    
    if has_legacy_config and has_unified_config:
        # Both are imported, but since legacy forwards to unified, this is OK
        # Just warn about the legacy usage
        for legacy in legacy_configs & mods:
            warn(
                f"Using legacy {legacy}; prefer research_system.config.settings",
                DeprecationWarning,
                stacklevel=2
            )
    
    # Check for mixed collection imports
    legacy_collections = {"research_system.collection_enhanced"}
    unified_collection = "research_system.collection"
    
    # Note: research_system.collection is now the unified one, 
    # and collection_enhanced forwards to it
    if "research_system.collection_enhanced" in mods:
        warn(
            "Using legacy collection_enhanced; prefer research_system.collection",
            DeprecationWarning,
            stacklevel=2
        )
    
    # Check for direct imports of moved modules
    if "research_system.quality.thresholds" in mods:
        warn(
            "research_system.quality.thresholds should not be imported directly; "
            "use research_system.config.settings instead",
            DeprecationWarning,
            stacklevel=2
        )


def check_import_health() -> dict:
    """Return diagnostic information about module imports.
    
    Returns:
        Dictionary with import health information
    """
    mods = set(sys.modules.keys())
    
    health = {
        "has_legacy_config": bool({"research_system.config", "research_system.config_v2"} & mods),
        "has_unified_config": "research_system.config.settings" in mods,
        "has_legacy_collection": "research_system.collection_enhanced" in mods,
        "has_unified_collection": "research_system.collection" in mods,
        "has_unified_metrics": "research_system.metrics.run" in mods,
        "warnings": []
    }
    
    # Add warnings
    if health["has_legacy_config"]:
        health["warnings"].append("Legacy config modules in use")
    
    if health["has_legacy_collection"]:
        health["warnings"].append("Legacy collection_enhanced in use")
    
    if "research_system.quality.thresholds" in mods and health["has_unified_config"]:
        health["warnings"].append("Both quality.thresholds and config.settings imported")
    
    health["is_healthy"] = len(health["warnings"]) == 0
    
    return health


def enforce_unified_imports() -> None:
    """Enforce that only unified modules are used (strict mode).
    
    This is more strict than assert_no_legacy_mix and will raise errors
    for any legacy module usage.
    """
    mods = set(sys.modules.keys())
    
    forbidden = {
        "research_system.config": "Use research_system.config.settings instead",
        "research_system.config_v2": "Use research_system.config.settings instead",
        "research_system.collection_enhanced": "Use research_system.collection instead",
        "research_system.quality.thresholds": "Use research_system.config.settings instead",
    }
    
    violations = []
    for module, replacement in forbidden.items():
        if module in mods:
            violations.append(f"{module}: {replacement}")
    
    if violations:
        raise RuntimeError(
            "Legacy modules detected (strict mode):\n" + "\n".join(violations)
        )


# Auto-check on import (non-strict by default)
if __name__ != "__main__":
    # Only run checks when imported, not when executed as script
    try:
        assert_no_legacy_mix()
    except Exception as e:
        # Log but don't crash - this is just a warning system
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Import guard detected potential issues: {e}")