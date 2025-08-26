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

HTML_TAG = re.compile(r"<[^>]+>")

def _clean(s: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    s = HTML_TAG.sub("", s or "")
    s = " ".join(s.split())
    return s

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

def compose_findings(
    cards: List[Any], 
    para_clusters: List[Dict], 
    struct_tris: List[Dict],
    topic: str = ""
) -> str:
    """
    Compose findings section with triangulated claims first.
    Returns markdown-formatted findings.
    """
    findings = []
    used_indices = set()
    
    # Check if this is a CDC-related topic
    is_cdc_topic = "cdc" in topic.lower()
    
    # 1. Triangulated structured claims (highest priority)
    for tri in struct_tris:
        if len(set(tri.get("domains", []))) < 2:
            continue
        claim = _clean(tri.get("representative_claim", ""))
        
        # Filter for CDC relevance if needed
        if is_cdc_topic and not any(term.lower() in claim.lower() for term in CDC_POLICY_TERMS):
            continue
            
        if not has_numeric_and_period(claim):
            continue
        indices = tri.get("indices", [])
        if any(i in used_indices for i in indices):
            continue
        srcs = [cards[i] for i in indices]
        findings.append(render_finding(claim, tri.get("domains", []), srcs, "Triangulated"))
        used_indices.update(indices)
        if len(findings) >= 10:
            break
    
    # 2. Triangulated paraphrase clusters  
    if len(findings) < 10:
        for cluster in para_clusters:
            if len(set(cluster.get("domains", []))) < 2:
                continue
            claim = _clean(cluster.get("representative_claim", ""))
            
            # Filter for CDC relevance if needed
            if is_cdc_topic and not any(term.lower() in claim.lower() for term in CDC_POLICY_TERMS):
                continue
                
            if not has_numeric_and_period(claim):
                continue
            indices = cluster.get("indices", [])
            if any(i in used_indices for i in indices):
                continue
            srcs = [cards[i] for i in indices]
            findings.append(render_finding(claim, cluster.get("domains", []), srcs, "Triangulated"))
            used_indices.update(indices)
            if len(findings) >= 10:
                break
    
    # 3. Backfill with single-source primaries
    if len(findings) < 6:
        primaries = [
            c for c in cards 
            if c.source_domain in PRIMARY 
            and c.quote_span 
            and has_numeric_and_period(c.quote_span)
        ]
        # Sort by credibility
        primaries.sort(key=lambda c: c.credibility_score, reverse=True)
        
        for c in primaries:
            if cards.index(c) in used_indices:
                continue
            findings.append(render_finding(
                c.quote_span, 
                [c.source_domain], 
                [c], 
                "Single-source"
            ))
            used_indices.add(cards.index(c))
            if len(findings) >= 6:
                break
    
    return "\n".join(findings)

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