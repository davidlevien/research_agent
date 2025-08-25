from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum
import uuid


class Discipline(str, Enum):
    """Domain disciplines for routing and policy selection"""
    GENERAL = "general"
    SCIENCE = "science"
    MEDICINE = "medicine"
    LAW_POLICY = "law_policy"
    FINANCE_ECON = "finance_econ"
    TECH_SOFTWARE = "tech_software"
    SECURITY = "security"
    TRAVEL_TOURISM = "travel_tourism"
    CLIMATE_ENV = "climate_env"


class EvidenceCard(BaseModel):
    # Core identity
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Legacy fields (for backward compatibility - now optional)
    subtopic_name: str = "Research Findings"
    claim: str = ""
    supporting_text: str = ""
    source_url: Optional[str] = None  # Now optional - use 'url' instead
    source_title: Optional[str] = None  # Now optional - use 'title' instead
    source_domain: Optional[str] = None  # Now optional - derived from 'url'
    credibility_score: float = Field(ge=0, le=1)
    is_primary_source: bool = False
    relevance_score: float = Field(ge=0, le=1)
    confidence: float = Field(default=0.5, ge=0, le=1)
    collected_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    search_provider: Optional[str] = None
    publication_date: Optional[str] = None
    author: Optional[str] = None
    
    # NEW required fields for blueprint compliance
    url: str  # Canonical URL (required)
    title: str  # Article title (required)
    snippet: str  # Non-empty extract (required)
    provider: str  # Required provider stamp (tavily, brave, serper, serpapi, nps, openalex, crossref, etc.)
    date: Optional[str] = None  # Publication date if available
    
    # Controversy tracking fields
    stance: Literal["supports", "disputes", "neutral"] = "neutral"
    claim_id: Optional[str] = None
    disputed_by: List[str] = Field(default_factory=list)
    controversy_score: float = Field(default=0.0, ge=0, le=1)
    
    # Enhanced evidence anchoring & QA
    quote_span: Optional[str] = None  # Exact quote from source
    content_hash: Optional[str] = None  # For duplicate detection
    reachability: float = Field(default=1.0, ge=0, le=1)  # 0=paywalled, 1=accessible
    
    # Topic tagging for conglomeration
    topic: str = "seed"  # seed topic or related topic label
    related_reason: Optional[str] = None  # Why this related topic was included
    
    # Discipline classification and persistent identifiers
    discipline: Discipline = Discipline.GENERAL
    doi: Optional[str] = None  # Digital Object Identifier
    pmid: Optional[str] = None  # PubMed ID
    arxiv_id: Optional[str] = None  # ArXiv identifier
    law_citation: Optional[str] = None  # Legal citation (e.g., 15 U.S.C. §1)
    cve_id: Optional[str] = None  # CVE identifier for security vulnerabilities
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata storage
    
    @model_validator(mode="after")
    def backfill_required_fields(self):
        """Ensure bidirectional field compatibility"""
        # Backfill from legacy to new (if new are missing)
        if not self.url and self.source_url:
            self.url = self.source_url
        if not self.title and self.source_title:
            self.title = self.source_title
        if not self.date and self.publication_date:
            self.date = self.publication_date
        if not self.snippet and self.supporting_text:
            self.snippet = self.supporting_text[:500]
            
        # Backfill from new to legacy (if legacy are missing)
        if not self.source_url and self.url:
            self.source_url = self.url
        if not self.source_title and self.title:
            self.source_title = self.title
        # Belt-and-suspenders: ensure supporting_text is never empty
        if not self.supporting_text:
            self.supporting_text = (self.snippet or self.title or "")[:5000]
        if not self.source_domain and self.url:
            from urllib.parse import urlparse
            self.source_domain = urlparse(self.url).netloc
        if not self.provider and self.search_provider:
            self.provider = self.search_provider
        if not self.claim and self.title:
            self.claim = self.title[:200]  # Use title as claim if missing
        if not self.source_url and self.url:
            self.source_url = self.url
        return self
    
    @classmethod
    def from_seed(cls, d: dict, provider: str):
        """Create EvidenceCard from seed dictionary with domain normalization."""
        from research_system.tools.domain_norm import canonical_domain
        
        # Normalize domain
        domain = d.get("source_domain", "")
        if not domain and d.get("url"):
            from urllib.parse import urlparse
            domain = urlparse(d.get("url", "")).netloc
        domain = canonical_domain(domain)
        
        return cls(
            id=d.get("id") or str(uuid.uuid4()),
            url=d.get("url", ""),
            title=d.get("title", ""),
            snippet=d.get("snippet", ""),
            source_domain=domain,
            claim=d.get("claim", d.get("title", "")),
            supporting_text=d.get("supporting_text", d.get("snippet", "")),
            provider=provider,
            date=d.get("published_at") or d.get("date"),
            metadata=d.get("metadata", {}),
            credibility_score=d.get("credibility_score", 0.7),
            relevance_score=d.get("relevance_score", 0.7),
            confidence=d.get("confidence", 0.5),
            retrieved_at=d.get("retrieved_at"),
            is_primary_source=d.get("is_primary_source", False)
        )
    
    def to_jsonl_dict(self) -> dict:
        """Return canonical fields for JSONL output with licensing info"""
        d = self.model_dump()
        
        # Add licensing information based on provider
        meta = d.get("metadata") or {}
        
        # Set default licenses for known providers
        if self.provider == "wikipedia":
            meta.setdefault("license", "CC BY-SA 3.0")
        elif self.provider in {"wikidata", "openalex"}:
            meta.setdefault("license", "CC0")
        elif self.provider == "worldbank":
            meta.setdefault("license", "CC BY-4.0")
        elif self.provider == "arxiv":
            meta.setdefault("license", "arXiv License")
        elif self.provider in {"pubmed", "europepmc"}:
            meta.setdefault("license", "Public Domain/Open Access where applicable")
        elif self.provider == "overpass":
            meta.setdefault("license", "ODbL 1.0")
        
        if meta:
            d["metadata"] = meta
        
        # Output all required fields plus extras (including PE-grade fields for clustering)
        keys = ["id", "title", "url", "snippet", "provider", "date",
                "credibility_score", "relevance_score", "confidence",
                "collected_at", "source_domain", "stance", "claim_id",
                "disputed_by", "controversy_score", "subtopic_name",
                "claim", "supporting_text", "is_primary_source",
                "quote_span", "content_hash", "author", "source_title", 
                "source_url", "search_provider", "publication_date", "metadata"]
        return {k: d.get(k) for k in keys if k in d}

class ReportSection(BaseModel):
    title: str
    content: str
    evidence_ids: List[str]
    confidence: float = Field(ge=0, le=1)
    word_count: int

class ResearchMetrics(BaseModel):
    total_sources_examined: int
    total_evidence_collected: int
    unique_domains: int
    avg_credibility_score: float
    execution_time_seconds: float
    total_cost_usd: float
    llm_calls: int
    search_api_calls: int

class ResearchReport(BaseModel):
    report_id: str
    topic: str
    executive_summary: str
    sections: List[ReportSection]
    evidence: List[EvidenceCard]
    metrics: ResearchMetrics
    created_at: datetime
    status: str
    
    def to_markdown(self) -> str:
        """Convert report to markdown format"""
        md = f"# Research Report: {self.topic}\n\n"
        md += f"**Report ID:** {self.report_id}\n"
        md += f"**Created:** {self.created_at}\n"
        md += f"**Status:** {self.status}\n\n"
        
        md += "## Executive Summary\n\n"
        md += f"{self.executive_summary}\n\n"
        
        for section in self.sections:
            md += f"## {section.title}\n\n"
            md += f"{section.content}\n\n"
            md += f"*Confidence: {section.confidence:.0%} | Sources: {len(section.evidence_ids)}*\n\n"
        
        md += "## Metrics\n\n"
        md += f"- Sources Examined: {self.metrics.total_sources_examined}\n"
        md += f"- Evidence Collected: {self.metrics.total_evidence_collected}\n"
        md += f"- Unique Domains: {self.metrics.unique_domains}\n"
        md += f"- Average Credibility: {self.metrics.avg_credibility_score:.0%}\n"
        md += f"- Execution Time: {self.metrics.execution_time_seconds:.1f}s\n"
        md += f"- Total Cost: ${self.metrics.total_cost_usd:.2f}\n"
        
        return md


class BiasIndicators(BaseModel):
    """Indicators of potential bias in content"""
    political_lean: Optional[float] = Field(None, ge=-1, le=1)  # -1 left, 0 neutral, 1 right
    commercial_bias: Optional[float] = Field(None, ge=0, le=1)
    emotional_tone: Optional[float] = Field(None, ge=-1, le=1)  # -1 negative, 0 neutral, 1 positive
    promotional_content: bool = False
    disclaimer_present: bool = False


class QualityIndicators(BaseModel):
    """Quality indicators for content assessment"""
    source_reputation: Optional[float] = Field(None, ge=0, le=1)
    citation_density: Optional[float] = Field(None, ge=0, le=1)
    fact_checkable: bool = True
    peer_reviewed: bool = False
    methodology_transparent: bool = False


class RelatedTopic(BaseModel):
    """Represents a related topic discovered during research"""
    name: str
    score: float = Field(ge=0)
    reason_to_include: str


# Legacy models for backward compatibility with tests
class ResearchDepth(str, Enum):
    """Research depth levels"""
    RAPID = "rapid"
    STANDARD = "standard"
    DEEP = "deep"

class ResearchRequest(BaseModel):
    """Legacy research request for tests"""
    topic: str
    depth: ResearchDepth = ResearchDepth.STANDARD
    max_sources: int = 20
    
class ResearchPlan(BaseModel):
    """Research plan structure"""
    topic: str
    objectives: List[str]
    methodology: str
    expected_sources: List[str]
    
class Subtopic(BaseModel):
    """Subtopic for research"""
    name: str
    relevance: float
    
class ResearchMethodology(BaseModel):
    """Research methodology details"""
    approach: str
    data_sources: List[str]
    quality_criteria: Dict[str, Any]

class ResearchSection(BaseModel):
    """Section in research report"""
    title: str
    content: str
    evidence_ids: List[str] = Field(default_factory=list)

class EnhancedResearchRequest(BaseModel):
    """Enhanced research request with expanded capabilities"""
    topic: str
    purpose: Literal["brief", "dossier", "market-scan"] = "brief"
    audience: Literal["exec", "pm", "analyst"] = "exec"
    depth_level: int = Field(ge=1, le=3, default=1)
    freshness_days: int = Field(ge=1, le=365, default=90)
    explore_radius: int = Field(ge=0, le=2, default=1)  # 0=seed only, 1=near, 2=broad
    region: Optional[str] = None
    providers: Optional[List[str]] = None  # Override provider policy if set