"""Post-processing utilities for triangulation results."""

from math import ceil


def _cap_for_cluster(n_cards: int, n_domains: int, total_cards: int) -> int:
    """Calculate maximum cluster size based on domain diversity."""
    # Base cap: 20% of run size, with a floor and ceiling
    base = max(3, ceil(0.20 * total_cards))
    # Diversity bonus: +10% of run size per extra domain (beyond 1)
    bonus = ceil(0.10 * total_cards) * max(0, n_domains - 1)
    # Hard absolute ceiling (prevents pathological over-merge)
    return min(base + bonus, max(8, ceil(0.35 * total_cards)))


def sanitize_paraphrase_clusters(clusters, cards, max_frac=0.5):
    """
    Sanitize paraphrase clusters to prevent over-merging and ensure quality.
    
    PE-grade filtering with domain diversity requirements.
    
    Args:
        clusters: List of paraphrase clusters
        cards: List of evidence cards
        max_frac: Maximum fraction of cards that can be in a single cluster (deprecated, kept for compatibility)
        
    Returns:
        List of sanitized clusters
    """
    import logging
    logger = logging.getLogger(__name__)
    
    total = len(cards)
    out = []
    
    logger.info(f"\n=== SANITIZING PARAPHRASE CLUSTERS ===")
    logger.info(f"Processing {len(clusters or [])} clusters with {total} total cards")
    
    for i, c in enumerate(clusters or []):
        idx = c.get("indices", [])
        
        # Extract domains for this cluster
        doms = sorted(set(cards[j].source_domain for j in idx if j < len(cards)))
        
        logger.info(f"Cluster {i}: {len(idx)} cards from {len(doms)} domains {doms[:3]}...")
        
        # Must have ≥2 domains to be a triangulation candidate
        if len(doms) < 2:
            logger.info(f"  -> REJECTED: single-domain cluster")
            continue
            
        # Calculate cap based on domain diversity
        cap = _cap_for_cluster(len(idx), len(doms), total)
        
        if len(idx) > cap:
            logger.info(f"  -> TRIMMING: cluster size {len(idx)} > cap {cap} (keeping most similar)")
            # Keep the most central items (highest similarity if available)
            sim_scores = c.get("sim", [1.0] * len(idx))  # Default to 1.0 if no sim scores
            idx_sim = list(zip(idx, sim_scores))
            idx_sim.sort(key=lambda t: t[1], reverse=True)
            kept_indices = [i for i, _ in idx_sim[:cap]]
            
            # Create trimmed cluster
            c2 = dict(c)
            c2["indices"] = kept_indices
            c2["size"] = len(kept_indices)
            logger.info(f"  -> ACCEPTED after trimming to {len(kept_indices)} cards")
            out.append(c2)
        else:
            logger.info(f"  -> ACCEPTED")    
            out.append(c)
    
    logger.info(f"Final result: {len(out)} clusters retained")
    return out