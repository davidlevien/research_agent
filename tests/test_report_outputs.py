import re
from research_system.report.key_numbers import compose_key_numbers_section
from research_system.report.composer import compose_key_numbers, compose_findings
from research_system.text.contradictions import prune_conflicts

def test_key_numbers_are_numeric(tmp_path):
    class MockClaim:
        def __init__(self, text, source):
            self.text = text
            self.source = source
    
    md = compose_key_numbers_section([
        MockClaim("Top 1% effective rate: 23% in 2022", {"url":"https://treasury.gov/x"})
    ])
    assert "%" in md and "source" in md

def test_findings_no_advocacy_language():
    class MockCard:
        def __init__(self, text, domain_count=2, cred_score=0.9):
            self.text = text
            self.domain_count = domain_count
            self.cred_score = cred_score
            self.source = {"url": "https://oecd.org"}
            self.url = "https://oecd.org"
    
    cards = [
        MockCard("Tax rates increase by 2%"),
        MockCard("Project 2025 will hurt the middle class")  # Should be filtered
    ]
    
    bullets = compose_findings(cards)
    assert "Project 2025" not in bullets

def test_contradiction_prune():
    class MockCard:
        def __init__(self, text, domain_count=2, cred_score=0.9):
            self.text = text
            self.domain_count = domain_count
            self.cred_score = cred_score
            self.source = {"url": "https://oecd.org"}
    
    kept = prune_conflicts([
        MockCard("Tax increases reduce GDP by 1%"), 
        MockCard("Tax increases raise GDP by 1%")
    ], keep=1)
    assert len(kept) == 1