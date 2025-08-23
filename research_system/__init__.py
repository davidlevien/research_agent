"""
Research System - Production-ready research automation
"""

__version__ = "5.0.0"
__author__ = "Research System Team"

from .models import ResearchRequest, ResearchPlan, EvidenceCard, ResearchReport
from .orchestrator import ResearchOrchestrator
from .config import Config

__all__ = [
    "ResearchRequest",
    "ResearchPlan", 
    "EvidenceCard",
    "ResearchReport",
    "ResearchOrchestrator",
    "Config",
]