"""Deprecated seeding module - use research_system.utils.deterministic instead."""

from warnings import warn
from research_system.utils.deterministic import set_global_seeds as _impl

def set_global_seeds(seed_like="20230817"):
    """Deprecated: use research_system.utils.deterministic.set_global_seeds instead."""
    warn(
        "research_system.utils.seeding.set_global_seeds is deprecated; "
        "use research_system.utils.deterministic.set_global_seeds",
        DeprecationWarning,
        stacklevel=2,
    )
    # Convert old string-based seed to int for compatibility
    if isinstance(seed_like, str):
        try:
            seed = abs(hash(seed_like)) % (2**31)
        except Exception:
            seed = 1337
    else:
        seed = seed_like
    return _impl(seed)

# Re-export for backward compatibility
__all__ = ["set_global_seeds"]