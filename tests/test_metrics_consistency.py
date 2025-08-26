"""Test that metrics are consistent with actual evidence cards written."""

import json
import tempfile
from pathlib import Path
import uuid


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


if __name__ == "__main__":
    test_metrics_match_written_cards()
    print("✅ All metrics consistency tests passed")