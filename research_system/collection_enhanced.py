"""Legacy collection_enhanced.py - maintained for backward compatibility.

This module is deprecated. Use research_system.collection instead.
"""

from warnings import warn

# Emit deprecation warning on import
warn(
    "collection_enhanced.py is deprecated. Use research_system.collection instead.",
    DeprecationWarning,
    stacklevel=2
)

# Forward all imports to the new location
from research_system.collection.enhanced import *  # noqa