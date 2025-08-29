"""
Patch instructions for integrating v8.13.0 improvements into orchestrator.py

This file contains the key changes needed to integrate all v8.13.0 modules.
Apply these changes to research_system/orchestrator.py
"""

# Add these imports at the top of orchestrator.py:
IMPORTS_TO_ADD = """
from research_system.utils.file_ops import run_transaction, atomic_write_text, atomic_write_json
from research_system.config_v2 import load_quality_config
from research_system.quality.metrics_v2 import compute_metrics, gates_pass, write_metrics, FinalMetrics
from research_system.evidence.canonicalize import dedup_by_canonical, get_canonical_domain
from research_system.quality.domain_weights import mark_primary, credibility_weight
from research_system.retrieval.filters import filter_for_intent, detect_jurisdiction_from_query
from research_system.orchestrator_stats import run_stats_pipeline, prioritize_stats_sources
from research_system.report.insufficient import write_insufficient_evidence_report, format_gate_failure_message
from research_system.report.binding import (
    enforce_number_bindings, build_evidence_bindings, 
    assert_no_placeholders, validate_references_section
)
from research_system.triangulation.representative import pick_cluster_representative_card
from research_system.quality.quote_rescue import rescue_quotes, extract_key_numbers
"""

# Replace the run method with transaction wrapper:
RUN_METHOD_WRAPPER = """
def run(self):
    '''Main orchestrator run method with transaction support.'''
    
    # Load v8.13.0 configuration
    cfg = load_quality_config()
    
    # Log configuration once at start
    logger.info(
        "Quality thresholds: primary_share=%.0f%%, triangulation=%.0f%%, domain_cap=%.0f%%",
        cfg.primary_share_floor * 100,
        cfg.triangulation_floor * 100,
        cfg.domain_concentration_cap * 100
    )
    
    # Wrap entire run in transaction for atomic writes
    with run_transaction(self.s.output_dir):
        self._run_internal()

def _run_internal(self):
    '''Internal run method wrapped by transaction.'''
    # Original run method code goes here with modifications...
"""

# Key modifications to the run flow:

# 1. After evidence collection, add canonicalization:
AFTER_COLLECTION = """
# Canonicalize and deduplicate evidence
logger.info(f"Before canonicalization: {len(cards)} cards")
cards = dedup_by_canonical(cards)
logger.info(f"After canonicalization: {len(cards)} cards")

# Mark primary sources
for card in cards:
    mark_primary(card)

# Filter by intent requirements
intent = self.context.get("intent", "generic")
jurisdiction = detect_jurisdiction_from_query(self.s.topic)
cards = filter_for_intent(cards, intent, self.s.topic)
logger.info(f"After intent filtering for {intent}: {len(cards)} cards")
"""

# 2. Replace metrics computation with unified version:
METRICS_COMPUTATION = """
# Compute metrics once using v8.13.0 system
final_metrics = compute_metrics(
    cards=cards,
    clusters=paraphrase_cluster_sets,
    provider_errors=self.provider_errors,
    provider_attempts=self.provider_attempts
)

# Write metrics to file
write_metrics(self.s.output_dir, final_metrics)

# Check quality gates
intent = self.context.get("intent", "generic")
gates_passed = gates_pass(final_metrics, intent)

if not gates_passed:
    # HARD GATE: Stop here, only write insufficient evidence report
    failure_msg = format_gate_failure_message(final_metrics, intent)
    logger.warning(f"Quality gates failed: {failure_msg}")
    
    write_insufficient_evidence_report(
        output_dir=str(self.s.output_dir),
        metrics=final_metrics,
        intent=intent,
        errors=[failure_msg]
    )
    
    # CRITICAL: Return early - do NOT generate final report
    logger.info("Exiting early due to quality gate failure")
    return

# Gates passed - continue to final report generation
logger.info("Quality gates passed, generating final report")
"""

# 3. For stats intent, use specialized pipeline:
STATS_PIPELINE = """
if intent == "stats":
    # Use specialized stats pipeline
    from research_system.orchestrator_stats import run_stats_pipeline
    
    primary_cards, context_cards = run_stats_pipeline(
        query=self.s.topic,
        all_providers=available_providers,
        collect_function=self._collect_from_providers
    )
    
    # Prioritize stats sources
    cards = prioritize_stats_sources(primary_cards)
    
    # Add context cards at the end (not counted in metrics)
    cards.extend(context_cards)
    
    logger.info(f"Stats pipeline: {len(primary_cards)} primary, {len(context_cards)} context cards")
"""

# 4. Use credibility-weighted representative selection:
REPRESENTATIVE_SELECTION = """
# Select cluster representatives using credibility weighting
for cluster in paraphrase_cluster_sets:
    if hasattr(cluster, 'members'):
        representative = pick_cluster_representative_card(cluster.members, self.s.topic)
        cluster.representative = representative
"""

# 5. Enforce evidence-number binding:
EVIDENCE_BINDING = """
# Build and enforce evidence bindings for key numbers
if key_numbers:  # Assuming key_numbers is a list of bullet points
    cards_by_id = {c.id: c for c in cards if hasattr(c, 'id')}
    bindings = build_evidence_bindings(cards, key_numbers)
    
    try:
        enforce_number_bindings(key_numbers, bindings, cards_by_id)
    except BindingError as e:
        logger.error(f"Evidence binding failed: {e}")
        # Fall back to text-only bullets without numbers
        key_numbers = []

# Assert no placeholders in final report
assert_no_placeholders(report_text)
"""

# 6. Use atomic writes for all outputs:
ATOMIC_WRITES = """
# Replace all file writes with atomic versions
# Old: self._write("file.md", content)
# New:
atomic_write_text(
    str(self.s.output_dir / "file.md"),
    content
)
"""

# 7. Enhanced quote rescue with requirements:
QUOTE_RESCUE = """
# Rescue quotes with numeric requirements
rescued_quotes = rescue_quotes(cards, max_quotes=200)
logger.info(f"Rescued {len(rescued_quotes)} high-quality quotes")

# Extract key numbers from primary sources
key_numbers_data = extract_key_numbers(cards)
logger.info(f"Extracted {len(key_numbers_data)} key numbers")
"""

def apply_patch():
    """
    Instructions for applying this patch:
    
    1. Back up the original orchestrator.py
    2. Add the imports listed in IMPORTS_TO_ADD
    3. Wrap the run method with transaction support
    4. Add canonicalization after evidence collection
    5. Replace metrics computation with unified version
    6. Add stats pipeline for stats intent
    7. Use credibility-weighted representative selection
    8. Enforce evidence-number binding
    9. Replace file writes with atomic versions
    10. Add enhanced quote rescue
    
    Test thoroughly after applying patches!
    """
    pass