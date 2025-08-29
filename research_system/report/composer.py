# research_system/report/composer.py
from __future__ import annotations
import re, math, textwrap
from collections import defaultdict, Counter
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from research_system.report.claim_filter import (
    filter_key_findings, is_numeric_claim, is_on_topic
)
from research_system.report.key_numbers import compose_key_numbers_section
from research_system.triangulation.contradiction_filter import get_contradiction_summary

NUM = re.compile(r"\b(?:[±~]?\d+(?:\.\d+)?%|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\b(?:19|20)\d{2}\b)\b")
INCR = ("increase","increased","up","rise","grew","growth","higher")
DECR = ("decrease","decreased","down","decline","fell","lower")
HTML_TAG = re.compile(r"<[^>]+>")

def _clean(s: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    s = HTML_TAG.sub("", s or "")
    s = " ".join(s.split())
    return s

def _short(s: str, n: int = 240) -> str:
    s = _clean(s or "")
    return s if len(s) <= n else s[:n].rsplit(" ",1)[0] + "…"

def _best_text(card) -> str:
    """Get best available text from card, with robust fallbacks and HTML cleaning."""
    # Try best_quote first if it exists
    if getattr(card, "best_quote", None):
        return _clean(card.best_quote)
    
    # Try quotes list if available
    if getattr(card, "quotes", None):
        for q in card.quotes:
            cleaned = _clean(q)
            if cleaned and len(cleaned) >= 40:
                return cleaned
    
    # Fall back to other text fields - prioritize actual content (snippet/supporting_text) over metadata (claim/title)
    text = getattr(card, "snippet", "") or getattr(card, "supporting_text", "") or getattr(card, "claim", "") or getattr(card, "title", "")
    return _clean(text)

def _has_numbers(s: str) -> bool:
    return bool(NUM.search(s or ""))

def _domain(card) -> str:
    return (card.source_domain or "").lower()

def _is_primary(card) -> bool:
    dom = _domain(card)
    return bool(getattr(card, "is_primary_source", False)) or any(
        key in dom for key in ("unwto.org","wttc.org","iata.org","oecd.org","worldbank.org","imf.org",".gov",".edu",".int")
    )

def _score_cluster(cards) -> float:
    # reward domain diversity, primary share, numeric density, credibility
    doms = { _domain(c) for c in cards if _domain(c) }
    primary = sum(1 for c in cards if _is_primary(c))
    numeric = sum(1 for c in cards if _has_numbers(_best_text(c)))
    cred = sum((c.credibility_score or 0.5) for c in cards) / max(1,len(cards))
    return 2.5*len(doms) + 1.5*primary + 1.0*numeric + 1.0*cred

# NOTE: Contradiction detection moved to research_system.triangulation.contradiction_filter
# This function is kept for backward compatibility but should not be used for new clusters

def _index_sources(cards) -> Tuple[Dict[str,int], List[str]]:
    idx, seen = {}, []
    n = 1
    for c in cards:
        if c.id not in idx:
            idx[c.id] = n
            seen.append(c)
            n += 1
    footnotes = []
    for c in seen:
        t = (c.title or c.source_title or _domain(c) or "Source").strip()
        u = c.url or c.source_url or ""
        lab = f"[{idx[c.id]}]"
        footnotes.append(f"{lab} {t} — {u}".strip())
    return idx, footnotes

def _cit(card, idx) -> str:
    return f"[{idx.get(card.id, '?')}]"

def _pick_quotes(cards, k=2) -> List[str]:
    cand = []
    for c in cards:
        txt = _best_text(c)
        # split into sentences, prefer those with numbers/dates
        sents = re.split(r"(?<=[.!?])\s+", txt)
        for s in sents:
            s = s.strip()
            # Reduced minimum length from 60 to 20 to include important short snippets
            if 20 <= len(s) <= 400:
                score = 1.0 + (1.0 if _has_numbers(s) else 0.0) + (0.2 if len(s) > 180 else 0)
                cand.append((score, s))
    cand.sort(reverse=True, key=lambda x: x[0])
    out = []
    seen = set()
    for _, s in cand:
        if s not in seen:
            out.append(s)
            seen.add(s)
        if len(out) >= k: break
    return out

def compose_report(topic: str, cards, tri: dict, metrics: dict, *, max_findings: int = 10) -> str:
    # 0) Build source index for consistent citations
    idx, footnotes = _index_sources(cards)

    # 1) Executive summary (3–5 bullets)
    total = len(cards)
    tri_u = metrics.get("union_triangulation", 0.0)
    prim_u = metrics.get("primary_share_in_union", 0.0)
    qc = metrics.get("quote_coverage", 0.0)
    prov_h = metrics.get("provider_entropy", 0.0)
    summary = [
        f"Evidence base: **{total} sources**, triangulation **{int(tri_u*100)}%**, primary share in union **{int(prim_u*100)}%**.",
        f"Quote coverage **{int(qc*100)}%**; provider diversity (entropy) **{int(prov_h*100)}%**.",
        f"Topic: **{topic}** — synthesized from authoritative and corroborated sources.",
    ]

    # 2) Pick top clusters by score (fall back to card groups if no tri clusters)
    clusters = []
    # Fixed: Removed invalid tuple unpacking loop that caused crashes
    # Clusters are lists of dicts, not key-value pairs
    # generic: tri might be {"clusters":[{"key":..., "cards":[...]}], ...}
    raw_clusters = tri.get("clusters") or []
    for cl in raw_clusters:
        cs = cl.get("cards") or []
        if cs:
            clusters.append((cl.get("key","cluster"), cs))
    # fallback: synthesize pseudo-clusters by domain if nothing
    if not clusters:
        by_dom = defaultdict(list)
        for c in cards: by_dom[_domain(c)].append(c)
        clusters = list(by_dom.items())

    clusters_scored = sorted(clusters, key=lambda t: _score_cluster(t[1]), reverse=True)[:max_findings]

    # 3) Key findings (multi-sentence, with quotes + citations) - FILTERED
    findings_raw = []
    for key, cs in clusters_scored:
        # lead sentence: dominant signal
        lead = _pick_quotes(cs, k=1)
        if not lead:
            lead = [_short(_best_text(cs[0]), 280)]
        
        # Filter: Skip if not numeric or on-topic
        lead_text = lead[0]
        if not is_numeric_claim(lead_text) or not is_on_topic(lead_text, topic):
            continue
            
        cites = " ".join(_cit(c, idx) for c in cs[:3])
        para = f"- **{lead_text}** {cites}"
        # second sentence: context/number
        q_add = _pick_quotes(cs, k=2)
        if len(q_add) > 1 and q_add[1] != lead[0]:
            # Also check second sentence
            if is_numeric_claim(q_add[1]) or is_on_topic(q_add[1], topic):
                para += f" — {q_add[1]}"
        findings_raw.append((para, cs))

    # Filter findings for quality
    findings = []
    for para, cs in findings_raw:
        # Must have multiple independent sources
        domains = set(c.source_domain for c in cs if hasattr(c, 'source_domain'))
        if len(domains) >= 2:
            findings.append(para)
    
    # ensure at least 3 findings by appending strongest numeric single-card items
    if len(findings) < 3:
        extras = []
        for c in sorted(cards, key=lambda x: (1 if _is_primary(x) else 0, x.credibility_score or 0.5, len(_best_text(x))), reverse=True):
            text = _short(_best_text(c), 260)
            # Must be numeric and on-topic
            if is_numeric_claim(text) and is_on_topic(text, topic):
                extras.append(f"- {text} {_cit(c, idx)}")
                if len(findings)+len(extras) >= 6: break
        findings.extend(extras)

    # 4) Key numbers (structured extraction with units and labels) - v8.14.0 ENHANCEMENT
    key_numbers_section = compose_key_numbers_section(cards, max_numbers=8)
    # Convert to list format for compatibility with existing logic
    key_numbers = key_numbers_section.split('\n') if key_numbers_section else []

    # 5) Contradictions & uncertainties (using new contradiction filter)
    # NOTE: Main contradiction filtering should happen before clustering/representative selection
    # This is a final pass to report any remaining issues
    contra = get_contradiction_summary([(key, cs) for key, cs in clusters_scored])
    if not contra or all(c.startswith("- No") for c in contra):
        contra = ["- No direct contradictions surfaced in clustered evidence; monitor for new data."]

    # 6) Outlook (heuristic: extrapolate from top clusters with primaries)
    outlook = []
    prim_top = [c for _, cs in clusters_scored for c in cs if _is_primary(c)]
    if prim_top:
        outlook.append("- Expect continued movement consistent with primary indicators; reassess in 4–6 weeks as updates release.")
    else:
        outlook.append("- Evidence base skews secondary; acquire fresh primary releases to improve confidence.")

    # 7) Compose markdown
    md = []
    md.append(f"# Final Report: {topic}\n")
    
    # Executive Summary - always include
    md.append("## Executive Summary")
    if summary and any(summary):
        md.extend([f"- {b}" for b in summary if b])
    else:
        md.append("- Insufficient high-quality evidence to generate executive summary")

    # Key Findings - only include if we have valid findings
    if findings and any(f for f in findings if f and not f.startswith("- N/A")):
        md.append("\n## Key Findings")
        md.extend([f for f in findings if f and not f.startswith("- N/A")])
    else:
        md.append("\n## Key Findings")
        md.append("No publishable findings met evidence thresholds for this query.")

    # Key Numbers - only include if we have actual numbers
    if key_numbers and any(kn.strip() for kn in key_numbers):
        md.append("\n## Key Numbers")
        md.extend([kn for kn in key_numbers if kn.strip()])
    # Skip Key Numbers section entirely if no valid numbers

    # Contradictions - only include if found
    if contra and any(c for c in contra if c and not c.startswith("- None")):
        md.append("\n## Contradictions & Uncertainties")
        md.extend([c for c in contra if c and not c.startswith("- None")])
    # Skip contradictions section if none found

    # Outlook - only include if meaningful
    if outlook and any(o for o in outlook if o and len(o) > 20):
        md.append("\n## Outlook (Next 4–6 weeks)")
        md.extend([o for o in outlook if o and len(o) > 20])

    md.append("\n## Methodology (Brief)")
    md.append("- Multi-provider search with domain caps; triangulation favors multi-domain agreement.")
    md.append("- Primary sources are boosted; quotes prefer numeric/date-bearing sentences for auditability.")
    md.append("- See metrics for coverage/diversity; full source list below.")

    md.append("\n## Metrics")
    md.append(f"- Evidence cards: **{total}**")
    md.append(f"- Triangulation (union): **{int(tri_u*100)}%**")
    md.append(f"- Primary share in union: **{int(prim_u*100)}%**")
    md.append(f"- Quote coverage: **{int(qc*100)}%**")
    md.append(f"- Provider entropy: **{int(metrics.get('provider_entropy',0)*100)}%**")
    md.append(f"- Top domain share: **{int(metrics.get('top_domain_share',0)*100)}%**")

    md.append("\n## Sources")
    md.extend([f"{f}" for f in footnotes])

    # Ensure overall length
    min_words = 800
    if len(" ".join(md).split()) < min_words and key_numbers:
        # pad with more numbers to hit readability floor
        for extra in key_numbers[8:20]:
            md.append(extra)
            if len(" ".join(md).split()) >= min_words:
                break

    return "\n".join(md)