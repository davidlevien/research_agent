"""Test entity normalization functionality."""

import pytest
from research_system.tools.entity_norm import normalize_entity, is_same_entity


def test_unwto_alias():
    """Test UNWTO aliases normalize correctly."""
    assert normalize_entity("UN Tourism") == "unwto"
    assert normalize_entity("U.N. Tourism") == "unwto"
    assert normalize_entity("un-tourism") == "unwto"
    assert normalize_entity("World Tourism Organization") == "unwto"


def test_country_normalization():
    """Test country name normalization."""
    # USA variants
    assert normalize_entity("United States") == "united states"
    assert normalize_entity("USA") == "united states"
    assert normalize_entity("U.S.") == "united states"
    assert normalize_entity("America") == "united states"
    
    # UK variants
    assert normalize_entity("UK") == "united kingdom"
    assert normalize_entity("U.K.") == "united kingdom"
    assert normalize_entity("Britain") == "united kingdom"
    assert normalize_entity("Great Britain") == "united kingdom"
    
    # Saudi Arabia variants
    assert normalize_entity("Saudi") == "saudi arabia"
    assert normalize_entity("KSA") == "saudi arabia"
    assert normalize_entity("Kingdom of Saudi Arabia") == "saudi arabia"


def test_organization_normalization():
    """Test organization name normalization."""
    assert normalize_entity("International Air Transport Association") == "iata"
    assert normalize_entity("World Travel & Tourism Council") == "wttc"
    assert normalize_entity("World Health Organization") == "who"
    assert normalize_entity("W.H.O.") == "who"


def test_region_normalization():
    """Test region name normalization."""
    assert normalize_entity("Asia-Pacific") == "asia pacific"
    assert normalize_entity("APAC") == "asia pacific"
    assert normalize_entity("Asia and the Pacific") == "asia pacific"
    
    assert normalize_entity("MENA") == "middle east"
    assert normalize_entity("Middle East and North Africa") == "middle east"


def test_is_same_entity():
    """Test entity comparison."""
    assert is_same_entity("USA", "United States") is True
    assert is_same_entity("UN Tourism", "UNWTO") is True
    assert is_same_entity("UK", "Germany") is False
    assert is_same_entity(None, "USA") is False
    assert is_same_entity("USA", None) is False


def test_preserve_unknown():
    """Test that unknown entities are preserved."""
    assert normalize_entity("Some Random Company") == "Some Random Company"
    assert normalize_entity("Unknown Country XYZ") == "Unknown Country XYZ"