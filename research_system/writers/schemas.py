"""Strict schemas for evidence extraction with validation."""

from typing import Optional, Union, List
from pydantic import BaseModel, Field, field_validator
import logging

logger = logging.getLogger(__name__)


class KeyFinding(BaseModel):
    """
    Structured key finding that must be grounded in evidence.
    
    All fields are required for validation to pass.
    """
    metric: str = Field(..., description="The metric being measured (e.g., 'effective tax rate')")
    value: Union[float, int, str] = Field(..., description="The measured value")
    unit: str = Field(..., description="Unit of measurement (%, pp, USD, etc.)")
    geography: str = Field(..., description="Geographic scope (US, OECD, etc.)")
    cohort: str = Field(..., description="Population cohort (e.g., 'top 1% households')")
    year: int = Field(..., description="Year of measurement")
    citation_id: str = Field(..., description="ID of the evidence card or snippet")
    
    @field_validator('metric')
    def metric_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Metric cannot be empty")
        return v.strip()
    
    @field_validator('unit')
    def unit_valid(cls, v):
        valid_units = {
            "%", "pp", "USD", "$", "€", "£", "¥",
            "billion", "million", "trillion",
            "ratio", "index", "per capita", "/year"
        }
        if v not in valid_units and not v.endswith("/year"):
            logger.warning(f"Unusual unit: {v}")
        return v
    
    @field_validator('year')
    def year_reasonable(cls, v):
        if v < 1900 or v > 2050:
            raise ValueError(f"Year {v} out of reasonable range")
        return v


class KeyNumber(BaseModel):
    """
    Structured key number for the Key Numbers section.
    
    More concise than KeyFinding but still requires grounding.
    """
    label: str = Field(..., description="Brief label for the number")
    value: Union[float, int, str] = Field(..., description="The numeric value")
    unit: str = Field(..., description="Unit of measurement")
    year: int = Field(..., description="Year of measurement")
    citation_id: str = Field(..., description="ID of the evidence card")
    
    @field_validator('label')
    def label_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Label cannot be empty")
        return v.strip()


class CitationReference:
    """Helper to look up citation texts."""
    
    def __init__(self, cards: List):
        self.lookup = {}
        for card in cards:
            card_id = getattr(card, 'id', None)
            if card_id:
                # Store the actual text content
                text = (
                    getattr(card, 'claim', '') or
                    getattr(card, 'snippet', '') or
                    getattr(card, 'quote_span', '') or
                    getattr(card, 'title', '')
                )
                self.lookup[card_id] = text
    
    def get_snippet_by_id(self, citation_id: str) -> str:
        """Get the text snippet for a citation ID."""
        return self.lookup.get(citation_id, "")


def build_key_findings(evidence_cards: List, intent: str) -> List[dict]:
    """
    Build key findings from evidence cards with strict validation.
    
    Only returns findings that:
    1. Can be extracted from the evidence
    2. Pass schema validation
    3. Are entailed by the cited snippet
    
    Args:
        evidence_cards: List of evidence cards
        intent: Research intent
        
    Returns:
        List of validated key finding dicts
    """
    from research_system.writers.extractors import extract_structured_fact
    from research_system.validation.entailment import entails
    
    findings = []
    citation_ref = CitationReference(evidence_cards)
    
    for card in evidence_cards:
        # Try to extract structured fact
        fact_data = extract_structured_fact(card)
        if not fact_data:
            continue
        
        # Add citation ID
        fact_data['citation_id'] = getattr(card, 'id', 'unknown')
        
        try:
            # Validate against schema
            kf = KeyFinding(**fact_data)
        except Exception as e:
            logger.debug(f"Fact failed schema validation: {e}")
            continue
        
        # Check entailment
        snippet = citation_ref.get_snippet_by_id(kf.citation_id)
        if not snippet:
            logger.debug(f"No snippet found for citation {kf.citation_id}")
            continue
        
        # Build claim string for entailment check
        claim = (
            f"{kf.metric} is {kf.value}{kf.unit} "
            f"in {kf.year} for {kf.cohort} in {kf.geography}"
        )
        
        if not entails(snippet, claim):
            logger.debug(f"Claim not entailed: '{claim}' not in '{snippet[:100]}...'")
            continue
        
        # All checks passed
        findings.append(kf.model_dump())
    
    logger.info(f"Extracted {len(findings)} valid key findings from {len(evidence_cards)} cards")
    return findings


def build_key_numbers(evidence_cards: List, intent: str) -> List[dict]:
    """
    Build key numbers from evidence cards with strict validation.
    
    Args:
        evidence_cards: List of evidence cards
        intent: Research intent
        
    Returns:
        List of validated key number dicts
    """
    from research_system.writers.extractors import extract_number
    from research_system.validation.entailment import entails
    
    numbers = []
    citation_ref = CitationReference(evidence_cards)
    
    for card in evidence_cards:
        # Try to extract number
        num_data = extract_number(card)
        if not num_data:
            continue
        
        # Add citation ID
        num_data['citation_id'] = getattr(card, 'id', 'unknown')
        
        try:
            # Validate against schema
            kn = KeyNumber(**num_data)
        except Exception as e:
            logger.debug(f"Number failed schema validation: {e}")
            continue
        
        # Check entailment
        snippet = citation_ref.get_snippet_by_id(kn.citation_id)
        if not snippet:
            continue
        
        # Build claim string
        claim = f"{kn.label}: {kn.value}{kn.unit} ({kn.year})"
        
        if not entails(snippet, claim):
            logger.debug(f"Number not entailed: '{claim}'")
            continue
        
        numbers.append(kn.model_dump())
    
    logger.info(f"Extracted {len(numbers)} valid key numbers from {len(evidence_cards)} cards")
    return numbers