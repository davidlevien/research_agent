"""Evidence-number binding enforcement for reports."""

import logging
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class NumberBinding:
    """Binding between a numeric claim and its evidence."""
    bullet_id: str
    value: str
    evidence_card_id: str
    quote_span: str
    source_domain: Optional[str] = None

class BindingError(Exception):
    """Raised when evidence binding requirements are not met."""
    pass

def enforce_number_bindings(
    bullets: List[Dict[str, Any]], 
    bindings: Dict[str, NumberBinding], 
    cards_by_id: Dict[str, Any]
) -> None:
    """
    Enforce that all numeric bullets have valid evidence bindings.
    
    Requirements:
    - Every bullet must have a binding
    - Every binding must reference a valid card
    - No placeholders allowed
    - Quote span must be non-empty
    
    Args:
        bullets: List of bullet dicts with 'id' and 'text' keys
        bindings: Map of bullet_id to NumberBinding
        cards_by_id: Map of card ID to card object
        
    Raises:
        BindingError: If any binding requirement is violated
    """
    if not bullets:
        return
    
    # Check for missing bindings
    missing = [b for b in bullets if b["id"] not in bindings]
    if missing:
        missing_ids = [b["id"] for b in missing]
        raise BindingError(f"Unbound numeric bullets: {missing_ids}")
    
    # Validate each binding
    for bullet in bullets:
        bullet_id = bullet["id"]
        nb = bindings[bullet_id]
        
        # Check card exists
        if nb.evidence_card_id not in cards_by_id:
            raise BindingError(
                f"Binding for '{bullet_id}' references unknown card '{nb.evidence_card_id}'"
            )
        
        # Check for placeholders in value
        placeholders = ["[", "]", "TBD", "TODO", "XXX", "???"]
        for placeholder in placeholders:
            if placeholder in nb.value:
                raise BindingError(
                    f"Binding for '{bullet_id}' contains placeholder: {nb.value}"
                )
        
        # Check quote span is not empty
        if not nb.quote_span or nb.quote_span.strip() == "":
            raise BindingError(
                f"Binding for '{bullet_id}' has empty quote span"
            )
        
        # Verify the value appears in the quote span
        if nb.value not in nb.quote_span:
            logger.warning(
                f"Value '{nb.value}' not found in quote span for '{bullet_id}'"
            )
    
    logger.info(f"Validated {len(bullets)} evidence bindings")

def build_evidence_bindings(
    cards: List[Any], 
    bullets: List[Dict[str, Any]]
) -> Dict[str, NumberBinding]:
    """
    Build evidence bindings for numeric bullets.
    
    Attempts to match each bullet to the most relevant evidence card.
    
    Args:
        cards: List of evidence cards
        bullets: List of bullet dicts
        
    Returns:
        Dict mapping bullet_id to NumberBinding
    """
    bindings = {}
    
    for bullet in bullets:
        bullet_id = bullet["id"]
        bullet_text = bullet.get("text", "")
        bullet_value = bullet.get("value", "")
        
        # Find best matching card
        best_card = None
        best_quote = ""
        best_score = 0
        
        for card in cards:
            # Get card text
            card_text = (
                getattr(card, "snippet", "") or
                getattr(card, "text", "") or
                getattr(card, "quote_span", "")
            )
            
            if not card_text:
                continue
            
            # Check if bullet value appears in card
            if bullet_value and bullet_value in card_text:
                # Extract surrounding context
                import re
                pattern = re.escape(bullet_value)
                matches = list(re.finditer(pattern, card_text))
                
                if matches:
                    # Get context around first match
                    match = matches[0]
                    start = max(0, match.start() - 50)
                    end = min(len(card_text), match.end() + 50)
                    quote = card_text[start:end].strip()
                    
                    # Score based on primary source and credibility
                    score = 1.0
                    if getattr(card, "is_primary_source", False):
                        score += 1.0
                    score += getattr(card, "credibility_score", 0.5)
                    
                    if score > best_score:
                        best_card = card
                        best_quote = quote
                        best_score = score
        
        # Create binding if we found a match
        if best_card:
            bindings[bullet_id] = NumberBinding(
                bullet_id=bullet_id,
                value=bullet_value,
                evidence_card_id=getattr(best_card, "id", "unknown"),
                quote_span=best_quote,
                source_domain=getattr(best_card, "source_domain", "unknown")
            )
        else:
            # No match found - this will fail validation
            logger.warning(f"No evidence found for bullet '{bullet_id}': {bullet_text}")
    
    return bindings

def assert_no_placeholders(text: str) -> None:
    """
    Assert that text contains no placeholders.
    
    Args:
        text: Text to check
        
    Raises:
        ValueError: If placeholders are detected
    """
    placeholders = [
        "[increase", "[decrease", "[TBD", "[TODO",
        "[]", "XXX", "???", "...", "[PLACEHOLDER"
    ]
    
    for placeholder in placeholders:
        if placeholder in text:
            raise ValueError(f"Placeholder detected in report: {placeholder}")

def validate_references_section(references: str) -> None:
    """
    Validate that references section is not empty.
    
    Args:
        references: References section text
        
    Raises:
        BindingError: If references are empty or invalid
    """
    if not references or not references.strip():
        raise BindingError("Empty References section — refusing to render")
    
    # Should have at least one citation
    lines = references.strip().split('\n')
    citation_count = sum(1 for line in lines if line.strip() and not line.startswith('#'))
    
    if citation_count < 1:
        raise BindingError("References section has no citations")
    
    logger.info(f"Validated references section with {citation_count} citations")

def format_inline_citation(binding: NumberBinding) -> str:
    """
    Format an inline citation for a number binding.
    
    Args:
        binding: NumberBinding object
        
    Returns:
        Formatted citation string
    """
    # Format: value [source]
    source = binding.source_domain or "source"
    return f"{binding.value} [{source}]"

def build_references_from_bindings(
    bindings: Dict[str, NumberBinding],
    cards_by_id: Dict[str, Any]
) -> List[str]:
    """
    Build a references list from evidence bindings.
    
    Args:
        bindings: Evidence bindings
        cards_by_id: Map of card IDs to cards
        
    Returns:
        List of formatted reference strings
    """
    references = []
    seen_cards = set()
    
    for binding in bindings.values():
        card_id = binding.evidence_card_id
        
        if card_id in seen_cards:
            continue
        
        seen_cards.add(card_id)
        
        card = cards_by_id.get(card_id)
        if not card:
            continue
        
        # Format reference
        title = getattr(card, "title", "Untitled")
        url = getattr(card, "url", "")
        source = getattr(card, "source_domain", "Unknown")
        year = getattr(card, "year", "n.d.")
        
        if url:
            ref = f"- {title}. {source}, {year}. Available at: {url}"
        else:
            ref = f"- {title}. {source}, {year}."
        
        references.append(ref)
    
    return sorted(references)