"""
Query Planning Module - PE-Grade Input Processing

Extracts time constraints, geographic entities, and key entities from user queries
to optimize provider-specific searches and improve recall/precision.
"""

from __future__ import annotations
import re
import datetime as dt
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple

# Robust year extraction patterns
YEAR = re.compile(r"\b(19|20)\d{2}\b")
RANGE = re.compile(r"\b(19|20)\d{2}\s*[-–]\s*(19|20)\d{2}\b")
MONTH_YEAR = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(19|20)\d{2}\b", re.IGNORECASE)
QUARTER = re.compile(r"\b[Q][1-4]\s+(19|20)\d{2}\b", re.IGNORECASE)

# Common geographic entities (expandable)
GEO_ENTITIES = [
    "united states", "us", "usa", "america",
    "europe", "eu", "european union", "eurozone",
    "china", "india", "japan", "germany", "uk", "united kingdom", "britain",
    "canada", "brazil", "mexico", "argentina",
    "middle east", "africa", "asia", "apac", "emea", "latam",
    "australia", "new zealand", "oceania",
    "france", "italy", "spain", "netherlands", "belgium",
    "russia", "ukraine", "poland", "turkey",
    "south korea", "singapore", "indonesia", "thailand", "vietnam",
    "saudi arabia", "uae", "israel", "egypt", "south africa", "nigeria",
    "oecd", "g7", "g20", "brics", "asean", "nafta", "opec"
]

# Common organizations and institutions (expandable)
ORG_PATTERNS = [
    r"\b(World\s+Bank|IMF|UN|WHO|WTO|OECD|ECB|Fed|Federal\s+Reserve)\b",
    r"\b(Google|Microsoft|Apple|Amazon|Meta|Facebook|Tesla|OpenAI|Anthropic)\b",
    r"\b(NYSE|NASDAQ|S&P|Dow\s+Jones|FTSE|DAX|Nikkei|Shanghai\s+Composite)\b",
    r"\b(Harvard|MIT|Stanford|Oxford|Cambridge|Yale|Princeton)\b",
    r"\b(NASA|ESA|CERN|NIH|CDC|FDA|EPA|IPCC|IAEA)\b"
]

@dataclass(frozen=True)
class QueryConstraints:
    """Extracted constraints from user query"""
    years: Tuple[Optional[int], Optional[int]]  # (start, end)
    geos: List[str]  # normalized country/region names
    entities: List[str]  # organizations, products, actors
    time_expressions: List[str]  # raw time expressions found
    
    def has_time_constraint(self) -> bool:
        return self.years[0] is not None or self.years[1] is not None
    
    def has_geo_constraint(self) -> bool:
        return len(self.geos) > 0
    
    def has_entity_constraint(self) -> bool:
        return len(self.entities) > 0

@dataclass(frozen=True)
class QueryIntent:
    """Decomposed query intent"""
    primary_intent: str  # main question/topic
    facets: Dict[str, str]  # who/what/where/when/why/how decomposition
    question_type: str  # factual/comparative/causal/predictive/evaluative
    
def _extract_years(q: str) -> Tuple[Optional[int], Optional[int]]:
    """Extract year or year range from query"""
    # Check for explicit ranges first
    m = RANGE.search(q)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return (min(a, b), max(a, b))
    
    # Check for quarter expressions
    qm = QUARTER.search(q)
    if qm:
        year = int(qm.group(1))
        return (year, year)
    
    # Check for month-year expressions
    mm = MONTH_YEAR.search(q)
    if mm:
        year = int(mm.group(2))
        return (year, year)
    
    # Find all standalone years
    ys = [int(y) for y in YEAR.findall(q)]
    if ys:
        # If multiple years, treat as range
        if len(ys) > 1:
            return (min(ys), max(ys))
        return (ys[0], ys[0])
    
    # Check for relative time expressions
    lower_q = q.lower()
    current_year = dt.datetime.now().year
    
    if "last year" in lower_q:
        return (current_year - 1, current_year - 1)
    elif "this year" in lower_q or "current year" in lower_q:
        return (current_year, current_year)
    elif "next year" in lower_q:
        return (current_year + 1, current_year + 1)
    elif "last decade" in lower_q:
        return (current_year - 10, current_year)
    elif "past 5 years" in lower_q or "last 5 years" in lower_q:
        return (current_year - 5, current_year)
    elif "past 3 years" in lower_q or "last 3 years" in lower_q:
        return (current_year - 3, current_year)
    elif "recent" in lower_q or "latest" in lower_q:
        return (current_year - 2, current_year)
    
    return (None, None)

def _extract_geos(q: str) -> List[str]:
    """Extract geographic entities from query"""
    lower_q = q.lower()
    found_geos = []
    
    for geo in GEO_ENTITIES:
        # Use word boundaries for more precise matching
        pattern = r"\b" + re.escape(geo) + r"\b"
        if re.search(pattern, lower_q):
            # Normalize to canonical form
            if geo in ["us", "usa", "america"]:
                found_geos.append("united states")
            elif geo in ["uk", "britain"]:
                found_geos.append("united kingdom")
            elif geo in ["eu", "european union", "eurozone"]:
                found_geos.append("europe")
            else:
                found_geos.append(geo)
    
    # Deduplicate while preserving order
    seen = set()
    unique_geos = []
    for g in found_geos:
        if g not in seen:
            seen.add(g)
            unique_geos.append(g)
    
    return unique_geos

def _extract_entities(q: str) -> List[str]:
    """Extract organizational and named entities from query"""
    entities = []
    
    # Check for known organization patterns
    for pattern in ORG_PATTERNS:
        matches = re.findall(pattern, q, re.IGNORECASE)
        entities.extend(matches)
    
    # Extract capitalized multi-word entities (proper nouns)
    # Pattern: consecutive capitalized words
    cap_pattern = r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b"
    cap_entities = re.findall(cap_pattern, q)
    entities.extend(cap_entities)
    
    # Extract acronyms (2-5 uppercase letters)
    acronym_pattern = r"\b[A-Z]{2,5}\b"
    acronyms = re.findall(acronym_pattern, q)
    # Filter out common words that might be in caps
    acronyms = [a for a in acronyms if a not in ["THE", "AND", "FOR", "WITH", "FROM", "INTO"]]
    entities.extend(acronyms)
    
    # Deduplicate and clean
    seen = set()
    unique_entities = []
    for e in entities:
        e_clean = e.strip()
        e_lower = e_clean.lower()
        if e_lower not in seen and len(e_clean) > 1:
            seen.add(e_lower)
            unique_entities.append(e_clean)
    
    return unique_entities

def parse_constraints(user_query: str) -> QueryConstraints:
    """Parse query to extract all constraints"""
    start, end = _extract_years(user_query)
    geos = _extract_geos(user_query)
    entities = _extract_entities(user_query)
    
    # Extract raw time expressions for transparency
    time_expressions = []
    for pattern in [YEAR, RANGE, MONTH_YEAR, QUARTER]:
        matches = pattern.findall(user_query)
        time_expressions.extend([str(m) for m in matches])
    
    return QueryConstraints(
        years=(start, end),
        geos=geos,
        entities=entities,
        time_expressions=time_expressions
    )

def decompose_intent(user_query: str) -> QueryIntent:
    """Decompose query into intent facets"""
    lower_q = user_query.lower()
    
    # Determine question type
    if any(word in lower_q for word in ["compare", "versus", "vs", "difference between"]):
        question_type = "comparative"
    elif any(word in lower_q for word in ["why", "cause", "reason", "because", "due to"]):
        question_type = "causal"
    elif any(word in lower_q for word in ["will", "forecast", "predict", "future", "outlook", "projection"]):
        question_type = "predictive"
    elif any(word in lower_q for word in ["evaluate", "assess", "impact", "effect", "implication"]):
        question_type = "evaluative"
    else:
        question_type = "factual"
    
    # Extract facets (5W1H)
    facets = {}
    
    # WHO - actors/entities
    who_pattern = r"(?:who|which\s+(?:company|organization|country|person|group))"
    who_match = re.search(who_pattern, lower_q, re.IGNORECASE)
    if who_match:
        facets["who"] = user_query[who_match.start():min(who_match.end() + 50, len(user_query))]
    
    # WHAT - subject matter
    what_pattern = r"(?:what|which)\s+(?:is|are|was|were)?\s*([^?,.\n]+)"
    what_match = re.search(what_pattern, lower_q, re.IGNORECASE)
    if what_match:
        facets["what"] = what_match.group(1).strip()
    
    # WHERE - location context
    constraints = parse_constraints(user_query)
    if constraints.geos:
        facets["where"] = ", ".join(constraints.geos)
    
    # WHEN - temporal context
    if constraints.has_time_constraint():
        facets["when"] = render_time_band(constraints)
    
    # WHY - causal/reasoning
    why_pattern = r"(?:why|reason|cause)\s+(?:is|are|was|were|does|do|did)?\s*([^?,.\n]+)"
    why_match = re.search(why_pattern, lower_q, re.IGNORECASE)
    if why_match:
        facets["why"] = why_match.group(1).strip()
    
    # HOW - mechanism/process
    how_pattern = r"(?:how|method|process|mechanism)\s+(?:is|are|was|were|does|do|did)?\s*([^?,.\n]+)"
    how_match = re.search(how_pattern, lower_q, re.IGNORECASE)
    if how_match:
        facets["how"] = how_match.group(1).strip()
    
    return QueryIntent(
        primary_intent=user_query,
        facets=facets,
        question_type=question_type
    )

def render_time_band(c: QueryConstraints) -> str:
    """Render time constraint as search-friendly string"""
    s, e = c.years
    if s and e and s != e:
        return f"{s}..{e}"
    if s:
        current = dt.datetime.now().year
        if s == current:
            return str(s)
        elif s < current:
            return f"{s}..{current}"
        else:
            return str(s)
    return ""

def render_api_date_param(c: QueryConstraints, format: str = "range") -> str:
    """Render time constraint for API parameters"""
    s, e = c.years
    if format == "range":
        # Format: "2020:2025" for World Bank style
        if s and e:
            return f"{s}:{e}"
        elif s:
            return f"{s}:{dt.datetime.now().year}"
    elif format == "after":
        # Format: "after:2020-01-01" for some APIs
        if s:
            return f"after:{s}-01-01"
    elif format == "year_list":
        # Format: "2020,2021,2022" for APIs that want explicit years
        if s and e:
            years = list(range(s, e + 1))
            return ",".join(str(y) for y in years[-5:])  # Limit to last 5 years
        elif s:
            return str(s)
    return ""

def generate_query_variants(
    base_query: str,
    constraints: QueryConstraints,
    provider: str,
    max_variants: int = 3
) -> List[str]:
    """Generate provider-specific query variants"""
    variants = []
    time_band = render_time_band(constraints)
    
    # Base query with time constraint
    if time_band:
        variants.append(f"{base_query} {time_band}")
    else:
        variants.append(base_query)
    
    # Add geographic constraints
    if constraints.geos and len(variants) < max_variants:
        geo_query = f"{base_query} {' '.join(constraints.geos[:2])}"
        if time_band:
            geo_query += f" {time_band}"
        variants.append(geo_query)
    
    # Add entity constraints
    if constraints.entities and len(variants) < max_variants:
        entity_query = f"{base_query} {' '.join(constraints.entities[:2])}"
        if time_band:
            entity_query += f" {time_band}"
        variants.append(entity_query)
    
    # Provider-specific enhancements
    if provider in ["brave", "serpapi", "serper"]:
        # Add filetype variant for web search
        if len(variants) < max_variants and "pdf" not in base_query.lower():
            pdf_variant = f"{variants[0]} filetype:pdf"
            variants.append(pdf_variant)
    
    # Deduplicate while preserving order
    seen = set()
    unique_variants = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique_variants.append(v)
    
    return unique_variants[:max_variants]

def suggest_related_queries(
    user_query: str,
    intent: QueryIntent,
    constraints: QueryConstraints,
    max_queries: int = 5
) -> List[Tuple[str, str]]:
    """Suggest related queries based on intent and constraints"""
    related = []
    
    # Add temporal variants if no time constraint exists
    if not constraints.has_time_constraint():
        current_year = dt.datetime.now().year
        related.append(("recent", f"{user_query} {current_year - 1}..{current_year}"))
        related.append(("historical", f"{user_query} {current_year - 5}..{current_year - 1}"))
    
    # Add geographic variants if no geo constraint exists
    if not constraints.has_geo_constraint():
        related.append(("global", f"{user_query} global worldwide"))
        related.append(("regional", f"{user_query} united states europe asia"))
    
    # Add comparative variants for appropriate question types
    if intent.question_type in ["factual", "evaluative"]:
        related.append(("comparative", f"{user_query} comparison benchmark"))
    
    # Add causal/impact variants
    if intent.question_type != "causal":
        related.append(("impact", f"{user_query} impact effect implications"))
    
    # Add outlook/future variant
    if intent.question_type != "predictive":
        related.append(("outlook", f"{user_query} forecast outlook future trends"))
    
    return related[:max_queries]

def create_query_plan(user_query: str) -> Dict:
    """Create comprehensive query plan from user input"""
    constraints = parse_constraints(user_query)
    intent = decompose_intent(user_query)
    
    plan = {
        "original_query": user_query,
        "constraints": {
            "time": {
                "years": constraints.years,
                "expressions": constraints.time_expressions,
                "band": render_time_band(constraints)
            },
            "geo": constraints.geos,
            "entities": constraints.entities
        },
        "intent": {
            "type": intent.question_type,
            "facets": intent.facets
        },
        "suggested_variants": {},
        "related_queries": suggest_related_queries(user_query, intent, constraints)
    }
    
    # Generate provider-specific variants (sample)
    for provider in ["brave", "worldbank", "oecd"]:
        plan["suggested_variants"][provider] = generate_query_variants(
            user_query, constraints, provider
        )
    
    return plan