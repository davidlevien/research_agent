"""Cache management for run isolation.

This module provides a centralized registry for all caches used in the system,
allowing clean-room resets between runs to prevent cross-run contamination.
"""

_REGISTRY = []

def register(cache_like):
    """Register a cache-like object for reset management."""
    _REGISTRY.append(cache_like)

def reset_all():
    """Reset all registered caches. Safe to call even if module is missing."""
    for c in list(_REGISTRY):
        try:
            if hasattr(c, 'clear'):
                c.clear()
            elif hasattr(c, 'reset'):
                c.reset()
        except Exception:
            pass  # Ignore failures, this is best-effort cleanup