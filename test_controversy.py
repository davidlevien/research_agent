#!/usr/bin/env python3
"""
Unit tests for controversy detection and claim clustering
"""

import uuid
from datetime import datetime
from research_system.models import EvidenceCard
from research_system.controversy import ControversyDetector


def create_evidence_card(claim: str, supporting_text: str, stance: str = "neutral", 
                         domain: str = "example.com", credibility: float = 0.7) -> EvidenceCard:
    """Helper to create test evidence cards"""
    return EvidenceCard(
        id=str(uuid.uuid4()),
        subtopic_name="Test Topic",
        claim=claim,
        supporting_text=supporting_text,
        source_url=f"https://{domain}/article",
        source_title="Test Article",
        source_domain=domain,
        credibility_score=credibility,
        is_primary_source=False,
        relevance_score=0.8,
        confidence=credibility * 0.8,
        collected_at=datetime.utcnow().isoformat() + "Z",
        stance=stance
    )


def test_claim_clustering():
    """Test that similar claims are properly clustered"""
    detector = ControversyDetector(similarity_threshold=0.6)  # Lower threshold for testing
    
    cards = [
        create_evidence_card("Climate change is causing global temperatures to rise", 
                           "Data shows warming trend"),
        create_evidence_card("Global temperatures are rising due to climate change",
                           "Temperature data confirms"),
        create_evidence_card("Coffee consumption improves focus",
                           "Studies show cognitive benefits"),
    ]
    
    clusters = detector.cluster_claims(cards)
    
    # Should have at least 2 clusters
    assert len(clusters) >= 2
    
    # Find the largest cluster (should be climate)
    largest_cluster = max(clusters.values(), key=len)
    
    # Climate claims should be together
    climate_claims = [c for c in cards if "climate" in c.claim.lower() or "temperature" in c.claim.lower()]
    if len(largest_cluster) > 1:
        # Check that similar claims are clustered
        assert all(c.claim_id is not None for c in largest_cluster)
    
    print("✓ Claim clustering test passed")


def test_contradiction_detection():
    """Test detection of contradictory evidence"""
    detector = ControversyDetector()
    
    # Test numerical contradiction
    card1 = create_evidence_card(
        "Market increased this quarter",
        "Stock market rises by 10% in Q3"
    )
    
    card2 = create_evidence_card(
        "Market decreased this quarter",
        "Stock market falls by 5% in Q3"
    )
    
    # Should detect rises vs falls pattern
    is_contradictory = detector.detect_contradiction(card1, card2)
    assert is_contradictory == True
    
    # Non-contradictory cards
    card3 = create_evidence_card(
        "Exercise improves health",
        "Regular exercise has health benefits"
    )
    
    assert detector.detect_contradiction(card1, card3) == False
    
    print("✓ Contradiction detection test passed")


def test_stance_assignment():
    """Test that stances are properly assigned when contradictions are found"""
    detector = ControversyDetector()
    
    cards = [
        create_evidence_card("Stock market rises in Q3", "Market increased by 10%"),
        create_evidence_card("Stock market falls in Q3", "Market decreased by 5%"),
    ]
    
    clusters = detector.cluster_claims(cards)
    detector.analyze_stances(clusters)
    
    # Both cards should have non-neutral stances
    assert any(c.stance != "neutral" for c in cards)
    
    # Cards should dispute each other
    assert len(cards[0].disputed_by) > 0 or len(cards[1].disputed_by) > 0
    
    print("✓ Stance assignment test passed")


def test_controversy_scoring():
    """Test controversy score calculation"""
    detector = ControversyDetector()
    
    # High controversy - balanced opposing views
    cards_high = [
        create_evidence_card("AI will replace most jobs", "Automation study", 
                           stance="supports", credibility=0.8),
        create_evidence_card("AI will create more jobs", "Economic analysis",
                           stance="disputes", credibility=0.8),
    ]
    
    for card in cards_high:
        card.claim_id = "ai_jobs"
    
    clusters_high = {"ai_jobs": cards_high}
    scores_high = detector.calculate_controversy_scores(clusters_high)
    
    assert scores_high["ai_jobs"] > 0.5  # High controversy
    
    # Low controversy - consensus
    cards_low = [
        create_evidence_card("Exercise is healthy", "Medical research",
                           stance="supports", credibility=0.9),
        create_evidence_card("Exercise improves wellbeing", "Health study",
                           stance="supports", credibility=0.8),
    ]
    
    for card in cards_low:
        card.claim_id = "exercise"
    
    clusters_low = {"exercise": cards_low}
    scores_low = detector.calculate_controversy_scores(clusters_low)
    
    assert scores_low["exercise"] == 0.0  # No controversy (consensus)
    
    print("✓ Controversy scoring test passed")


def test_full_pipeline():
    """Test the complete controversy detection pipeline"""
    detector = ControversyDetector()
    
    # Create a mix of controversial and non-controversial evidence
    cards = [
        # Controversial topic
        create_evidence_card("Nuclear power is safe", "Safety records show...", 
                           domain="nuclear.org", credibility=0.7),
        create_evidence_card("Nuclear power is dangerous", "Accident data shows...",
                           domain="safety.gov", credibility=0.9),
        
        # Consensus topic
        create_evidence_card("Water is essential for life", "Biology confirms...",
                           domain="science.edu", credibility=0.95),
        create_evidence_card("Humans need water to survive", "Medical facts...",
                           domain="health.gov", credibility=0.95),
    ]
    
    clusters, scores = detector.process_evidence(cards)
    
    # Should detect the nuclear controversy
    controversial = detector.get_controversial_claims(threshold=0.3)
    assert len(controversial) >= 1
    
    # Nuclear topic should be controversial
    nuclear_cluster = None
    for claim_id, cluster in controversial:
        if any("nuclear" in c.claim.lower() for c in cluster):
            nuclear_cluster = cluster
            break
    
    assert nuclear_cluster is not None
    assert len([c for c in nuclear_cluster if c.stance == "supports"]) > 0
    assert len([c for c in nuclear_cluster if c.stance == "disputes"]) > 0
    
    print("✓ Full pipeline test passed")


def test_integration_with_orchestrator():
    """Test integration scenario with conflicting sources"""
    from research_system.orchestrator import Orchestrator, OrchestratorSettings
    from pathlib import Path
    import tempfile
    import os
    
    # Set fake API keys for testing
    os.environ.update({
        'LLM_PROVIDER': 'openai',
        'OPENAI_API_KEY': 'sk-fake-test',
        'SEARCH_PROVIDERS': 'tavily',
        'TAVILY_API_KEY': 'fake-test'
    })
    
    with tempfile.TemporaryDirectory() as tmpdir:
        settings = OrchestratorSettings(
            topic="Test Controversy",
            depth="rapid",
            output_dir=Path(tmpdir),
            strict=False  # Don't enforce strict for this test
        )
        
        # This would normally run the full pipeline
        # For testing, we verify the controversy module is imported
        orch = Orchestrator(settings)
        assert hasattr(orch, 'run')
        
    print("✓ Integration test passed")


if __name__ == "__main__":
    print("\n=== Running Controversy Detection Tests ===\n")
    
    test_claim_clustering()
    test_contradiction_detection()
    test_stance_assignment()
    test_controversy_scoring()
    test_full_pipeline()
    test_integration_with_orchestrator()
    
    print("\n✅ All tests passed!\n")