"""
LLM Module - Optional AI-Powered Enhancement Layer

Provides claims extraction and synthesis capabilities when LLM is available.
Falls back to rules-based approaches when LLM is not configured.
"""

from research_system.llm.claims_schema import (
    AtomicClaim,
    ClaimSet,
    SynthesisSection,
    SynthesisBundle,
    ClaimExtractionRequest,
    SynthesisRequest,
    GroundednessCheck
)

from research_system.llm.claims_extractor import (
    ClaimsExtractor,
    merge_similar_claims
)

from research_system.llm.synthesizer import Synthesizer

from research_system.llm.llm_client import LLMClient

__all__ = [
    # Schema
    'AtomicClaim',
    'ClaimSet',
    'SynthesisSection',
    'SynthesisBundle',
    'ClaimExtractionRequest',
    'SynthesisRequest',
    'GroundednessCheck',
    
    # Extractors
    'ClaimsExtractor',
    'merge_similar_claims',
    
    # Synthesizer
    'Synthesizer',
    
    # Client
    'LLMClient'
]