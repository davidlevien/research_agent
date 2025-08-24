from __future__ import annotations
from typing import List, Set
import re

def _norm(t: str) -> str:
    t = t.lower()
    t = re.sub(r"\b(1st|first)\s+quarter\b", "q1", t)
    t = re.sub(r"\b(2nd|second)\s+quarter\b", "q2", t)
    t = re.sub(r"\b(3rd|third)\s+quarter\b", "q3", t)
    t = re.sub(r"\b(4th|fourth)\s+quarter\b", "q4", t)
    t = re.sub(r"\b(grew|increased|rose|surged|up)\b", "increase", t)
    t = re.sub(r"\b(decreased|fell|declined|down|dropped)\b", "decrease", t)
    t = re.sub(r"\b(\d{1,2})\s*%\b", " NUM_PCT ", t)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return " ".join([w for w in t.split() if len(w) > 2])

def _jaccard_clusters(texts: List[str], threshold=0.82, min_overlap=3) -> List[Set[int]]:
    sigs = [set(_norm(x or "").split()) for x in texts]
    n = len(sigs); parent=list(range(n))
    def find(x): 
        while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
        return x
    def union(a,b):
        ra,rb=find(a),find(b)
        if ra!=rb: parent[rb]=ra
    for i in range(n):
        for j in range(i+1,n):
            inter = len(sigs[i] & sigs[j])
            if inter < min_overlap: continue
            u = len(sigs[i] | sigs[j]); sim = inter/u if u else 0.0
            if sim >= threshold: union(i,j)
    groups={}
    for i in range(n):
        r=find(i); groups.setdefault(r,set()).add(i)
    return [g for g in groups.values() if len(g)>=2]

def _sbert_clusters(texts: List[str], cos_threshold=0.86, min_size=2) -> List[Set[int]]:
    try:
        from sentence_transformers import SentenceTransformer
        from sklearn.metrics.pairwise import cosine_similarity
        from sklearn.cluster import AgglomerativeClustering
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        emb = model.encode(texts, normalize_embeddings=True)
        from numpy import clip
        from numpy import asarray
        dist = 1 - cosine_similarity(emb)
        thr = 1 - cos_threshold
        cl = AgglomerativeClustering(n_clusters=None, affinity="precomputed", linkage="average", distance_threshold=thr)
        labels = cl.fit_predict(dist)
        clusters = {}
        for i, k in enumerate(labels):
            clusters.setdefault(int(k), []).append(i)
        return [set(v) for v in clusters.values() if len(v) >= min_size]
    except Exception:
        return []

def hybrid_clusters(texts: List[str]) -> List[Set[int]]:
    if not texts:
        return []
    c = _sbert_clusters(texts)
    return c if c else _jaccard_clusters(texts)