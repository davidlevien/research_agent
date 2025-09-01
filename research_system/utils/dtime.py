"""Deprecated datetime module - use research_system.utils.datetime_safe instead."""

from warnings import warn
from research_system.utils.datetime_safe import safe_strftime as _impl

def safe_strftime(ts, fmt="%Y%m%d_%H%M%S"):
    """Deprecated: use research_system.utils.datetime_safe.safe_strftime instead."""
    warn(
        "research_system.utils.dtime.safe_strftime is deprecated; "
        "use research_system.utils.datetime_safe.safe_strftime",
        DeprecationWarning,
        stacklevel=2,
    )
    # Call the new implementation with compatible signature
    return _impl(ts, fmt)

# Re-export for backward compatibility
__all__ = ["safe_strftime"]