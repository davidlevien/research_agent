"""Extractors for structured facts from evidence cards."""

import re
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Patterns for extraction
YEAR_RE = re.compile(r'\b(19\d{2}|20\d{2})\b')
PCT_RE = re.compile(r'(\d+(?:\.\d+)?)\s*%')
NUM_RE = re.compile(r'\b(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\b')
MONEY_RE = re.compile(r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:\s*(?:billion|million|trillion))?)')

# Metric keywords
METRIC_KEYWORDS = {
    'tax': ['tax rate', 'effective rate', 'marginal rate', 'tax burden', 'tax share'],
    'income': ['income', 'earnings', 'wages', 'compensation', 'salary'],
    'gdp': ['gdp', 'gross domestic product', 'economic growth', 'output'],
    'unemployment': ['unemployment', 'jobless', 'employment rate'],
    'inflation': ['inflation', 'cpi', 'price index', 'cost of living'],
    'debt': ['debt', 'deficit', 'borrowing', 'liabilities'],
    'trade': ['trade', 'exports', 'imports', 'balance', 'surplus'],
}

# Geography patterns
GEO_PATTERNS = {
    'US': r'\b(united states|u\.?s\.?a?|america)\b',
    'EU': r'\b(european union|eu|eurozone|europe)\b',
    'UK': r'\b(united kingdom|u\.?k\.?|britain)\b',
    'OECD': r'\b(oecd|developed countries)\b',
    'China': r'\b(china|chinese)\b',
    'Japan': r'\b(japan|japanese)\b',
    'Global': r'\b(global|worldwide|international)\b',
}

# Cohort patterns
COHORT_PATTERNS = {
    'top 1%': r'\b(top|highest|richest)\s+1\s*%',
    'top 10%': r'\b(top|highest|richest)\s+10\s*%',
    'bottom 50%': r'\b(bottom|lowest|poorest)\s+50\s*%',
    'middle class': r'\b(middle\s+class|middle\s+income)\b',
    'households': r'\b(household|family|families)\b',
    'corporations': r'\b(corporat|company|companies|business)\b',
    'all': r'\b(all|total|overall|aggregate)\b',
}


def extract_structured_fact(card: Any) -> Optional[Dict]:
    """
    Extract a structured fact from an evidence card.
    
    Very conservative: only extracts if all required fields can be found.
    
    Args:
        card: Evidence card
        
    Returns:
        Dict with structured fact data or None
    """
    # Get text content
    text = (
        getattr(card, 'claim', '') or
        getattr(card, 'snippet', '') or
        getattr(card, 'quote_span', '') or
        getattr(card, 'title', '')
    )[:1200]  # Limit length
    
    if not text:
        return None
    
    # Look for year
    year_match = YEAR_RE.search(text)
    if not year_match:
        return None
    year = int(year_match.group(1))
    
    # Look for numeric value
    value = None
    unit = ""
    
    # Try percentage first
    pct_match = PCT_RE.search(text)
    if pct_match:
        value = float(pct_match.group(1))
        unit = "%"
    else:
        # Try money
        money_match = MONEY_RE.search(text)
        if money_match:
            value_str = money_match.group(1)
            # Handle billions/millions
            if 'billion' in value_str.lower():
                value = float(re.sub(r'[^\d.]', '', value_str.split()[0])) * 1e9
                unit = "USD"
            elif 'million' in value_str.lower():
                value = float(re.sub(r'[^\d.]', '', value_str.split()[0])) * 1e6
                unit = "USD"
            elif 'trillion' in value_str.lower():
                value = float(re.sub(r'[^\d.]', '', value_str.split()[0])) * 1e12
                unit = "USD"
            else:
                value = float(re.sub(r'[^\d.]', '', value_str))
                unit = "USD"
        else:
            # Try regular number
            num_match = NUM_RE.search(text)
            if num_match:
                value = float(num_match.group(1).replace(',', ''))
                unit = ""  # No unit for plain numbers
    
    if value is None:
        return None
    
    # Extract metric
    metric = guess_metric_label(text)
    
    # Extract geography
    geography = extract_geography(text) or "US"  # Default to US
    
    # Extract cohort
    cohort = extract_cohort(text) or "all households"  # Default
    
    return {
        'metric': metric,
        'value': value,
        'unit': unit,
        'geography': geography,
        'cohort': cohort,
        'year': year,
    }


def extract_number(card: Any) -> Optional[Dict]:
    """
    Extract a simpler number fact for Key Numbers section.
    
    Args:
        card: Evidence card
        
    Returns:
        Dict with number data or None
    """
    fact = extract_structured_fact(card)
    if not fact:
        return None
    
    # Simplify for Key Numbers
    return {
        'label': fact['metric'],
        'value': fact['value'],
        'unit': fact['unit'],
        'year': fact['year'],
    }


def guess_metric_label(text: str) -> str:
    """
    Guess the metric being discussed based on keywords.
    
    Args:
        text: Text to analyze
        
    Returns:
        Best guess metric label
    """
    text_lower = text.lower()
    
    # Check each metric category
    for category, keywords in METRIC_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                # Return the most specific keyword found
                return keyword
    
    # Fallback: look for any metric-like phrase
    if 'rate' in text_lower:
        return 'rate'
    if 'share' in text_lower:
        return 'share'
    if 'growth' in text_lower:
        return 'growth'
    
    return 'metric'


def extract_geography(text: str) -> Optional[str]:
    """
    Extract geographic scope from text.
    
    Args:
        text: Text to analyze
        
    Returns:
        Geographic code or None
    """
    text_lower = text.lower()
    
    for geo, pattern in GEO_PATTERNS.items():
        if re.search(pattern, text_lower, re.I):
            return geo
    
    return None


def extract_cohort(text: str) -> Optional[str]:
    """
    Extract population cohort from text.
    
    Args:
        text: Text to analyze
        
    Returns:
        Cohort description or None
    """
    text_lower = text.lower()
    
    for cohort, pattern in COHORT_PATTERNS.items():
        if re.search(pattern, text_lower, re.I):
            return cohort
    
    return None