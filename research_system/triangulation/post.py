"""Post-processing utilities for triangulation results."""


def sanitize_paraphrase_clusters(clusters, cards, max_frac=0.5):
    """
    Sanitize paraphrase clusters to prevent over-merging and ensure quality.
    
    Args:
        clusters: List of paraphrase clusters
        cards: List of evidence cards
        max_frac: Maximum fraction of cards that can be in a single cluster
        
    Returns:
        List of sanitized clusters
    """
    import logging
    logger = logging.getLogger(__name__)
    
    N = len(cards)
    out = []
    
    logger.info(f"\n=== SANITIZING PARAPHRASE CLUSTERS ===")
    logger.info(f"Processing {len(clusters or [])} clusters with N={N} cards, max_frac={max_frac}")
    
    for i, c in enumerate(clusters or []):
        idx = c.get("indices", [])
        
        # Extract domains for this cluster
        doms = {cards[i].source_domain for i in idx if i < len(cards)}
        
        logger.info(f"Cluster {i}: {len(idx)} cards from {len(doms)} domains")
        
        # Must be multi-domain
        if len(doms) < 2:
            logger.info(f"  -> REJECTED: single-domain cluster")
            continue
            
        # Cap giant clusters (but be reasonable - 80% of cards from diverse domains is good triangulation!)
        max_size = max(2, int(max_frac * N))
        # If the cluster has many diverse domains, be more lenient
        domain_diversity_bonus = len(doms) / 2  # Each additional domain allows more cards
        adjusted_max = max_size + int(domain_diversity_bonus * 2)
        
        if len(idx) > adjusted_max:
            logger.info(f"  -> REJECTED: cluster size {len(idx)} > adjusted_max {adjusted_max} (base {max_size} + bonus {int(domain_diversity_bonus * 2)})")
            continue
        
        logger.info(f"  -> ACCEPTED")    
        out.append(c)
    
    logger.info(f"Final result: {len(out)} clusters retained")
    return out