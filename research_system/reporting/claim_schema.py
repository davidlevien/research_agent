"""Strict claim schema for validated findings and numbers."""

from dataclasses import dataclass, field
from typing import List, Optional, Set
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class ClaimType(Enum):
    """Type of claim for proper categorization."""
    NUMERIC_MEASURE = "numeric_measure"      # Statistical measurement with units
    MECHANISM_OR_THEORY = "mechanism_or_theory"  # Causal explanation
    OPINION_ADVOCACY = "opinion_advocacy"    # Opinion or advocacy position
    NEWS_CONTEXT = "news_context"            # News or current events


class SourceClass(Enum):
    """Classification of source credibility."""
    OFFICIAL_STATS = "official_stats"  # IRS, OECD, IMF, Treasury, Eurostat, CBO
    PEER_REVIEW = "peer_review"        # Academic journals
    GOV_MEMO = "gov_memo"              # Government reports/memos
    THINK_TANK = "think_tank"          # Think tank reports
    MEDIA = "media"                    # News media
    BLOG = "blog"                      # Blogs and opinion pieces


class PartisanTag(Enum):
    """Political alignment of source."""
    NEUTRAL = "neutral"
    ADVOCACY = "advocacy"
    PARTISAN_LEFT = "partisan_left"
    PARTISAN_RIGHT = "partisan_right"
    UNKNOWN = "unknown"


@dataclass
class SourceRecord:
    """Validated source for a claim."""
    url: str
    domain: str
    title: str
    source_class: SourceClass
    credibility_score: float = 0.5
    is_primary: bool = False
    
    def is_credible(self) -> bool:
        """Check if source meets credibility threshold."""
        return (
            self.source_class in [SourceClass.OFFICIAL_STATS, SourceClass.PEER_REVIEW] or
            self.credibility_score >= 0.7
        )


@dataclass
class Claim:
    """Structured claim with strict validation."""
    subject: str               # e.g., "US top 1% households"
    metric: str                # e.g., "effective federal tax rate"
    value: Optional[float]     # Numeric value
    unit: str                  # "%", "pp", "USD", etc.
    geo: str                   # "US", "OECD", "CA", ...
    time: str                  # "2023", "2010-2020"
    definition: str            # How the metric is defined
    sources: List[SourceRecord] = field(default_factory=list)
    triangulated: bool = False  # >=2 independent, non-derivative sources
    partisan_tag: PartisanTag = PartisanTag.UNKNOWN
    claim_type: ClaimType = ClaimType.NUMERIC_MEASURE
    confidence: float = 0.0
    
    def __post_init__(self):
        """Validate claim on initialization."""
        # Auto-detect triangulation
        if len(self.sources) >= 2:
            unique_domains = set(s.domain for s in self.sources)
            if len(unique_domains) >= 2:
                self.triangulated = True
        
        # Auto-detect partisan tag from sources
        if self.partisan_tag == PartisanTag.UNKNOWN:
            self._detect_partisan_tag()
        
        # Calculate confidence
        self._calculate_confidence()
    
    def _detect_partisan_tag(self):
        """Detect partisan alignment from sources."""
        # Known partisan domains (simplified - should be expanded)
        LEFT_DOMAINS = {"americanprogress.org", "epi.org", "cbpp.org"}
        RIGHT_DOMAINS = {"heritage.org", "aei.org", "cato.org"}
        
        domains = {s.domain for s in self.sources}
        
        has_left = bool(domains & LEFT_DOMAINS)
        has_right = bool(domains & RIGHT_DOMAINS)
        
        if has_left and has_right:
            self.partisan_tag = PartisanTag.ADVOCACY  # Mixed advocacy
        elif has_left:
            self.partisan_tag = PartisanTag.PARTISAN_LEFT
        elif has_right:
            self.partisan_tag = PartisanTag.PARTISAN_RIGHT
        elif any(s.source_class == SourceClass.OFFICIAL_STATS for s in self.sources):
            self.partisan_tag = PartisanTag.NEUTRAL
        else:
            self.partisan_tag = PartisanTag.UNKNOWN
    
    def _calculate_confidence(self):
        """Calculate confidence score for claim."""
        score = 0.0
        
        # Base score from triangulation
        if self.triangulated:
            score += 0.4
        
        # Add for official sources
        official_count = sum(1 for s in self.sources 
                           if s.source_class == SourceClass.OFFICIAL_STATS)
        score += min(0.3, official_count * 0.15)
        
        # Add for peer review
        peer_count = sum(1 for s in self.sources 
                        if s.source_class == SourceClass.PEER_REVIEW)
        score += min(0.2, peer_count * 0.1)
        
        # Add for high credibility
        high_cred_count = sum(1 for s in self.sources if s.credibility_score >= 0.8)
        score += min(0.1, high_cred_count * 0.05)
        
        self.confidence = min(1.0, score)


def is_publishable_finding(c: Claim) -> bool:
    """
    Check if a claim meets standards for publication as a key finding.
    
    Args:
        c: Claim to validate
        
    Returns:
        True if claim meets all publication standards
    """
    # Must be triangulated
    if not c.triangulated:
        logger.debug(f"Claim rejected: not triangulated - {c.metric}")
        return False
    
    # Must have a value (0 is valid)
    if c.value is None:
        logger.debug(f"Claim rejected: no value - {c.metric}")
        return False
    
    # Must have geography and time
    if not c.geo or not c.time:
        logger.debug(f"Claim rejected: missing geo/time - {c.metric}")
        return False
    
    # Must be neutral or have balanced sources
    if c.partisan_tag not in [PartisanTag.NEUTRAL, PartisanTag.ADVOCACY]:
        # Advocacy is OK if it has official sources too
        has_official = any(s.source_class == SourceClass.OFFICIAL_STATS 
                          for s in c.sources)
        if not has_official:
            logger.debug(f"Claim rejected: partisan without official source - {c.metric}")
            return False
    
    # Must have minimum confidence
    if c.confidence < 0.5:
        logger.debug(f"Claim rejected: low confidence {c.confidence:.2f} - {c.metric}")
        return False
    
    # For numeric claims, must have proper units
    if c.claim_type == ClaimType.NUMERIC_MEASURE:
        valid_units = {"%", "pp", "USD", "$", "€", "£", "ratio", "index", "per capita"}
        if c.unit not in valid_units and not c.unit.endswith("/year"):
            logger.debug(f"Claim rejected: invalid unit '{c.unit}' - {c.metric}")
            return False
    
    return True


def is_publishable_number(c: Claim) -> bool:
    """
    Check if a claim qualifies for the Key Numbers section.
    
    Stricter than is_publishable_finding - requires numeric measure with clear units.
    """
    if not is_publishable_finding(c):
        return False
    
    # Must be numeric measure
    if c.claim_type != ClaimType.NUMERIC_MEASURE:
        return False
    
    # Must have year in time field
    year_pattern = r'\b(19|20)\d{2}\b'
    if not re.search(year_pattern, c.time):
        logger.debug(f"Number rejected: no year in time '{c.time}' - {c.metric}")
        return False
    
    # Must have at least one primary source
    if not any(s.is_primary for s in c.sources):
        logger.debug(f"Number rejected: no primary source - {c.metric}")
        return False
    
    return True


def extract_claims_from_cards(cards: List, topic: str) -> List[Claim]:
    """
    Extract structured claims from evidence cards.
    
    Args:
        cards: List of EvidenceCard objects
        topic: Research topic for context
        
    Returns:
        List of validated Claim objects
    """
    claims = []
    
    for card in cards:
        # Skip cards without proper content
        if not getattr(card, 'claim', None) and not getattr(card, 'snippet', None):
            continue
        
        # Try to extract structured information
        text = card.claim or card.snippet or ""
        
        # Pattern matching for numeric claims
        numeric_pattern = r'(\d+(?:\.\d+)?)\s*(%|percent|pp|USD|\$|€)'
        matches = re.findall(numeric_pattern, text)
        
        if matches:
            for value_str, unit in matches:
                try:
                    value = float(value_str)
                    
                    # Create source record
                    source = SourceRecord(
                        url=card.url,
                        domain=card.source_domain,
                        title=card.title or "",
                        source_class=classify_source(card.source_domain),
                        credibility_score=getattr(card, 'credibility_score', 0.5),
                        is_primary=getattr(card, 'is_primary_source', False)
                    )
                    
                    # Extract context (simplified - should use NLP)
                    claim = Claim(
                        subject=extract_subject(text, value_str),
                        metric=extract_metric(text, value_str),
                        value=value,
                        unit=normalize_unit(unit),
                        geo=extract_geo(text) or "Unknown",
                        time=extract_time(text) or "Unknown",
                        definition="",  # Would need more context
                        sources=[source],
                        claim_type=ClaimType.NUMERIC_MEASURE
                    )
                    
                    claims.append(claim)
                    
                except (ValueError, AttributeError) as e:
                    logger.debug(f"Failed to extract claim from card: {e}")
                    continue
    
    # Merge similar claims
    merged = merge_similar_claims(claims)
    
    return merged


def classify_source(domain: str) -> SourceClass:
    """Classify a domain into source classes."""
    domain = domain.lower()
    
    # Official statistics sources
    OFFICIAL_DOMAINS = {
        "irs.gov", "treasury.gov", "cbo.gov", "bls.gov", "census.gov",
        "oecd.org", "imf.org", "worldbank.org", "europa.eu", "eurostat.ec.europa.eu",
        "statistics.gov.uk", "stats.govt.nz", "abs.gov.au"
    }
    
    # Academic domains
    ACADEMIC_PATTERNS = [".edu", "arxiv.org", "ssrn.com", "nber.org"]
    
    # Government domains
    GOV_PATTERNS = [".gov", ".gov.uk", ".gc.ca", ".gov.au"]
    
    # Think tanks
    THINK_TANKS = {
        "brookings.edu", "rand.org", "urban.org", "aei.org", "heritage.org",
        "cato.org", "cbpp.org", "epi.org", "americanprogress.org"
    }
    
    # Check classifications
    if domain in OFFICIAL_DOMAINS:
        return SourceClass.OFFICIAL_STATS
    
    if any(pattern in domain for pattern in ACADEMIC_PATTERNS):
        return SourceClass.PEER_REVIEW
    
    if domain in THINK_TANKS:
        return SourceClass.THINK_TANK
    
    if any(pattern in domain for pattern in GOV_PATTERNS):
        return SourceClass.GOV_MEMO
    
    # Default to media
    return SourceClass.MEDIA


def normalize_unit(unit: str) -> str:
    """Normalize unit strings."""
    unit = unit.strip().lower()
    
    if unit in ["percent", "%"]:
        return "%"
    if unit in ["pp", "percentage points"]:
        return "pp"
    if unit in ["usd", "$", "dollars"]:
        return "USD"
    if unit in ["eur", "€", "euros"]:
        return "€"
    
    return unit


def extract_subject(text: str, value: str) -> str:
    """Extract subject from text (simplified)."""
    # This would need NLP in production
    lines = text.split(".")
    for line in lines:
        if value in line:
            # Take first noun phrase before the value
            words = line[:line.index(value)].split()[-5:]
            return " ".join(words).strip()
    return "Unknown subject"


def extract_metric(text: str, value: str) -> str:
    """Extract metric description from text (simplified)."""
    # This would need NLP in production
    keywords = ["tax rate", "income", "gdp", "growth", "unemployment", "inflation"]
    text_lower = text.lower()
    
    for keyword in keywords:
        if keyword in text_lower:
            return keyword
    
    return "metric"


def extract_geo(text: str) -> Optional[str]:
    """Extract geography from text."""
    # Common country codes and names
    GEOS = {
        "united states": "US", "u.s.": "US", "america": "US",
        "oecd": "OECD", "european union": "EU", "eurozone": "EU",
        "united kingdom": "UK", "u.k.": "UK", "britain": "UK",
        "canada": "CA", "australia": "AU", "japan": "JP"
    }
    
    text_lower = text.lower()
    for name, code in GEOS.items():
        if name in text_lower:
            return code
    
    return None


def extract_time(text: str) -> Optional[str]:
    """Extract time period from text."""
    # Look for years
    year_pattern = r'\b(19|20)\d{2}\b'
    years = re.findall(year_pattern, text)
    
    if len(years) >= 2:
        return f"{min(years)}-{max(years)}"
    elif years:
        return years[0]
    
    return None


def merge_similar_claims(claims: List[Claim]) -> List[Claim]:
    """
    Merge similar claims from different sources.
    
    Claims are merged if they have the same metric, geo, and time.
    """
    if not claims:
        return []
    
    merged = {}
    
    for claim in claims:
        # Create merge key
        key = (claim.metric, claim.geo, claim.time, claim.unit)
        
        if key in merged:
            # Merge sources
            existing = merged[key]
            existing.sources.extend(claim.sources)
            
            # Update triangulation status
            unique_domains = set(s.domain for s in existing.sources)
            if len(unique_domains) >= 2:
                existing.triangulated = True
            
            # Recalculate confidence
            existing._calculate_confidence()
            
            # Average values if different
            if existing.value and claim.value:
                existing.value = (existing.value + claim.value) / 2
        else:
            merged[key] = claim
    
    return list(merged.values())