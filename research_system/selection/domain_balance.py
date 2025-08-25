from __future__ import annotations
from collections import Counter, defaultdict
from typing import List, Iterable, Dict, Tuple, Set
from dataclasses import dataclass
from research_system.tools.domain_norm import canonical_domain

@dataclass(frozen=True)
class BalanceConfig:
    cap: float = 0.24           # ≤ 24% per domain
    min_cards: int = 24         # target floor; triggers backfill if trimmed
    prefer_primary: bool = True # when backfilling, prefer primary institutions

PRIMARY_POOL: Set[str] = {
    "worldbank.org","oecd.org","imf.org","data.europa.eu","ec.europa.eu","eurostat.ec.europa.eu",
    "bis.org","unctad.org","wto.org","ecb.europa.eu","who.int","un.org"
}

def _domain(card) -> str:
    return canonical_domain(getattr(card, "source_domain", "") or "")

def enforce_cap(cards: List, cfg: BalanceConfig) -> Tuple[List, Dict[str,int]]:
    doms = [_domain(c) for c in cards]
    n = len(cards) or 1
    # Subtract tiny epsilon to avoid rounding up to 25%
    cap_abs = max(1, int((cfg.cap - 1e-9) * n))
    counts = Counter(doms)
    keep: List = []
    kept_per_domain = defaultdict(int)
    # stable single-pass keep until hit cap
    for c in cards:
        d = _domain(c)
        if kept_per_domain[d] < cap_abs:
            keep.append(c)
            kept_per_domain[d] += 1
    return keep, dict(kept_per_domain)

def need_backfill(cards: List, cfg: BalanceConfig) -> bool:
    return len(cards) < cfg.min_cards

def backfill_queries(topic: str) -> Iterable[str]:
    # Simple, cheap related-topic expansion: add synonyms for macro
    seeds = [
        topic,
        f"{topic} site:oecd.org", f"{topic} site:imf.org", f"{topic} site:data.europa.eu",
        f"{topic} site:eurostat.ec.europa.eu", f"{topic} site:unctad.org", f"{topic} site:wto.org",
        f"{topic} site:ecb.europa.eu", f"{topic} site:bis.org"
    ]
    # unique order
    seen = set()
    for q in seeds:
        if q not in seen:
            seen.add(q); yield q

def backfill(cards: List, topic: str, search_fn, to_cards_fn, cfg: BalanceConfig) -> List:
    have = {_domain(c) for c in cards}
    additions: List = []
    for q in backfill_queries(topic):
        rows = search_fn(q)
        seeds = to_cards_fn(rows) if to_cards_fn else rows
        for s in seeds:
            d = canonical_domain(s.get("source_domain",""))
            if d in have and d not in PRIMARY_POOL:
                continue  # prefer new primaries
            additions.append(s)
        if len(cards) + len(additions) >= cfg.min_cards:
            break
    return additions