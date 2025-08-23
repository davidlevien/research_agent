"""
Research System - Production-ready research automation
"""

__version__ = "5.0.0"
__author__ = "Research System Team"

# Do NOT import heavy modules at package import time.
# Export only stable, present symbols; keep others discoverable via explicit imports.
from .models import EvidenceCard  # present
from .orchestrator import Orchestrator, OrchestratorSettings  # present
from .config import Settings  # present

__all__ = [
    "EvidenceCard",
    "Orchestrator",
    "OrchestratorSettings",
    "Settings",
]