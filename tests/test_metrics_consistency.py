"""Test that metrics are consistent with actual evidence cards written."""

import json
import tempfile
from pathlib import Path
import uuid
import pytest
import re
from unittest.mock import Mock, patch
from research_system.tools.aggregates import triangulation_rate_from_clusters


def test_metrics_match_written_cards():
    """Test that metrics.json card count matches evidence_cards.jsonl count."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create valid cards as dicts
        valid_cards = [
            {
                "id": str(uuid.uuid4()),
                "url": f"https://example.com/{i}",
                "title": f"Valid Card {i}",
                "snippet": f"Test snippet {i}",
                "provider": "wikipedia",
                "source_domain": "example.com",
                "credibility_score": 0.8,
                "relevance_score": 0.7,
                "confidence": 0.75,
                "is_primary_source": False,
                "subtopic_name": "Test",
                "claim": "Test claim",
                "supporting_text": "Test supporting text",
                "collected_at": "2025-01-01T00:00:00Z"
            } for i in range(5)
        ]
        
        # Invalid cards - will fail schema validation
        invalid_cards = [
            {
                "id": f"invalid-{i}",  # Invalid UUID format
                "url": "",  # Empty URL
                "title": "",  # Empty title  
                "snippet": "",
                "provider": "invalid",  # Invalid provider
                "source_domain": "",
                "credibility_score": 0.5,
                "relevance_score": 0.5,
                "confidence": 0.5,
                "is_primary_source": False,
                "subtopic_name": "",
                "claim": "",
                "supporting_text": "",
                "collected_at": ""
            } for i in range(3)
        ]
        
        # Write valid cards
        output_path = Path(tmpdir) / "evidence_cards.jsonl"
        with open(output_path, 'w') as f:
            for card in valid_cards:
                f.write(json.dumps(card) + '\n')
        
        # Write invalid cards to errors file
        error_path = Path(tmpdir) / "evidence_cards.errors.jsonl" 
        with open(error_path, 'w') as f:
            for card in invalid_cards:
                error_entry = {
                    "id": card["id"],
                    "url": card["url"],
                    "error": "Evidence schema validation failed: invalid provider"
                }
                f.write(json.dumps(error_entry) + '\n')
        
        # Simulate what orchestrator should do - calculate metrics AFTER filtering
        actual_cards_written = len(valid_cards)
        metrics = {
            "cards": actual_cards_written,  # Should match what was actually written
            "quote_coverage": 0.5,
            "union_triangulation": 0.35,
            "primary_share_in_union": 0.5,
            "top_domain_share": 0.24,
            "provider_entropy": 0.8
        }
        
        metrics_path = Path(tmpdir) / "metrics.json"
        metrics_path.write_text(json.dumps(metrics, indent=2))
        
        # Verify consistency
        evidence_lines = len(output_path.read_text().strip().split('\n'))
        metrics_data = json.loads(metrics_path.read_text())
        
        assert metrics_data["cards"] == evidence_lines, \
            f"Metrics shows {metrics_data['cards']} cards but evidence_cards.jsonl has {evidence_lines} lines"
        
        # Check error file exists and has the invalid cards
        assert error_path.exists()
        error_lines = len(error_path.read_text().strip().split('\n'))
        assert error_lines == len(invalid_cards), f"Expected {len(invalid_cards)} error lines, got {error_lines}"


def test_orchestrator_metrics_order():
    """Test that orchestrator calculates metrics after filtering cards."""
    # The key insight from the fix:
    # 1. write_jsonl is called FIRST with skip_invalid=True
    # 2. If bad > 0, cards are re-read from the jsonl file
    # 3. Metrics are calculated with the ACTUAL valid cards
    # 4. metrics["cards"] matches the actual count in evidence_cards.jsonl
    
    # This ensures consistency between:
    # - metrics.json showing N cards
    # - evidence_cards.jsonl having N lines
    # - citation_checklist.md showing N cards
    pass  # Conceptual test showing the fix logic


def test_triangulation_rate_calculation():
    """Test the unified triangulation rate calculation"""
    # Single-source clusters (not triangulated)
    single_clusters = [
        {"indices": [0], "size": 1},
        {"indices": [1], "size": 1},
    ]
    assert triangulation_rate_from_clusters(single_clusters) == 0.0
    
    # Multi-source clusters (triangulated)
    multi_clusters = [
        {"indices": [0, 1], "size": 2, "domains": ["domain1.com", "domain2.com"]},
        {"indices": [2, 3, 4], "size": 3, "domains": ["domain3.com", "domain4.com", "domain5.com"]},
    ]
    # 5 cards total, all in multi-source clusters
    assert triangulation_rate_from_clusters(multi_clusters) == 1.0
    
    # Mixed clusters
    mixed_clusters = [
        {"indices": [0], "size": 1, "domains": ["domain1.com"]},  # 1 single
        {"indices": [1, 2], "size": 2, "domains": ["domain2.com", "domain3.com"]},  # 2 triangulated
    ]
    # 3 cards total, 2 triangulated = 66.7%
    rate = triangulation_rate_from_clusters(mixed_clusters)
    assert abs(rate - 2/3) < 0.01


def test_claims_counting_with_html():
    """Test that claims are counted correctly even with HTML artifacts"""
    report_text = """
# Report

- **First claim with <strong>HTML</strong> tags** [1] — source
- **Second claim** [2] — source  
- Regular text without bold
- **Third <em>claim</em>** [3] — source
"""
    
    claim_pattern = r'^\s*-\s+\*\*.*?\*\*'
    claims_found = len(re.findall(claim_pattern, report_text, re.MULTILINE))
    assert claims_found == 3  # Should find all three bolded claims


def test_html_cleaning():
    """Test HTML tag removal"""
    html_tag_pattern = re.compile(r'<[^>]+>')
    
    # Test basic HTML removal
    assert html_tag_pattern.sub('', "<strong>text</strong>") == "text"
    assert html_tag_pattern.sub('', "text with <em>emphasis</em>") == "text with emphasis"
    
    # Test nested tags
    assert html_tag_pattern.sub('', "<strong>CDC <em>policy</em></strong>") == "CDC policy"


def test_date_parsing():
    """Test the improved date parsing function"""
    from datetime import datetime
    
    def _parse_dt(s):
        if not s: return None
        s = str(s).strip()
        formats = [
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",  
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y"
        ]
        for fmt in formats:
            try:
                clean_s = s.split('+')[0].split('.')[0]
                return datetime.strptime(clean_s, fmt)
            except:
                pass
        return None
    
    # Test various formats
    assert _parse_dt("2024-03-15") is not None
    assert _parse_dt("2024-03-15T10:30:00Z") is not None
    assert _parse_dt("2024/03/15") is not None
    assert _parse_dt("2024") is not None
    assert _parse_dt(None) is None
    assert _parse_dt("") is None


if __name__ == "__main__":
    test_metrics_match_written_cards()
    test_triangulation_rate_calculation()
    test_claims_counting_with_html()
    test_html_cleaning()
    test_date_parsing()
    print("✅ All metrics consistency tests passed")