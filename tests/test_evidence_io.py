from research_system.tools.evidence_io import write_jsonl, read_jsonl
from research_system.models import EvidenceCard
from pathlib import Path

def test_evidence_roundtrip(tmp_path: Path):
    p = tmp_path/"ev.jsonl"
    card = EvidenceCard(
        id="00000000-0000-4000-8000-000000000001",
        url="https://example.org/x",
        title="Title",
        snippet="support",
        provider="tavily",
        subtopic_name="Overview",
        claim="claim",
        supporting_text="support",
        source_domain="example.org",
        credibility_score=0.9,
        is_primary_source=True,
        relevance_score=0.9,
        confidence=0.8,
        collected_at="2025-01-01T00:00:00Z"
    )
    write_jsonl(str(p), [card])
    out = read_jsonl(str(p))
    assert len(out) == 1 and out[0].source_domain == "example.org"