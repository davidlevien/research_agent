from __future__ import annotations
from typing import List, Tuple
from ..router import route_topic
from ..policy import POLICIES

def build_anchors(topic: str) -> Tuple[list[str], str, object]:
    disc = route_topic(topic)
    pol = POLICIES[disc]
    qs = [tmpl.format(topic=topic) for tmpl in pol.anchor_templates]
    # generic fallback
    qs += [f"{topic} 2024..2025", f"{topic} filetype:pdf 2024..2025"]
    seen, out = set(), []
    for q in qs:
        if q not in seen:
            out.append(q); seen.add(q)
    return out, disc, pol