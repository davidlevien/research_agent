"""
Observability tools for triangulation analysis and debugging
"""

from __future__ import annotations
from typing import List, Dict, Any
from collections import Counter
import json

def generate_triangulation_breakdown(
    cards: List[Any],
    paraphrase_clusters: List[set],
    structured_matches: List[Dict[str, Any]],
    contradictions: List[Dict[str, Any]],
    dedup_count: int = 0
) -> str:
    """
    Generate a detailed triangulation breakdown for debugging.
    
    Args:
        cards: List of evidence cards
        paraphrase_clusters: List of paraphrase cluster sets
        structured_matches: List of structured claim matches
        contradictions: List of detected contradictions
        dedup_count: Number of cards removed by deduplication
    
    Returns:
        Markdown formatted breakdown report
    """
    lines = ["# Triangulation Breakdown", ""]
    
    # Summary stats
    lines.append("## Summary Statistics")
    lines.append(f"- Total evidence cards: {len(cards)}")
    lines.append(f"- Cards removed by dedup: {dedup_count}")
    lines.append(f"- Paraphrase clusters found: {len(paraphrase_clusters)}")
    lines.append(f"- Structured matches found: {len(structured_matches)}")
    lines.append(f"- Contradictions detected: {len(contradictions)}")
    lines.append("")
    
    # Triangulation rates
    paraphrase_triangulated = sum(len(c) for c in paraphrase_clusters if len(c) >= 2)
    structured_triangulated = len(structured_matches)
    total_triangulated = paraphrase_triangulated + structured_triangulated
    
    if cards:
        paraphrase_rate = (paraphrase_triangulated / len(cards)) * 100
        structured_rate = (structured_triangulated / len(cards)) * 100
        total_rate = (total_triangulated / len(cards)) * 100
    else:
        paraphrase_rate = structured_rate = total_rate = 0
    
    lines.append("## Triangulation Rates")
    lines.append(f"- Paraphrase triangulation: {paraphrase_rate:.1f}%")
    lines.append(f"- Structured triangulation: {structured_rate:.1f}%")
    lines.append(f"- Combined triangulation: {total_rate:.1f}%")
    lines.append("")
    
    # Top paraphrase clusters
    if paraphrase_clusters:
        lines.append("## Top Paraphrase Clusters")
        for i, cluster in enumerate(paraphrase_clusters[:5], 1):
            if len(cluster) >= 2:
                sample_idx = list(cluster)[0]
                if sample_idx < len(cards):
                    sample_text = getattr(cards[sample_idx], 'quote_span', None) or \
                                 getattr(cards[sample_idx], 'claim', '') or \
                                 getattr(cards[sample_idx], 'snippet', '')
                    lines.append(f"{i}. **{len(cluster)} sources**: {sample_text[:100]}...")
                    
                    # Show domains
                    domains = set()
                    for idx in cluster:
                        if idx < len(cards):
                            domain = getattr(cards[idx], 'source_domain', 'unknown')
                            domains.add(domain)
                    lines.append(f"   - Domains: {', '.join(sorted(domains))}")
        lines.append("")
    
    # Top uncorroborated structured claims
    lines.append("## Top Uncorroborated Structured Claims")
    
    # Extract all structured claims
    from .claim_struct import extract_struct_claim, struct_key
    
    all_keys = []
    key_examples = {}
    for i, card in enumerate(cards):
        text = getattr(card, 'quote_span', None) or \
               getattr(card, 'claim', '') or \
               getattr(card, 'snippet', '')
        sc = extract_struct_claim(text)
        k = struct_key(sc)
        if k:
            all_keys.append(k)
            if k not in key_examples:
                key_examples[k] = {
                    "text": text[:150],
                    "entity": sc.entity,
                    "metric": sc.metric,
                    "period": sc.period,
                    "value": sc.value,
                    "unit": sc.unit
                }
    
    # Find uncorroborated (single occurrence)
    key_counts = Counter(all_keys)
    uncorroborated = [(k, v) for k, v in key_counts.items() if v == 1]
    uncorroborated.sort(key=lambda x: x[0])  # Sort by key
    
    for i, (key, count) in enumerate(uncorroborated[:5], 1):
        example = key_examples.get(key, {})
        entity = example.get("entity", "?")
        metric = example.get("metric", "?")
        period = example.get("period", "?")
        value = example.get("value")
        unit = example.get("unit")
        
        lines.append(f"{i}. **{entity} | {metric} | {period}**")
        if value is not None:
            val_str = f"{value}{unit or ''}"
            lines.append(f"   - Value: {val_str}")
        lines.append(f"   - Example: \"{example.get('text', '')}...\"")
    lines.append("")
    
    # Top contradictions
    if contradictions:
        lines.append("## Detected Contradictions")
        for i, conflict in enumerate(contradictions[:5], 1):
            key_parts = conflict["key"].split("|")
            entity = key_parts[0] if len(key_parts) > 0 else "?"
            metric = key_parts[1] if len(key_parts) > 1 else "?"
            period = key_parts[2] if len(key_parts) > 2 else "?"
            
            v1, v2 = conflict["values"]
            u1, u2 = conflict.get("units", [None, None])
            
            lines.append(f"{i}. **{entity} | {metric} | {period}**")
            lines.append(f"   - Source 1: {v1}{u1 or ''}")
            lines.append(f"   - Source 2: {v2}{u2 or ''}")
            lines.append(f"   - Difference: {abs(v1-v2):.1f}")
        lines.append("")
    
    # Domain distribution
    lines.append("## Domain Distribution")
    domain_counts = Counter()
    for card in cards:
        domain = getattr(card, 'source_domain', 'unknown')
        domain_counts[domain] += 1
    
    for domain, count in domain_counts.most_common(10):
        pct = (count / len(cards)) * 100 if cards else 0
        lines.append(f"- {domain}: {count} ({pct:.1f}%)")
    
    return "\n".join(lines)


def generate_strict_failure_details(
    triangulation_rate: float,
    structured_rate: float,
    paraphrase_rate: float,
    primary_share: float,
    domain_concentration: float,
    thresholds: Dict[str, float],
    reachability: float = 1.0,
    low_quality_share: float = 0.0
) -> str:
    """
    Generate detailed failure message for strict mode.
    
    Args:
        triangulation_rate: Overall triangulation rate
        structured_rate: Structured claim triangulation rate
        paraphrase_rate: Paraphrase triangulation rate
        primary_share: Share of primary sources
        domain_concentration: Top domain concentration
        thresholds: Dictionary of threshold values
        reachability: Share of reachable sources
        low_quality_share: Share of low-quality domains
    
    Returns:
        Detailed failure message
    """
    failures = []
    
    # Check triangulation
    tri_min = thresholds.get("triangulation_min", 0.35)
    if triangulation_rate < tri_min:
        failures.append(
            f"TRIANGULATION(paraphrase={paraphrase_rate:.0%}, "
            f"structured={structured_rate:.0%}, "
            f"union={triangulation_rate:.0%}) < {tri_min:.0%}"
        )
    
    # Check primary share
    primary_min = thresholds.get("primary_share_min", 0.50)
    if primary_share < primary_min:
        failures.append(
            f"PRIMARY_SHARE({primary_share:.0%}) < {primary_min:.0%}"
        )
    
    # Check domain concentration
    domain_max = thresholds.get("domain_concentration_max", 0.25)
    if domain_concentration > domain_max:
        failures.append(
            f"TOP_DOMAIN_SHARE({domain_concentration:.0%}) > {domain_max:.0%}"
        )
    
    # Check reachability
    reach_min = thresholds.get("reachability_min", 0.5)
    if reachability < reach_min:
        failures.append(
            f"REACHABILITY({reachability:.0%}) < {reach_min:.0%}"
        )
    
    # Check low-quality domain share
    low_max = thresholds.get("low_quality_max", 0.10)
    if low_quality_share > low_max:
        failures.append(
            f"LOW_QUALITY_SHARE({low_quality_share:.0%}) > {low_max:.0%}"
        )
    
    return " | ".join(failures) if failures else "All checks passed"