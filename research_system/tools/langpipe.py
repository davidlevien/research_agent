"""Language detection and translation preparation."""

import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

# Optional import - language detection is optional
try:
    from langdetect import detect, detect_langs, LangDetectException
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False
    logger.debug("langdetect not available - language detection disabled")


def detect_language(text: str) -> Optional[str]:
    """
    Detect language of text.
    
    Args:
        text: Text to analyze
        
    Returns:
        ISO 639-1 language code (e.g., 'en', 'es', 'fr')
    """
    if not LANGDETECT_AVAILABLE:
        return None
        
    if not text or len(text.strip()) < 20:
        return None
        
    try:
        return detect(text)
    except LangDetectException:
        return None
    except Exception as e:
        logger.debug(f"Language detection failed: {e}")
        return None


def detect_languages_with_confidence(text: str) -> List[tuple[str, float]]:
    """
    Detect possible languages with confidence scores.
    
    Args:
        text: Text to analyze
        
    Returns:
        List of (language_code, confidence) tuples
    """
    if not LANGDETECT_AVAILABLE:
        return []
        
    if not text or len(text.strip()) < 20:
        return []
        
    try:
        results = detect_langs(text)
        return [(r.lang, r.prob) for r in results]
    except LangDetectException:
        return []
    except Exception as e:
        logger.debug(f"Language detection failed: {e}")
        return []


def is_english(text: str, threshold: float = 0.8) -> bool:
    """
    Check if text is likely English.
    
    Args:
        text: Text to check
        threshold: Confidence threshold
        
    Returns:
        True if text is likely English
    """
    if not text:
        return False
        
    langs = detect_languages_with_confidence(text)
    
    for lang, conf in langs:
        if lang == "en" and conf >= threshold:
            return True
            
    return False


def to_english(text: str) -> str:
    """
    Placeholder for translation to English.
    
    Currently returns original text. Hook for future MT integration.
    
    Args:
        text: Text to translate
        
    Returns:
        English text (or original if translation not available)
    """
    if not text:
        return text
        
    # Check if already English
    if is_english(text):
        return text
        
    # Placeholder for future machine translation
    # For now, return original text
    lang = detect_language(text)
    if lang and lang != "en":
        logger.debug(f"Non-English text detected ({lang}), translation not implemented")
        
    return text


def prepare_multilingual_query(query: str, target_languages: List[str] = None) -> List[str]:
    """
    Prepare query variants for multilingual search.
    
    Args:
        query: Original query
        target_languages: List of language codes to target
        
    Returns:
        List of query variants
    """
    queries = [query]  # Always include original
    
    if not target_languages:
        # Default multilingual targets for common languages
        target_languages = ["es", "fr", "de", "zh", "ja", "ar"]
    
    # Placeholder for future translation
    # For now, just return original query
    # In production, would translate query to each target language
    
    return queries


def filter_by_language(texts: List[str], language: str = "en") -> List[str]:
    """
    Filter list of texts by language.
    
    Args:
        texts: List of texts to filter
        language: Target language code
        
    Returns:
        Filtered list containing only texts in target language
    """
    if not LANGDETECT_AVAILABLE:
        return texts
        
    filtered = []
    
    for text in texts:
        if not text:
            continue
            
        try:
            detected = detect_language(text)
            if detected == language:
                filtered.append(text)
        except Exception:
            # On error, include the text
            filtered.append(text)
            
    return filtered


def get_language_distribution(texts: List[str]) -> dict[str, int]:
    """
    Get distribution of languages in a list of texts.
    
    Args:
        texts: List of texts to analyze
        
    Returns:
        Dictionary mapping language code to count
    """
    if not LANGDETECT_AVAILABLE:
        return {}
        
    distribution = {}
    
    for text in texts:
        if not text:
            continue
            
        lang = detect_language(text)
        if lang:
            distribution[lang] = distribution.get(lang, 0) + 1
            
    return distribution