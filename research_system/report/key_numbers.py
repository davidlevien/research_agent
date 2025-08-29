"""Structured Key Numbers extraction with units, labels, and source weighting."""

import math
import re
import statistics
from collections import defaultdict, Counter
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Any
import logging

logger = logging.getLogger(__name__)

# Comprehensive numeric pattern matching
_NUM_PAT = re.compile(
    r"""(?P<raw>
        (?:[$€£¥]\s*)?\d{1,3}(?:,\d{3})*(?:\.\d+)?      # 1,234 or 1,234.56 or $1,234
        | \d+(?:\.\d+)?\s*%                             # 12.3%
        | \d+(?:\.\d+)?\s*(?:pp|ppt|bps)               # 2.5pp, 25bps
        | \b\d+(?:\.\d+)?\b                             # plain numbers
    )""",
    re.VERBOSE
)

# Unit hint patterns for context labeling
_UNIT_HINTS = [
    "%", "percentage", "percent", "pct",
    "$", "USD", "dollar", "dollars", "€", "EUR", "£", "GBP", "¥", "CNY",
    "pp", "ppt", "percentage-point", "percentage points",
    "bps", "basis points", "basis point",
    "years", "year", "y", "qoq", "yoy", "mom",
    "rate", "bracket", "tax rate", "gini", "share", "ratio",
    "million", "billion", "trillion", "thousand",
    "GDP", "CPI", "inflation", "unemployment", "growth"
]

# Context keywords for better labeling
_CONTEXT_KEYWORDS = [
    "marginal", "effective", "corporate", "income", "sales", "property", "estate",
    "top", "bottom", "highest", "lowest", "average", "median", "mean",
    "federal", "state", "local", "municipal", "national", "global",
    "2024", "2023", "2025", "current", "latest", "recent"
]

@dataclass
class KeyNumber:
    """Structured representation of a key number with full context."""
    value: float
    display: str      # Formatted display value (e.g., "37.5%")
    unit: str         # Unit type ("%", "$", "pp", etc.)
    label: str        # Descriptive label from context
    source: str       # Source domain
    url: str          # Source URL
    year: Optional[str]  # Year if available
    quote_span: str   # Original quote containing the number
    confidence: float # Confidence score for this number

def _norm_money(token: str) -> Tuple[float, str]:
    """Normalize monetary values."""
    s = token.replace(",", "").strip()
    
    # Detect currency symbols
    if s.startswith("$"):
        unit = "$"
        s = s[1:].strip()
    elif s.startswith("€"):
        unit = "€"
        s = s[1:].strip()
    elif s.startswith("£"):
        unit = "£"
        s = s[1:].strip()
    elif s.startswith("¥"):
        unit = "¥"
        s = s[1:].strip()
    else:
        unit = "$"  # Default assumption
    
    try:
        return float(s), unit
    except ValueError:
        return math.nan, unit

def _norm_percent(token: str) -> Tuple[float, str]:
    """Normalize percentage values."""
    s = token.strip()
    
    if s.endswith("%"):
        unit = "%"
        s = s[:-1].strip()
    elif s.endswith(("pp", "ppt")):
        unit = "pp"
        s = s[:-2].strip() if s.endswith("pp") else s[:-3].strip()
    elif s.endswith("bps"):
        unit = "bps"
        s = s[:-3].strip()
        # Convert basis points to percentage
        try:
            value = float(s) / 100
            return value, "%" 
        except ValueError:
            return math.nan, "bps"
    else:
        unit = "%"  # Default assumption for bare numbers
    
    try:
        return float(s), unit
    except ValueError:
        return math.nan, unit

def _canonicalize_unit(token: str) -> Tuple[float, str]:
    """Convert various numeric representations to canonical form."""
    token = token.strip()
    
    # Handle percentages, basis points, percentage points
    if any(token.endswith(x) for x in ["%", "pp", "ppt", "bps"]):
        return _norm_percent(token)
    
    # Handle currency
    if token.startswith(("$", "€", "£", "¥")):
        return _norm_money(token)
    
    # Handle numbers with commas (likely money)
    if "," in token and token.replace(",", "").replace(".", "").isdigit():
        val, unit = _norm_money("$" + token)  # Assume dollar
        return val, "$"
    
    # Plain number
    try:
        return float(token.replace(",", "")), ""
    except ValueError:
        return math.nan, ""

def _build_label_from_context(text: str, number_pos: int) -> str:
    """Build a descriptive label from surrounding context."""
    # Extract window around the number
    start = max(0, number_pos - 100)
    end = min(len(text), number_pos + 100)
    window = text[start:end].lower()
    
    # Find relevant keywords
    found_hints = [hint for hint in _UNIT_HINTS if hint in window]
    found_context = [kw for kw in _CONTEXT_KEYWORDS if kw in window]
    
    # Build label from found keywords
    label_parts = []
    
    # Add the most specific context first
    if found_context:
        label_parts.extend(found_context[:2])
    
    # Add unit hints
    if found_hints:
        label_parts.extend(found_hints[:2])
    
    # If no specific context found, look for capitalized words
    if not label_parts:
        caps = re.findall(r'\b[A-Z][A-Za-z-]{2,}\b', text[start:end])
        if caps:
            label_parts.extend(caps[:2])
    
    # Construct final label
    if label_parts:
        return ", ".join(sorted(set(label_parts))[:3])
    else:
        return "figure"

def _get_domain_priority(domain: str) -> float:
    """Get priority score for different domain types."""
    domain = domain.lower()
    
    # Tier 1: Official statistics, government, international orgs
    if any(d in domain for d in [
        "oecd.org", "imf.org", "worldbank.org", "treasury.gov", "irs.gov",
        "bls.gov", "bea.gov", "census.gov", "cbo.gov", "europa.eu", "ecb.europa.eu"
    ]):
        return 1.0
    
    # Tier 2: Academic, working papers, national statistics
    if any(d in domain for d in [
        ".edu", "nber.org", "ssrn.com", "arxiv.org", ".gov"
    ]):
        return 0.8
    
    # Tier 3: Think tanks, curated data
    if any(d in domain for d in [
        "brookings.edu", "urban.org", "taxfoundation.org", 
        "ourworldindata.org", "cbpp.org"
    ]):
        return 0.6
    
    # Tier 4: Media, other
    return 0.3

def _extract_key_numbers(cards: List[Any], max_items: int = 6) -> List[KeyNumber]:
    """Extract structured, de-duplicated numbers with labels, units, and sources."""
    candidates: List[KeyNumber] = []
    
    for card in cards:
        # Get text content
        text_fields = [
            getattr(card, "quote", "") or "",
            getattr(card, "snippet", "") or "",
            getattr(card, "supporting_text", "") or "",
            getattr(card, "text", "") or ""
        ]
        
        # Combine and limit text length
        full_text = " ".join(field for field in text_fields if field)[:1000]
        if not full_text.strip():
            continue
        
        # Get card metadata
        domain = getattr(card, "source_domain", "") or getattr(card, "domain", "") or "unknown"
        url = getattr(card, "url", "") or ""
        year = getattr(card, "year", None) or getattr(card, "publication_year", None)
        
        # Find numeric tokens
        for match in _NUM_PAT.finditer(full_text):
            token = match.group("raw")
            value, unit = _canonicalize_unit(token)
            
            if math.isnan(value):
                continue
            
            # Skip extremely large or small values that are likely errors
            if value > 1e10 or (value > 0 and value < 1e-6):
                continue
            
            # Build label from context
            match_pos = match.start()
            label = _build_label_from_context(full_text, match_pos)
            
            # Extract quote span around the number
            span_start = max(0, match_pos - 80)
            span_end = min(len(full_text), match_pos + 80)
            quote_span = full_text[span_start:span_end].strip()
            
            # Format display value
            if unit == "%":
                display = f"{value:.1f}%" if value != int(value) else f"{int(value)}%"
            elif unit in ["$", "€", "£", "¥"]:
                if value >= 1000000000:
                    display = f"{unit}{value/1000000000:.1f}B"
                elif value >= 1000000:
                    display = f"{unit}{value/1000000:.1f}M"
                elif value >= 1000:
                    display = f"{unit}{value/1000:.0f}K" if value >= 10000 else f"{unit}{value:,.0f}"
                else:
                    display = f"{unit}{value:g}"
            elif unit == "pp":
                display = f"{value:.1f}pp"
            elif unit == "bps":
                display = f"{value:.0f}bps"
            else:
                display = f"{value:g}"
            
            # Create full label with year if available
            year_str = str(year) if year else None
            if year_str and year_str not in label:
                label_with_year = f"{label} ({year_str})"
            else:
                label_with_year = label
            
            # Calculate confidence score
            confidence = (
                _get_domain_priority(domain) * 0.6 +
                (0.2 if unit in ["%", "$"] else 0.1) +
                (0.2 if len(quote_span) > 50 else 0.1)
            )
            
            candidates.append(KeyNumber(
                value=value,
                display=display,
                unit=unit,
                label=label_with_year,
                source=domain,
                url=url,
                year=year_str,
                quote_span=quote_span,
                confidence=confidence
            ))
    
    if not candidates:
        return []
    
    # Group by similar values and deduplicate
    buckets = defaultdict(list)
    for kn in candidates:
        # Group by rounded value, unit, and canonical label
        canonical_label = re.sub(r'\s+', ' ', kn.label.lower().strip())
        key = (round(kn.value, 3), kn.unit, canonical_label)
        buckets[key].append(kn)
    
    # Select best representatives from each bucket
    aggregated = []
    for key, items in buckets.items():
        if not items:
            continue
        
        # Score each item and select the best
        best_item = max(items, key=lambda x: x.confidence)
        
        # Calculate aggregate score for this bucket
        sources = {item.source for item in items}
        avg_confidence = statistics.mean(item.confidence for item in items)
        diversity_bonus = 0.1 * len(sources)
        
        final_score = avg_confidence + diversity_bonus
        
        aggregated.append((final_score, best_item, items))
    
    # Sort by score and return top items
    aggregated.sort(key=lambda x: x[0], reverse=True)
    
    results = []
    for score, best_item, all_items in aggregated[:max_items]:
        # Get top sources for citation
        top_sources = sorted(all_items, key=lambda x: x.confidence, reverse=True)[:2]
        source_list = [item.source for item in top_sources]
        url_list = [item.url for item in top_sources if item.url]
        
        # Update the best item with aggregated source info
        best_item.source = ", ".join(source_list)
        results.append(best_item)
    
    return results

def compose_key_numbers_section(cards: List[Any], max_numbers: int = 6) -> str:
    """Compose a structured Key Numbers section with proper units and citations."""
    try:
        key_numbers = _extract_key_numbers(cards, max_items=max_numbers)
        
        if not key_numbers:
            return "No quantitative figures with sufficient reliability were identified."
        
        # Format as structured bullets
        lines = []
        for kn in key_numbers:
            # Create bullet with number, label, and source
            source_text = f"*({kn.source})*" if kn.source and kn.source != "unknown" else ""
            line = f"- **{kn.display}** — {kn.label} {source_text}"
            lines.append(line)
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Error in compose_key_numbers_section: {e}")
        return "Error extracting key numbers."

def validate_key_numbers_quality(cards: List[Any]) -> Dict[str, Any]:
    """Validate the quality of extracted key numbers for testing."""
    try:
        key_numbers = _extract_key_numbers(cards, max_items=10)
        
        return {
            "total_numbers": len(key_numbers),
            "has_units": sum(1 for kn in key_numbers if kn.unit),
            "has_labels": sum(1 for kn in key_numbers if kn.label != "figure"),
            "has_sources": sum(1 for kn in key_numbers if kn.source != "unknown"),
            "avg_confidence": statistics.mean(kn.confidence for kn in key_numbers) if key_numbers else 0,
            "unit_distribution": Counter(kn.unit for kn in key_numbers),
            "sample_numbers": [
                {
                    "display": kn.display,
                    "label": kn.label,
                    "unit": kn.unit,
                    "source": kn.source
                }
                for kn in key_numbers[:3]
            ]
        }
    except Exception as e:
        logger.error(f"Error in validate_key_numbers_quality: {e}")
        return {"error": str(e)}