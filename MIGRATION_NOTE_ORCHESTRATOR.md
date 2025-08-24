# Orchestrator Migration Note

## Date: 2025-08-23

### Summary
The `orchestrator_enhanced.py` file has been deprecated in favor of the main `orchestrator.py` which now contains all PE-grade features.

### Changes Made
1. **Deprecated**: `research_system/orchestrator_enhanced.py` → `research_system/orchestrator_enhanced.py.deprecated`
2. **Updated**: `test_enhanced_features.py` to use the production orchestrator
3. **Verified**: All recent PE-grade updates are in the main `orchestrator.py`

### Reason for Change
- The enhanced orchestrator was an earlier development version
- All new surgical PE-grade updates (structured claims, contradictions, AREX, observability) were added to the main orchestrator
- Having two orchestrators was causing confusion
- The main orchestrator (46KB) is more complete than the enhanced version (24KB)

### Production Code Path
- **Main entry**: `python -m research_system --topic "..."`
- **Uses**: `research_system/main.py` → `research_system/orchestrator.py` → `Orchestrator.run()`

### Features in Production Orchestrator
✅ SBERT semantic clustering (86% threshold)
✅ MinHash deduplication (92% threshold)  
✅ Structured claim extraction with normalizations
✅ Contradiction detection
✅ Adaptive Research Expansion (AREX)
✅ Triangulation breakdown observability
✅ Discipline routing with policies
✅ Primary source connectors
✅ Enhanced strict mode with detailed failures

### Testing
All features can be tested with:
```bash
python -m pytest tests/test_normalizations.py -v
```

### No Action Required
The system will continue to work normally. This is just a cleanup to remove confusion.