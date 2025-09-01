from __future__ import annotations
from typing import List, Tuple
from ..routing.provider_router import choose_providers

def build_anchors(topic: str) -> Tuple[list[str], str, object]:
    disc = choose_providers(topic)
    # Generic fallback queries - no longer using POLICIES
    qs = [
        f"{topic} 2024..2025", 
        f"{topic} filetype:pdf 2024..2025",
        f'"{topic}" statistics 2024',
        f'"{topic}" data 2024'
    ]
    seen, out = set(), []
    for q in qs:
        if q not in seen:
            out.append(q); seen.add(q)
    return out, disc.reason, disc