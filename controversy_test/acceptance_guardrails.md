## Acceptance Guardrails

### Evidence Requirements
- ✓ Minimum 3 independent sources per major claim
- ✓ Primary sources preferred (government, academic)
- ✓ All sources must be reachable and verifiable
- ✓ Publication dates clearly identified
- ✓ Author credentials when available

### Quality Thresholds
- Credibility score > 0.6 for inclusion
- Relevance score > 0.5 for primary evidence
- Confidence weighted by source quality
- Controversy score tracked for all clustered claims

### Controversy Requirements
- ✓ Claims with controversy_score ≥ 0.3 must include both supporting and disputing evidence
- ✓ All controversial claims must have proper stance attribution
- ✓ Disputed evidence must include citations to opposing sources
- ✓ High-controversy topics (score > 0.5) require balanced presentation

### Validation Checks
- ✓ JSON schema validation for all evidence cards
- ✓ URL format validation
- ✓ No duplicate evidence IDs
- ✓ Search provider attribution
- ✓ Stance consistency within claim clusters
- ✓ claim_id required for non-neutral stances

### Strict Mode Requirements
✓ All 7 deliverables must be present and non-empty
✓ Controversial claims must include both stances
