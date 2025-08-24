import re
from collections import defaultdict
from typing import List, Dict, Any

def _norm_for_para(s: str) -> str:
    """Normalize text for paraphrase detection"""
    if not s: return ""
    s = s.lower()
    # Normalize temporal expressions
    s = re.sub(r"\b(20\d{2})\b", " YEAR ", s)
    s = re.sub(r"\bq([1-4])\s*20\d{2}\b", r" Q\1 YEAR ", s)
    s = re.sub(r"\bh([12])\s*20\d{2}\b", r" H\1 YEAR ", s)
    s = re.sub(r"\bfy\s*20\d{2}\b", " FY YEAR ", s)
    # Normalize percentages and numbers
    s = re.sub(r"\b\d+(?:\.\d+)?\s*%\b", " PCT ", s)
    s = re.sub(r"\b\d+(?:\.\d+)?\b", " NUM ", s)
    # Clean up non-alphanumeric
    s = re.sub(r"[^a-z0-9%\- ]+", " ", s)
    return " ".join(s.split())

def cluster_paraphrases(cards: List[Any]) -> List[Dict[str, Any]]:
    """
    Cluster evidence cards by paraphrase similarity
    Returns list of clusters with indices and domains
    """
    texts_raw = [getattr(c, "quote_span", None) or c.claim or c.snippet or c.title or "" for c in cards]
    texts = [_norm_for_para(t) for t in texts_raw]
    idx_map = list(range(len(texts)))
    clusters = []

    try:
        # Try SBERT for semantic similarity
        from sentence_transformers import SentenceTransformer, util
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        emb = model.encode(texts, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
        sim = util.cos_sim(emb, emb).cpu().numpy()
        
        # Union-find for clustering
        parent = list(range(len(texts)))
        def find(x):
            while parent[x] != x: 
                parent[x] = parent[parent[x]]  # Path compression
                x = parent[x]
            return x
        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb: parent[rb] = ra

        # Threshold for similarity (tuned for tourism domain)
        TH = 0.40
        n = len(texts)
        for i in range(n):
            for j in range(i+1, n):
                if sim[i, j] >= TH:
                    union(i, j)

        # Group by root
        groups = defaultdict(list)
        for i in range(n): 
            groups[find(i)].append(i)

        # Build clusters (only multi-domain ones matter for triangulation)
        for gidx, members in groups.items():
            if len(members) < 2: continue
            doms = {cards[i].source_domain for i in members}
            if len(doms) < 2: continue  # Skip single-domain clusters
            
            # Get representative claim (highest credibility)
            best_idx = max(members, key=lambda i: cards[i].credibility_score)
            representative = texts_raw[best_idx][:240]
            
            clusters.append({
                "indices": members, 
                "domains": sorted(doms),
                "representative_claim": representative,
                "size": len(members)
            })
        return clusters
        
    except Exception:
        # Fallback: token Jaccard similarity
        def tok(s): return set(s.split())
        def jacc(a, b):
            A, B = tok(a), tok(b)
            if not A or not B: return 0.0
            return len(A & B) / len(A | B)
        
        TH = 0.32  # Lower threshold for token-based
        parent = list(range(len(texts)))
        def find(x):
            while parent[x] != x: 
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb: parent[rb] = ra
            
        n = len(texts)
        for i in range(n):
            for j in range(i+1, n):
                if jacc(texts[i], texts[j]) >= TH:
                    union(i, j)
                    
        groups = defaultdict(list)
        for i in range(n): 
            groups[find(i)].append(i)
            
        clusters = []
        for members in groups.values():
            if len(members) < 2: continue
            doms = {cards[i].source_domain for i in members}
            if len(doms) < 2: continue
            
            best_idx = max(members, key=lambda i: cards[i].credibility_score)
            representative = texts_raw[best_idx][:240]
            
            clusters.append({
                "indices": members, 
                "domains": sorted(doms),
                "representative_claim": representative,
                "size": len(members)
            })
        return clusters