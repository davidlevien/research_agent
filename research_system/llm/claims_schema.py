"""
LLM Claims Extraction Schema - PE-Grade Evidence Processing

Defines the schema for atomic claims extraction from evidence cards,
ensuring groundedness and traceability.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime

class AtomicClaim(BaseModel):
    """Single atomic claim extracted from evidence"""
    id: str = Field(..., description="Stable ID (hash of normalized text)")
    normalized_text: str = Field(..., description="Canonical wording of the claim")
    support_card_ids: List[str] = Field(..., description="Evidence card IDs supporting this claim")
    support_quotes: List[str] = Field(..., description="Exact quotes from evidence")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")
    claim_type: str = Field(
        default="factual",
        description="Type: factual/statistical/causal/comparative/predictive"
    )
    entities: List[str] = Field(default_factory=list, description="Named entities in claim")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Extracted metrics/numbers")
    temporal_scope: Optional[str] = Field(None, description="Time period if applicable")
    geographic_scope: Optional[str] = Field(None, description="Geographic scope if applicable")
    
    @field_validator('normalized_text')
    def validate_text(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError("Claim text must be at least 10 characters")
        if len(v) > 500:
            raise ValueError("Claim text must be less than 500 characters")
        return v.strip()
    
    @field_validator('support_quotes')
    def validate_quotes(cls, v):
        if not v:
            raise ValueError("At least one supporting quote required")
        return v
    
    @field_validator('confidence')
    def validate_confidence(cls, v):
        return round(v, 3)

class ClaimSet(BaseModel):
    """Collection of atomic claims from evidence"""
    claims: List[AtomicClaim]
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_evidence_cards: int = Field(..., description="Number of cards processed")
    extraction_method: str = Field(default="llm", description="Method used: llm/rules/hybrid")
    model_used: Optional[str] = Field(None, description="LLM model identifier if applicable")
    
    def get_high_confidence_claims(self, threshold: float = 0.7) -> List[AtomicClaim]:
        """Get claims above confidence threshold"""
        return [c for c in self.claims if c.confidence >= threshold]
    
    def get_multi_source_claims(self) -> List[AtomicClaim]:
        """Get claims supported by multiple cards"""
        return [c for c in self.claims if len(c.support_card_ids) > 1]
    
    def get_claims_by_type(self, claim_type: str) -> List[AtomicClaim]:
        """Get claims of specific type"""
        return [c for c in self.claims if c.claim_type == claim_type]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "claims": [c.model_dump() for c in self.claims],
            "extraction_timestamp": self.extraction_timestamp.isoformat(),
            "total_evidence_cards": self.total_evidence_cards,
            "extraction_method": self.extraction_method,
            "model_used": self.model_used
        }

class SynthesisSection(BaseModel):
    """Section of synthesized report"""
    title: str = Field(..., description="Section title")
    bullets: List[Dict[str, Any]] = Field(
        ...,
        description="List of bullet points with text and claim IDs"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall section confidence")
    
    @field_validator('bullets')
    def validate_bullets(cls, v):
        for bullet in v:
            if "text" not in bullet:
                raise ValueError("Each bullet must have 'text' field")
            if "claim_ids" not in bullet or not bullet["claim_ids"]:
                raise ValueError("Each bullet must reference at least one claim_id")
        return v

class SynthesisBundle(BaseModel):
    """Complete synthesis output"""
    executive_summary: SynthesisSection
    key_numbers: Optional[SynthesisSection] = None
    trends: Optional[SynthesisSection] = None
    risks: Optional[SynthesisSection] = None
    outlook: Optional[SynthesisSection] = None
    contradictions: Optional[SynthesisSection] = None
    gaps: Optional[SynthesisSection] = None
    
    generation_timestamp: datetime = Field(default_factory=datetime.utcnow)
    model_used: Optional[str] = Field(None, description="LLM model identifier")
    total_claims_used: int = Field(..., description="Number of claims synthesized")
    
    def get_all_referenced_claims(self) -> List[str]:
        """Get all claim IDs referenced in synthesis"""
        claim_ids = set()
        for section in [self.executive_summary, self.key_numbers, self.trends, 
                       self.risks, self.outlook, self.contradictions, self.gaps]:
            if section:
                for bullet in section.bullets:
                    claim_ids.update(bullet.get("claim_ids", []))
        return list(claim_ids)
    
    def to_markdown(self, claims_lookup: Dict[str, AtomicClaim]) -> str:
        """Convert to markdown with claim citations"""
        lines = []
        
        # Executive Summary
        lines.append("# Executive Summary\n")
        for bullet in self.executive_summary.bullets:
            text = bullet["text"]
            claim_refs = " ".join([f"[{cid[:8]}]" for cid in bullet["claim_ids"]])
            lines.append(f"- {text} {claim_refs}")
        lines.append("")
        
        # Key Numbers
        if self.key_numbers:
            lines.append("## Key Numbers\n")
            for bullet in self.key_numbers.bullets:
                text = bullet["text"]
                claim_refs = " ".join([f"[{cid[:8]}]" for cid in bullet["claim_ids"]])
                lines.append(f"- {text} {claim_refs}")
            lines.append("")
        
        # Trends
        if self.trends:
            lines.append("## Trends\n")
            for bullet in self.trends.bullets:
                text = bullet["text"]
                claim_refs = " ".join([f"[{cid[:8]}]" for cid in bullet["claim_ids"]])
                lines.append(f"- {text} {claim_refs}")
            lines.append("")
        
        # Risks
        if self.risks:
            lines.append("## Risks & Challenges\n")
            for bullet in self.risks.bullets:
                text = bullet["text"]
                claim_refs = " ".join([f"[{cid[:8]}]" for cid in bullet["claim_ids"]])
                lines.append(f"- **{text}** {claim_refs}")
            lines.append("")
        
        # Outlook
        if self.outlook:
            lines.append("## Outlook\n")
            for bullet in self.outlook.bullets:
                text = bullet["text"]
                claim_refs = " ".join([f"[{cid[:8]}]" for cid in bullet["claim_ids"]])
                lines.append(f"- {text} {claim_refs}")
            lines.append("")
        
        # Contradictions
        if self.contradictions:
            lines.append("## Contradictions & Disagreements\n")
            for bullet in self.contradictions.bullets:
                text = bullet["text"]
                claim_refs = " ".join([f"[{cid[:8]}]" for cid in bullet["claim_ids"]])
                lines.append(f"- ⚠️ {text} {claim_refs}")
            lines.append("")
        
        # Gaps
        if self.gaps:
            lines.append("## Information Gaps\n")
            for bullet in self.gaps.bullets:
                text = bullet["text"]
                claim_refs = " ".join([f"[{cid[:8]}]" for cid in bullet["claim_ids"]])
                lines.append(f"- {text} {claim_refs}")
            lines.append("")
        
        # Add claim references appendix
        lines.append("---\n")
        lines.append("## Claim References\n")
        for claim_id in self.get_all_referenced_claims():
            if claim_id in claims_lookup:
                claim = claims_lookup[claim_id]
                lines.append(f"**[{claim_id[:8]}]**: {claim.normalized_text}")
                if claim.support_quotes:
                    lines.append(f"  > \"{claim.support_quotes[0][:200]}...\"")
        
        return "\n".join(lines)

class GroundednessCheck(BaseModel):
    """Validation that claims are grounded in evidence"""
    claim_id: str
    is_grounded: bool
    grounding_score: float = Field(..., ge=0.0, le=1.0)
    evidence_overlap: List[str] = Field(..., description="Overlapping text segments")
    validation_notes: Optional[str] = None
    
class ClaimExtractionRequest(BaseModel):
    """Request structure for LLM claim extraction"""
    evidence_cards: List[Dict[str, Any]]
    max_claims_per_card: int = Field(default=5, ge=1, le=10)
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    require_quotes: bool = Field(default=True)
    merge_similar: bool = Field(default=True)
    similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)

class SynthesisRequest(BaseModel):
    """Request structure for LLM synthesis"""
    claims: List[AtomicClaim]
    topic: str
    max_bullets_per_section: int = Field(default=7, ge=3, le=15)
    include_contradictions: bool = Field(default=True)
    include_gaps: bool = Field(default=True)
    target_length: str = Field(default="medium", pattern="^(short|medium|long)$")
    style: str = Field(default="executive", pattern="^(executive|academic|technical)$")