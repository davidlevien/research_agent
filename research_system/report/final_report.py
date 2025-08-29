"""
Enhanced report composition with triangulated-first ordering
"""

import re
from typing import List, Dict, Any, Optional
from datetime import datetime

# Primary source domains
PRIMARY = {
    "unwto.org", "e-unwto.org", "iata.org", "wttc.org", 
    "oecd.org", "worldbank.org", "imf.org", "ec.europa.eu",
    "who.int", "un.org", "unesco.org", "ilo.org", "cdc.gov"
}

# CDC/Policy-specific terms for filtering
CDC_POLICY_TERMS = (
    "CDC", "Centers for Disease Control", "ACIP", "MMWR", 
    "guideline", "policy", "rule", "advisory", "recommendation",
    "regulation", "mandate", "requirement", "protocol"
)

# Safe verbs for SVO (subject-verb-object) patterns
SAFE_VERBS = ("increases", "decreases", "is associated with",
              "correlates with", "contributes to", "reduces", "raises")

# Banned advocacy phrases - moved from key_numbers for reuse
BAN_PHRASES = (
    "project 2025", "corporate welfare", "hurt the middle class",
    "tax the rich more", "fair share", "talking point", "manifesto",
    "campaign", "party platform", "press release", "op-ed"
)

HTML_TAG = re.compile(r"<[^>]+>")

def _clean(s: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    s = HTML_TAG.sub("", s or "")
    s = " ".join(s.split())
    return s

def _is_advocacy(text: str) -> bool:
    """Check if text contains advocacy language."""
    t = text.lower()
    return any(p in t for p in BAN_PHRASES)

def _svotize(text: str) -> Optional[str]:
    """Convert text to SVO format if it contains safe verbs and numbers."""
    # crude but reliable: require at least one SAFE_VERB and a number or explicit noun phrase
    t = " ".join(text.split())
    if any(v in t.lower() for v in SAFE_VERBS) and re.search(r"\d|percent|percentage|rate|ratio|index", t, re.I):
        return t
    return None

def has_numeric_and_period(s: str) -> bool:
    """Check if text contains both numbers and time periods"""
    return bool(re.search(r"\d", s or "")) and bool(
        re.search(r"\b(20\d{2}|Q[1-4]\s*20\d{2}|H[12]\s*20\d{2}|FY\s*20\d{2})\b", s or "", re.I)
    )

def md_link(text: str, url: str, maxlen: int = 80) -> str:
    """Create safe markdown link"""
    t = (text or url or "").strip().replace("[", "").replace("]", "")
    if len(t) > maxlen: 
        t = t[:maxlen-1] + "…"
    return f"[{t}]({url})"

def render_finding(claim: str, domains: List[str], sources: List[Any], label: str) -> str:
    """Render a finding with proper formatting"""
    out = [
        f"- **{claim.strip()}** _[{label}]_",
        f"  - Domains: {', '.join(sorted(set(domains)))}"
    ]
    for s in sources[:3]:  # Show up to 3 sources
        title = s.source_title or s.title or s.url
        out.append(f"    - {md_link(title, s.url)} — {s.source_domain}")
    return "\n".join(out)

def compose_findings(cards, para_clusters, struct_tris, topic: str = "") -> str:
    """
    Compose findings section with factual, SVO-structured claims.
    Prioritizes triangulated, multi-domain claims and rejects advocacy language.
    """
    ranked = []
    used = set()
    
    # prefer structured triangles first (multi-domain)
    for tri in struct_tris:
        for c in tri.get("cards", []):
            if getattr(c, "domain_count", 1) < 2:
                continue
            if _is_advocacy(c.text):
                continue
            svot = _svotize(c.text or "")
            if not svot:
                continue
            k = svot.lower()
            if k in used:
                continue
            used.add(k)
            ranked.append(("A", svot, c))
    
    # then paraphrase clusters (still multi-domain)
    for cl in para_clusters:
        for c in cl.get("cards", []):
            if _is_advocacy(c.text):
                continue
            svot = _svotize(c.text or "")
            if not svot:
                continue
            k = svot.lower()
            if k in used:
                continue
            used.add(k)
            ranked.append(("B", svot, c))

    # finally high-cred singletons only if we're starving
    if len(ranked) < 3:
        for c in cards:
            if getattr(c, "cred_score", 0.0) < 0.75:
                continue
            if _is_advocacy(c.text):
                continue
            svot = _svotize(c.text or "")
            if not svot:
                continue
            k = svot.lower()
            if k in used:
                continue
            used.add(k)
            ranked.append(("C", svot, c))

    # build markdown with inline links
    out = []
    for tier, svot, c in ranked[:6]:
        url = getattr(c, "url", "") or (getattr(c, "source", {}) or {}).get("url", "")
        dom = getattr(c, "source_domain", "") or getattr(c, "domain", "")
        src_md = f" [[source]({url}) — {dom}]" if url else ""
        out.append(f"- {svot}{src_md}")

    return "\n".join(out) if out else "- _No triangulated, factual findings passed guardrails._"

def generate_final_report(
    cards: List[Any],
    para_clusters: List[Dict],
    struct_tris: List[Dict],
    topic: str,
    providers: List[str]
) -> str:
    """
    Generate complete final report with enhanced structure.
    """
    now = datetime.utcnow().isoformat() + "Z"
    
    # Calculate topic neighborhood (simple version)
    from collections import Counter
    all_text = " ".join([c.snippet or "" for c in cards]).lower()
    words = re.findall(r'\b[a-z]{4,}\b', all_text)
    word_freq = Counter(words)
    # Filter common words and get top terms
    common = {"that", "this", "with", "from", "have", "been", "were", "their", "which", "would"}
    topic_words = [w for w, _ in word_freq.most_common(20) if w not in common][:5]
    
    # Build report
    report = f"""# Final Report: {topic}

**Generated**: {now}
**Evidence Cards**: {len(cards)}
**Providers**: {', '.join(providers)}

## Topic Neighborhood
"""
    
    for word in topic_words:
        count = sum(1 for c in cards if word in (c.snippet or "").lower())
        score = count / max(1, len(cards))
        report += f"- **{word}** — {count} sources (score: {score:.2f})\n"
    
    report += "\n## Key Findings (triangulated first)\n"
    findings = compose_findings(cards, para_clusters, struct_tris, topic)
    if findings:
        report += findings
    else:
        report += "- No triangulated findings with numeric claims and time periods found.\n"
    
    # Add controversy section if present
    controversial = [c for c in cards if c.controversy_score >= 0.3]
    if controversial:
        report += "\n## Controversial Claims\n"
        for c in controversial[:3]:
            claim = c.quote_span or c.claim or c.snippet
            report += f"- {claim[:200]}\n"
            report += f"  - Controversy score: {c.controversy_score:.2f}\n"
            if c.disputed_by:
                report += f"  - Disputed by: {len(c.disputed_by)} sources\n"
    
    # Add source quality summary
    domains = {}
    for c in cards:
        d = c.source_domain
        if d not in domains:
            domains[d] = {"count": 0, "avg_cred": 0}
        domains[d]["count"] += 1
        domains[d]["avg_cred"] += c.credibility_score
    
    report += "\n## Source Quality Summary\n"
    top_domains = sorted(domains.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
    for domain, stats in top_domains:
        avg_cred = stats["avg_cred"] / stats["count"]
        primary_marker = " 🔷" if domain in PRIMARY else ""
        report += f"- {domain}: {stats['count']} articles (credibility: {avg_cred:.2f}){primary_marker}\n"
    
    return report