"""
Advanced content processing tools
"""

import re
import nltk
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
from dataclasses import dataclass
import logging
from bs4 import BeautifulSoup
import hashlib


logger = logging.getLogger(__name__)

# Download required NLTK data (in production, this would be done during setup)
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
except:
    pass


@dataclass
class ProcessedContent:
    """Processed content with metadata"""
    original_text: str
    cleaned_text: str
    summary: str
    keywords: List[str]
    entities: Dict[str, List[str]]
    statistics: Dict[str, Any]
    language: str
    reading_level: float
    sentiment_indicators: Dict[str, float]


class ContentProcessor:
    """Advanced text processing and analysis tools"""
    
    def __init__(self):
        self.stopwords = self._load_stopwords()
    
    def _load_stopwords(self) -> set:
        """Load stopwords for filtering"""
        try:
            from nltk.corpus import stopwords
            return set(stopwords.words('english'))
        except:
            # Fallback stopwords if NLTK data not available
            return {
                'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'but',
                'in', 'with', 'to', 'for', 'of', 'as', 'by', 'that', 'this',
                'it', 'from', 'be', 'are', 'was', 'were', 'been', 'have', 'has',
                'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'
            }
    
    def process_content(
        self,
        text: str,
        extract_entities: bool = True,
        generate_summary: bool = True
    ) -> ProcessedContent:
        """Comprehensive content processing"""
        
        # Clean text
        cleaned_text = self.clean_text(text)
        
        # Extract keywords
        keywords = self.extract_keywords(cleaned_text, num_keywords=10)
        
        # Extract entities if requested
        entities = self.extract_named_entities(cleaned_text) if extract_entities else {}
        
        # Generate summary if requested
        summary = self.summarize_content(cleaned_text, max_sentences=3) if generate_summary else ""
        
        # Calculate statistics
        statistics = self.calculate_text_statistics(text)
        
        # Detect language
        language = self.detect_language(cleaned_text)
        
        # Calculate reading level
        reading_level = self.calculate_reading_level(cleaned_text)
        
        # Analyze sentiment indicators
        sentiment_indicators = self.analyze_sentiment_indicators(cleaned_text)
        
        return ProcessedContent(
            original_text=text,
            cleaned_text=cleaned_text,
            summary=summary,
            keywords=keywords,
            entities=entities,
            statistics=statistics,
            language=language,
            reading_level=reading_level,
            sentiment_indicators=sentiment_indicators
        )
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        from research_system.text.normalize import clean_text
        
        # Use unified text cleaning
        return clean_text(text, remove_html=True, remove_urls=True, remove_emails=True)
    
    def extract_keywords(
        self,
        text: str,
        num_keywords: int = 10,
        include_phrases: bool = True
    ) -> List[str]:
        """Extract keywords using TF-IDF approach"""
        
        if not text:
            return []
        
        # Tokenize
        words = re.findall(r'\b[a-z]+\b', text.lower())
        
        # Filter stopwords
        words = [w for w in words if w not in self.stopwords and len(w) > 2]
        
        # Get word frequencies
        word_freq = Counter(words)
        
        # Extract single keywords
        keywords = [word for word, _ in word_freq.most_common(num_keywords)]
        
        # Extract key phrases if requested
        if include_phrases:
            phrases = self._extract_key_phrases(text, num_phrases=5)
            keywords.extend(phrases)
        
        return keywords[:num_keywords]
    
    def _extract_key_phrases(self, text: str, num_phrases: int = 5) -> List[str]:
        """Extract key phrases from text"""
        
        phrases = []
        
        # Extract 2-gram and 3-gram phrases
        words = text.lower().split()
        
        # 2-grams
        for i in range(len(words) - 1):
            phrase = f"{words[i]} {words[i+1]}"
            if all(w not in self.stopwords for w in [words[i], words[i+1]]):
                phrases.append(phrase)
        
        # 3-grams
        for i in range(len(words) - 2):
            phrase = f"{words[i]} {words[i+1]} {words[i+2]}"
            if sum(w not in self.stopwords for w in [words[i], words[i+1], words[i+2]]) >= 2:
                phrases.append(phrase)
        
        # Count phrase frequencies
        phrase_freq = Counter(phrases)
        
        # Return most common phrases
        return [phrase for phrase, _ in phrase_freq.most_common(num_phrases)]
    
    def summarize_content(
        self,
        text: str,
        max_sentences: int = 3,
        max_length: int = 500
    ) -> str:
        """Generate extractive summary"""
        
        if not text:
            return ""
        
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        if not sentences:
            return text[:max_length]
        
        # Score sentences based on keyword frequency
        keywords = self.extract_keywords(text, num_keywords=10)
        keyword_set = set(keywords)
        
        sentence_scores = []
        for sentence in sentences:
            words = set(sentence.lower().split())
            score = len(words & keyword_set) / len(words) if words else 0
            sentence_scores.append((sentence, score))
        
        # Sort by score and select top sentences
        sentence_scores.sort(key=lambda x: x[1], reverse=True)
        summary_sentences = [s for s, _ in sentence_scores[:max_sentences]]
        
        # Maintain original order
        summary_sentences = [s for s in sentences if s in summary_sentences]
        
        summary = '. '.join(summary_sentences)
        if not summary.endswith('.'):
            summary += '.'
        
        # Truncate if too long
        if len(summary) > max_length:
            summary = summary[:max_length-3] + '...'
        
        return summary
    
    def extract_named_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract named entities from text"""
        
        entities = {
            "people": [],
            "organizations": [],
            "locations": [],
            "dates": [],
            "numbers": [],
            "urls": [],
            "emails": []
        }
        
        if not text:
            return entities
        
        # Extract URLs
        entities["urls"] = re.findall(r'https?://\S+|www\.\S+', text)
        
        # Extract emails
        entities["emails"] = re.findall(r'\S+@\S+\.\S+', text)
        
        # Extract dates
        date_patterns = [
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b',
            r'\b\d{4}\b'
        ]
        for pattern in date_patterns:
            entities["dates"].extend(re.findall(pattern, text, re.IGNORECASE))
        
        # Extract numbers
        entities["numbers"] = re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', text)
        
        # Simple NER using capitalization patterns
        # Extract potential person names (Title Case)
        person_pattern = r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'
        entities["people"] = list(set(re.findall(person_pattern, text)))
        
        # Extract potential organizations (all caps or special patterns)
        org_pattern = r'\b[A-Z]{2,}\b|\b[A-Z][a-z]+ (?:Inc|Corp|LLC|Ltd|Company|Group)\b'
        entities["organizations"] = list(set(re.findall(org_pattern, text)))
        
        # Extract potential locations (with common suffixes)
        location_pattern = r'\b[A-Z][a-z]+ (?:City|County|State|Country|Island|Mountain|River|Lake)\b'
        entities["locations"] = list(set(re.findall(location_pattern, text)))
        
        return entities
    
    def calculate_text_statistics(self, text: str) -> Dict[str, Any]:
        """Calculate various text statistics"""
        
        if not text:
            return {
                "character_count": 0,
                "word_count": 0,
                "sentence_count": 0,
                "paragraph_count": 0,
                "avg_word_length": 0,
                "avg_sentence_length": 0
            }
        
        # Character count
        char_count = len(text)
        
        # Word count
        words = re.findall(r'\b\w+\b', text)
        word_count = len(words)
        
        # Sentence count
        sentences = re.split(r'[.!?]+', text)
        sentence_count = len([s for s in sentences if s.strip()])
        
        # Paragraph count
        paragraphs = text.split('\n\n')
        paragraph_count = len([p for p in paragraphs if p.strip()])
        
        # Average word length
        avg_word_length = sum(len(w) for w in words) / word_count if word_count > 0 else 0
        
        # Average sentence length
        avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0
        
        return {
            "character_count": char_count,
            "word_count": word_count,
            "sentence_count": sentence_count,
            "paragraph_count": paragraph_count,
            "avg_word_length": round(avg_word_length, 2),
            "avg_sentence_length": round(avg_sentence_length, 2),
            "unique_words": len(set(words)),
            "lexical_diversity": len(set(words)) / word_count if word_count > 0 else 0
        }
    
    def detect_language(self, text: str) -> str:
        """Simple language detection based on common words"""
        
        if not text:
            return "unknown"
        
        # Common words in different languages
        language_indicators = {
            "english": ["the", "is", "and", "to", "of", "in", "that", "it"],
            "spanish": ["el", "la", "de", "que", "y", "en", "un", "por"],
            "french": ["le", "de", "et", "la", "les", "des", "est", "un"],
            "german": ["der", "die", "und", "das", "ist", "ein", "nicht", "mit"]
        }
        
        text_lower = text.lower()
        words = text_lower.split()
        
        scores = {}
        for lang, indicators in language_indicators.items():
            score = sum(1 for word in words if word in indicators)
            scores[lang] = score
        
        # Return language with highest score
        if scores:
            detected = max(scores.items(), key=lambda x: x[1])
            if detected[1] > 0:
                return detected[0]
        
        return "english"  # Default to English
    
    def calculate_reading_level(self, text: str) -> float:
        """Calculate Flesch Reading Ease score"""
        
        if not text:
            return 0.0
        
        # Count sentences
        sentences = re.split(r'[.!?]+', text)
        sentence_count = len([s for s in sentences if s.strip()])
        
        # Count words
        words = re.findall(r'\b\w+\b', text)
        word_count = len(words)
        
        # Count syllables (simplified)
        syllable_count = 0
        for word in words:
            syllable_count += self._count_syllables(word)
        
        if sentence_count == 0 or word_count == 0:
            return 0.0
        
        # Flesch Reading Ease formula
        score = 206.835 - 1.015 * (word_count / sentence_count) - 84.6 * (syllable_count / word_count)
        
        # Clamp between 0 and 100
        return max(0, min(100, score))
    
    def _count_syllables(self, word: str) -> int:
        """Simple syllable counting"""
        word = word.lower()
        vowels = "aeiou"
        syllable_count = 0
        previous_was_vowel = False
        
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not previous_was_vowel:
                syllable_count += 1
            previous_was_vowel = is_vowel
        
        # Adjust for silent e
        if word.endswith('e'):
            syllable_count -= 1
        
        # Ensure at least one syllable
        return max(1, syllable_count)
    
    def analyze_sentiment_indicators(self, text: str) -> Dict[str, float]:
        """Analyze sentiment indicators in text"""
        
        if not text:
            return {
                "positive": 0.0,
                "negative": 0.0,
                "neutral": 1.0,
                "subjectivity": 0.0
            }
        
        # Simple sentiment word lists
        positive_words = {
            'good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic',
            'positive', 'successful', 'beautiful', 'perfect', 'best', 'love',
            'happy', 'joy', 'brilliant', 'outstanding'
        }
        
        negative_words = {
            'bad', 'terrible', 'awful', 'horrible', 'poor', 'worst', 'fail',
            'negative', 'unsuccessful', 'ugly', 'hate', 'sad', 'angry',
            'disappointed', 'frustrating', 'annoying'
        }
        
        subjective_words = {
            'think', 'believe', 'feel', 'opinion', 'seems', 'appears',
            'probably', 'maybe', 'perhaps', 'might', 'could', 'should'
        }
        
        words = text.lower().split()
        total_words = len(words)
        
        if total_words == 0:
            return {
                "positive": 0.0,
                "negative": 0.0,
                "neutral": 1.0,
                "subjectivity": 0.0
            }
        
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        subjective_count = sum(1 for word in words if word in subjective_words)
        
        positive_score = positive_count / total_words
        negative_score = negative_count / total_words
        neutral_score = 1.0 - (positive_score + negative_score)
        subjectivity_score = subjective_count / total_words
        
        return {
            "positive": round(positive_score, 3),
            "negative": round(negative_score, 3),
            "neutral": round(max(0, neutral_score), 3),
            "subjectivity": round(subjectivity_score, 3)
        }
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts using Jaccard similarity"""
        from research_system.text import text_jaccard
        
        # Use unified similarity calculation
        similarity = text_jaccard(text1, text2, self.stopwords)
        return round(similarity, 3)
    
    def generate_content_hash(self, text: str) -> str:
        """Generate hash for content deduplication"""
        
        if not text:
            return ""
        
        # Normalize text for hashing
        normalized = self.clean_text(text).lower()
        
        # Generate SHA-256 hash
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def extract_related_topics(
        self, 
        cards: List[Any],  # List[EvidenceCard]
        seed_topic: str, 
        k: int = 8
    ) -> List[Dict[str, Any]]:
        """
        Lightweight candidate generation for related topics:
        - collect noun-ish tokens from titles/snippets/claims
        - score by frequency × novelty × recency
        - return k diverse candidates with inclusion reasons
        """
        from datetime import datetime, timezone
        from collections import defaultdict
        
        def _tokenize(text: str) -> List[str]:
            return [t.lower() for t in re.findall(r"[a-z0-9]{3,}", text or "")]
        
        def _score_related(cands: Dict[str, Dict[str, float]]) -> List[tuple]:
            ranked = []
            for key, metrics in cands.items():
                score = metrics["freq"] * (1 + metrics.get("recency_boost", 0)) * (1 + metrics.get("novelty", 0))
                reason = metrics.get("reason", "High co-mention frequency with new angles")
                ranked.append((key, score, reason))
            return sorted(ranked, key=lambda x: x[1], reverse=True)
        
        seed_tokens = set(_tokenize(seed_topic))
        now = datetime.now(timezone.utc)
        buckets: Dict[str, Dict[str, float]] = defaultdict(lambda: {"freq": 0, "novelty": 0, "recency_boost": 0})
        
        # Common words to exclude
        exclude_words = {"the", "and", "for", "with", "from", "into", "about", "travel", "tourism", "trend", "trends", "2024", "2025"}
        
        for card in cards:
            # Gather text from various fields
            text_parts = []
            if hasattr(card, 'title'):
                text_parts.append(card.title)
            if hasattr(card, 'snippet'):
                text_parts.append(card.snippet or "")
            if hasattr(card, 'claim'):
                text_parts.append(card.claim or "")
            
            text = " ".join(text_parts)
            tokens = _tokenize(text)
            
            for token in tokens:
                if token in seed_tokens or token in exclude_words or len(token) < 4:
                    continue
                    
                bucket = buckets[token]
                bucket["freq"] += 1
                
                # Boost for novelty (not in seed)
                if token not in seed_tokens:
                    bucket["novelty"] = 0.2
                
                # Boost for recency
                if hasattr(card, 'date') and card.date:
                    try:
                        if isinstance(card.date, str):
                            card_date = datetime.fromisoformat(card.date.replace('Z', '+00:00'))
                        else:
                            card_date = card.date
                        # Ensure both are timezone-aware
                        if card_date.tzinfo is None:
                            card_date = card_date.replace(tzinfo=timezone.utc)
                        age_days = max(1, (now - card_date).days)
                        bucket["recency_boost"] = max(bucket["recency_boost"], min(1.0, 30 / age_days))
                    except:
                        pass
        
        # Score and rank
        ranked = _score_related(buckets)
        
        # Diversify results
        output = []
        seen_roots = set()
        
        for term, score, reason in ranked[:k * 3]:  # Over-sample then filter
            # Skip if too similar to already selected terms
            root = term[:5]
            if root in seen_roots:
                continue
            
            # Skip if it's a substring of an existing term or vice versa
            if any(term in existing["name"] or existing["name"] in term for existing in output):
                continue
            
            output.append({
                "name": term,
                "score": float(score),
                "reason_to_include": reason
            })
            seen_roots.add(root)
            
            if len(output) >= k:
                break
        
        return output