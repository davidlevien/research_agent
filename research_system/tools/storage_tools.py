"""
Storage tools for data persistence
"""

import json
import pickle
import csv
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from ..models import EvidenceCard, ResearchReport
from .registry import get_registry

logger = logging.getLogger(__name__)


class StorageTools:
    """Collection of storage tools"""
    
    def __init__(self, base_path: str = "outputs"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._register_tools()
    
    def _register_tools(self):
        """Register all storage tools"""
        tool_registry.register(
            name="save_evidence",
            description="Save evidence cards to file",
            category="storage",
            function=self.save_evidence
        )
        
        tool_registry.register(
            name="load_evidence",
            description="Load evidence cards from file",
            category="storage",
            function=self.load_evidence
        )
        
        tool_registry.register(
            name="export_report",
            description="Export research report",
            category="storage",
            function=self.export_report
        )
        
        tool_registry.register(
            name="save_checkpoint",
            description="Save research checkpoint",
            category="storage",
            function=self.save_checkpoint
        )
    
    def save_evidence(
        self,
        evidence: List[EvidenceCard],
        filename: str = "evidence_cards.jsonl"
    ) -> str:
        """Save evidence cards to JSONL file"""
        filepath = self.base_path / filename
        
        try:
            with open(filepath, 'w') as f:
                for card in evidence:
                    json_line = json.dumps(card.dict(), default=str)
                    f.write(json_line + '\n')
            
            logger.info(f"Saved {len(evidence)} evidence cards to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to save evidence: {e}")
            raise
    
    def load_evidence(self, filename: str = "evidence_cards.jsonl") -> List[EvidenceCard]:
        """Load evidence cards from JSONL file"""
        filepath = self.base_path / filename
        evidence = []
        
        if not filepath.exists():
            logger.warning(f"Evidence file not found: {filepath}")
            return evidence
        
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        card = EvidenceCard(**data)
                        evidence.append(card)
            
            logger.info(f"Loaded {len(evidence)} evidence cards from {filepath}")
            return evidence
            
        except Exception as e:
            logger.error(f"Failed to load evidence: {e}")
            return evidence
    
    def export_report(
        self,
        report: ResearchReport,
        format: str = "markdown",
        filename: Optional[str] = None
    ) -> str:
        """Export research report in specified format"""
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{timestamp}.{format}"
        
        filepath = self.base_path / filename
        
        try:
            if format == "markdown":
                content = report.to_markdown()
                filepath = filepath.with_suffix('.md')
            elif format == "json":
                content = json.dumps(report.dict(), indent=2, default=str)
                filepath = filepath.with_suffix('.json')
            elif format == "html":
                content = self._generate_html_report(report)
                filepath = filepath.with_suffix('.html')
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            filepath.write_text(content)
            logger.info(f"Exported report to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to export report: {e}")
            raise
    
    def save_checkpoint(
        self,
        data: Dict[str, Any],
        checkpoint_name: str = "checkpoint"
    ) -> str:
        """Save research checkpoint for recovery"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{checkpoint_name}_{timestamp}.pkl"
        filepath = self.base_path / "checkpoints" / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"Saved checkpoint to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            raise
    
    def load_checkpoint(self, checkpoint_path: str) -> Dict[str, Any]:
        """Load research checkpoint"""
        
        filepath = Path(checkpoint_path)
        
        if not filepath.exists():
            raise FileNotFoundError(f"Checkpoint not found: {filepath}")
        
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            
            logger.info(f"Loaded checkpoint from {filepath}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            raise
    
    def save_metrics(
        self,
        metrics: Dict[str, Any],
        filename: str = "metrics.csv"
    ) -> str:
        """Save metrics to CSV file"""
        
        filepath = self.base_path / filename
        
        try:
            # Check if file exists to determine if we need headers
            file_exists = filepath.exists()
            
            with open(filepath, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=metrics.keys())
                
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow(metrics)
            
            logger.info(f"Saved metrics to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
            raise
    
    def _generate_html_report(self, report: ResearchReport) -> str:
        """Generate HTML version of report"""
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Research Report: {report.topic}</title>
            <style>
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                    margin: 40px auto;
                    max-width: 900px;
                    line-height: 1.6;
                    color: #333;
                }}
                h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
                h2 {{ color: #34495e; margin-top: 30px; }}
                .metadata {{ 
                    background: #ecf0f1; 
                    padding: 15px; 
                    border-radius: 5px;
                    margin: 20px 0;
                }}
                .section {{ 
                    margin: 30px 0;
                    padding: 20px;
                    background: #fff;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    border-radius: 5px;
                }}
                .evidence {{ 
                    border-left: 4px solid #3498db;
                    padding-left: 15px;
                    margin: 15px 0;
                    background: #f8f9fa;
                    padding: 10px 15px;
                }}
                .metrics {{ 
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 15px;
                    margin: 20px 0;
                }}
                .metric {{ 
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 5px;
                    text-align: center;
                }}
                .metric-value {{ 
                    font-size: 24px;
                    font-weight: bold;
                    color: #3498db;
                }}
                .metric-label {{ 
                    font-size: 12px;
                    color: #7f8c8d;
                    text-transform: uppercase;
                }}
            </style>
        </head>
        <body>
            <h1>Research Report: {report.topic}</h1>
            
            <div class="metadata">
                <p><strong>Report ID:</strong> {report.report_id}</p>
                <p><strong>Created:</strong> {report.created_at}</p>
                <p><strong>Status:</strong> <span style="color: {'green' if report.status == 'complete' else 'orange'};">{report.status}</span></p>
            </div>
            
            <div class="section">
                <h2>Executive Summary</h2>
                <p>{report.executive_summary}</p>
            </div>
        """
        
        # Add sections
        for section in report.sections:
            html += f"""
            <div class="section">
                <h2>{section.title}</h2>
                <p>{section.content}</p>
                <p style="color: #7f8c8d; font-size: 14px;">
                    <em>Confidence: {section.confidence:.0%} | Sources: {len(section.evidence_ids)} | Words: {section.word_count}</em>
                </p>
            </div>
            """
        
        # Add metrics
        html += """
            <div class="section">
                <h2>Research Metrics</h2>
                <div class="metrics">
        """
        
        metrics_display = [
            ("Sources Examined", report.metrics.total_sources_examined),
            ("Evidence Collected", report.metrics.total_evidence_collected),
            ("Unique Domains", report.metrics.unique_domains),
            ("Avg Credibility", f"{report.metrics.avg_credibility_score:.0%}"),
            ("Execution Time", f"{report.metrics.execution_time_seconds:.1f}s"),
            ("Total Cost", f"${report.metrics.total_cost_usd:.2f}")
        ]
        
        for label, value in metrics_display:
            html += f"""
                <div class="metric">
                    <div class="metric-value">{value}</div>
                    <div class="metric-label">{label}</div>
                </div>
            """
        
        html += """
                </div>
            </div>
        """
        
        # Add evidence sources
        html += """
            <div class="section">
                <h2>Evidence Sources</h2>
        """
        
        for i, evidence in enumerate(report.evidence[:20], 1):
            html += f"""
            <div class="evidence">
                <h4>{i}. {evidence.source_title}</h4>
                <p>{evidence.supporting_text[:300]}...</p>
                <p style="font-size: 14px;">
                    <a href="{evidence.source_url}" target="_blank">View Source</a> | 
                    Credibility: {evidence.credibility_score:.0%} | 
                    Relevance: {evidence.relevance_score:.0%}
                </p>
            </div>
            """
        
        html += """
        </div>
        </body>
        </html>
        """
        
        return html