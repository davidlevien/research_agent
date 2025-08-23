"""
Data models for the research system
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal
from enum import Enum
import uuid
from pydantic import BaseModel, Field, validator, HttpUrl


class ResearchDepth(str, Enum):
    """Research depth levels"""
    RAPID = "rapid"
    STANDARD = "standard"
    DEEP = "deep"


class SourceType(str, Enum):
    """Types of information sources"""
    ACADEMIC = "academic"
    GOVERNMENT = "government"
    NEWS = "news"
    TRADE = "trade"
    BLOG = "blog"
    SOCIAL = "social"


class Priority(str, Enum):
    """Priority levels"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Sentiment(str, Enum):
    """Sentiment categories"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


@dataclass
class ResearchConstraints:
    """Research constraints and limitations"""
    time_window: Optional[str] = None
    geographic_scope: List[str] = field(default_factory=list)
    language: List[str] = field(default_factory=lambda: ["en"])
    source_types: List[SourceType] = field(default_factory=list)
    max_cost_usd: float = 1.0
    max_time_seconds: int = 300
    max_api_calls: int = 100


@dataclass
class ResearchMethodology:
    """Research methodology configuration"""
    search_strategy: str
    quality_criteria: List[str]
    inclusion_criteria: List[str] = field(default_factory=list)
    exclusion_criteria: List[str] = field(default_factory=list)


@dataclass
class Subtopic:
    """Research subtopic"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    rationale: str = ""
    search_queries: List[str] = field(default_factory=list)
    freshness_days: int = 30
    priority: Priority = Priority.MEDIUM
    evidence_target: int = 10


class ResearchRequest(BaseModel):
    """User research request"""
    topic: str = Field(..., min_length=3, max_length=500)
    depth: ResearchDepth = ResearchDepth.STANDARD
    constraints: Optional[ResearchConstraints] = None
    custom_instructions: Optional[str] = None
    output_format: Literal["markdown", "json", "html", "pdf"] = "markdown"
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ResearchPlan(BaseModel):
    """Research execution plan"""
    topic: str
    depth: ResearchDepth
    subtopics: List[Subtopic]
    methodology: ResearchMethodology
    constraints: ResearchConstraints
    budget: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    @validator('subtopics')
    def validate_subtopics(cls, v):
        if not v:
            raise ValueError("At least one subtopic is required")
        if len(v) > 10:
            raise ValueError("Maximum 10 subtopics allowed")
        return v


@dataclass
class QualityIndicators:
    """Evidence quality indicators"""
    has_citations: bool = False
    has_methodology: bool = False
    has_data: bool = False
    peer_reviewed: bool = False
    fact_checked: bool = False


@dataclass
class BiasIndicators:
    """Bias detection indicators"""
    sentiment: Sentiment = Sentiment.NEUTRAL
    subjectivity: float = 0.5
    political_lean: Optional[str] = None
    commercial_intent: bool = False


@dataclass
class EntityExtraction:
    """Extracted entities from evidence"""
    people: List[str] = field(default_factory=list)
    organizations: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    dates: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)


class EvidenceCard(BaseModel):
    """Evidence card with comprehensive metadata"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subtopic_name: str
    claim: str = Field(..., min_length=10, max_length=2000)
    supporting_text: str = Field(..., min_length=10, max_length=5000)
    source_url: HttpUrl
    source_title: str = Field(..., min_length=1, max_length=500)
    source_domain: str
    publication_date: Optional[datetime] = None
    author: Optional[str] = Field(None, max_length=200)
    credibility_score: float = Field(..., ge=0, le=1)
    is_primary_source: bool = False
    relevance_score: float = Field(..., ge=0, le=1)
    confidence: float = Field(0.5, ge=0, le=1)
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    search_provider: Optional[str] = None
    entities: Optional[EntityExtraction] = None
    quality_indicators: Optional[QualityIndicators] = None
    bias_indicators: Optional[BiasIndicators] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


@dataclass
class ResearchSection:
    """Section of research report"""
    title: str
    content: str
    evidence_ids: List[str]
    confidence: float
    word_count: int


@dataclass
class ResearchMetrics:
    """Research execution metrics"""
    total_sources_examined: int = 0
    total_evidence_collected: int = 0
    unique_domains: int = 0
    avg_credibility_score: float = 0.0
    avg_relevance_score: float = 0.0
    execution_time_seconds: float = 0.0
    total_cost_usd: float = 0.0
    api_calls_made: int = 0
    cache_hit_rate: float = 0.0
    errors_encountered: int = 0


class ResearchReport(BaseModel):
    """Complete research report"""
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str
    topic: str
    executive_summary: str
    sections: List[ResearchSection]
    evidence: List[EvidenceCard]
    methodology: ResearchMethodology
    metrics: ResearchMetrics
    limitations: List[str]
    recommendations: List[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0.0"
    status: Literal["complete", "partial", "failed"] = "complete"
    
    @validator('evidence')
    def validate_evidence(cls, v):
        if not v and cls.status == "complete":
            raise ValueError("Complete report must have evidence")
        return v
    
    def to_markdown(self) -> str:
        """Convert report to markdown format"""
        md = f"# Research Report: {self.topic}\n\n"
        md += f"**Report ID:** {self.report_id}\n"
        md += f"**Created:** {self.created_at.isoformat()}\n"
        md += f"**Status:** {self.status}\n\n"
        
        md += "## Executive Summary\n\n"
        md += f"{self.executive_summary}\n\n"
        
        for section in self.sections:
            md += f"## {section.title}\n\n"
            md += f"{section.content}\n\n"
            md += f"*Confidence: {section.confidence:.0%} | "
            md += f"Sources: {len(section.evidence_ids)}*\n\n"
        
        md += "## Methodology\n\n"
        md += f"**Strategy:** {self.methodology.search_strategy}\n\n"
        md += "**Quality Criteria:**\n"
        for criterion in self.methodology.quality_criteria:
            md += f"- {criterion}\n"
        md += "\n"
        
        md += "## Metrics\n\n"
        md += f"- Sources Examined: {self.metrics.total_sources_examined}\n"
        md += f"- Evidence Collected: {self.metrics.total_evidence_collected}\n"
        md += f"- Unique Domains: {self.metrics.unique_domains}\n"
        md += f"- Avg Credibility: {self.metrics.avg_credibility_score:.2f}\n"
        md += f"- Avg Relevance: {self.metrics.avg_relevance_score:.2f}\n"
        md += f"- Execution Time: {self.metrics.execution_time_seconds:.1f}s\n"
        md += f"- Total Cost: ${self.metrics.total_cost_usd:.2f}\n"
        md += f"- Cache Hit Rate: {self.metrics.cache_hit_rate:.0%}\n\n"
        
        if self.limitations:
            md += "## Limitations\n\n"
            for limitation in self.limitations:
                md += f"- {limitation}\n"
            md += "\n"
        
        if self.recommendations:
            md += "## Recommendations\n\n"
            for rec in self.recommendations:
                md += f"- {rec}\n"
            md += "\n"
        
        md += "## Evidence Sources\n\n"
        for i, evidence in enumerate(self.evidence[:20], 1):
            md += f"{i}. [{evidence.source_title}]({evidence.source_url})\n"
            md += f"   - Credibility: {evidence.credibility_score:.0%}\n"
            md += f"   - Relevance: {evidence.relevance_score:.0%}\n"
        
        return md


class PartialReport(BaseModel):
    """Partial report for degraded mode"""
    topic: str
    evidence: List[EvidenceCard]
    status: str = "partial"
    reason: str
    created_at: datetime = Field(default_factory=datetime.utcnow)