from __future__ import annotations
from typing import List, Set
def minhash_near_dupes(texts: List[str], shingle_size=6, threshold=0.92) -> List[Set[int]]:
    try:
        from datasketch import MinHash, MinHashLSH
    except Exception:
        return []
    def shingles(s, k):
        toks = (s or "").lower().split()
        for i in range(max(1, len(toks)-k+1)):
            yield " ".join(toks[i:i+k])
    mhs=[]
    for t in texts:
        m = MinHash(num_perm=128)
        for sh in shingles(t, shingle_size):
            m.update(sh.encode("utf-8"))
        mhs.append(m)
    lsh = MinHashLSH(threshold=threshold, num_perm=128)
    for i, m in enumerate(mhs): lsh.insert(f"id{i}", m)
    groups, seen = [], set()
    for i, m in enumerate(mhs):
        if i in seen: continue
        near = set(int(x[2:]) for x in lsh.query(m))
        groups.append(near); seen |= near
    return [g for g in groups if len(g) >= 2]