from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime

class EvidenceCard(BaseModel):
    id: str
    subtopic_name: str
    claim: str
    supporting_text: str
    source_url: str
    source_title: str
    source_domain: str
    credibility_score: float = Field(ge=0, le=1)
    is_primary_source: bool
    relevance_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    collected_at: str
    search_provider: Optional[str] = None
    publication_date: Optional[str] = None
    author: Optional[str] = None
    # Controversy tracking fields
    stance: Literal["supports", "disputes", "neutral"] = "neutral"
    claim_id: Optional[str] = None  # Cluster key for related claims
    disputed_by: List[str] = Field(default_factory=list)  # IDs/URLs of opposing evidence
    controversy_score: float = Field(default=0.0, ge=0, le=1)  # 0=consensus, 1=highly disputed

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