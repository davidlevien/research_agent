"""
Research System - Production-ready research automation
"""

__version__ = "5.0.0"
__author__ = "Research System Team"

__all__ = [
    "EvidenceCard",
    "Orchestrator",
    "OrchestratorSettings",
    "Settings",
    "__version__",
    "__author__",
]

def __getattr__(name: str):
    """Lazy import to avoid import-time side effects."""
    if name == "EvidenceCard":
        from .models import EvidenceCard
        return EvidenceCard
    elif name == "Orchestrator":
        from .orchestrator import Orchestrator
        return Orchestrator
    elif name == "OrchestratorSettings":
        from .orchestrator import OrchestratorSettings
        return OrchestratorSettings
    elif name == "Settings":
        from research_system.config.settings import Settings
        return Settings
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")