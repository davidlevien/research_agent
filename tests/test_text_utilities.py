"""
Tests for unified text utilities.
"""

import pytest
from research_system.text import (
    jaccard, text_jaccard, calculate_claim_similarity,
    word_overlap_ratio, token_overlap_count
)
from research_system.text.normalize import (
    clean_text, tokenize, remove_stopwords, normalize_whitespace,
    remove_quotes, truncate_text, generate_text_hash, get_default_stopwords
)
from research_system.text.extract import (
    extract_text, clean_html, remove_html_tags, extract_metadata
)


class TestSimilarity:
    """Test similarity calculations."""
    
    def test_jaccard_identical_sets(self):
        """Test Jaccard similarity for identical sets."""
        tokens = {"hello", "world"}
        assert jaccard(tokens, tokens) == 1.0
    
    def test_jaccard_disjoint_sets(self):
        """Test Jaccard similarity for disjoint sets."""
        tokens1 = {"hello", "world"}
        tokens2 = {"foo", "bar"}
        assert jaccard(tokens1, tokens2) == 0.0
    
    def test_jaccard_partial_overlap(self):
        """Test Jaccard similarity for partial overlap."""
        tokens1 = {"hello", "world", "test"}
        tokens2 = {"world", "test", "foo"}
        # Intersection: {"world", "test"} = 2
        # Union: {"hello", "world", "test", "foo"} = 4
        # Similarity: 2/4 = 0.5
        assert jaccard(tokens1, tokens2) == 0.5
    
    def test_text_jaccard_basic(self):
        """Test text Jaccard similarity."""
        text1 = "hello world test"
        text2 = "world test foo"
        assert text_jaccard(text1, text2) == 0.5
    
    def test_text_jaccard_with_stopwords(self):
        """Test text Jaccard with stopword filtering."""
        text1 = "the quick brown fox"
        text2 = "the lazy brown dog"
        stopwords = {"the"}
        # Without stopwords: {"quick", "brown", "fox"} vs {"lazy", "brown", "dog"}
        # Intersection: {"brown"} = 1
        # Union: {"quick", "brown", "fox", "lazy", "dog"} = 5
        assert text_jaccard(text1, text2, stopwords) == 0.2
    
    def test_claim_similarity(self):
        """Test claim similarity calculation."""
        claim1 = "Global tourism increased by 10%"
        claim2 = "Tourism worldwide grew by 10 percent"
        similarity = calculate_claim_similarity(claim1, claim2)
        assert 0 < similarity < 1  # Partial overlap expected
    
    def test_word_overlap_ratio(self):
        """Test word overlap ratio."""
        text1 = "hello world"
        text2 = "world hello"
        assert word_overlap_ratio(text1, text2) == 1.0  # Same words
    
    def test_token_overlap_count(self):
        """Test token overlap counting."""
        text1 = "hello world test"
        text2 = "world test foo"
        assert token_overlap_count(text1, text2) == 2  # "world" and "test"


class TestTextNormalization:
    """Test text normalization functions."""
    
    def test_clean_text_basic(self):
        """Test basic text cleaning."""
        text = "Hello  world!   Test."
        cleaned = clean_text(text)
        assert "  " not in cleaned  # No double spaces
    
    def test_clean_text_remove_html(self):
        """Test HTML removal in clean_text."""
        text = "Hello <b>world</b> test"
        cleaned = clean_text(text, remove_html=True)
        assert "<b>" not in cleaned
        assert "world" in cleaned
    
    def test_clean_text_remove_urls(self):
        """Test URL removal."""
        text = "Check https://example.com for more"
        cleaned = clean_text(text, remove_urls=True)
        assert "https://" not in cleaned
        assert "Check" in cleaned
    
    def test_clean_text_remove_emails(self):
        """Test email removal."""
        text = "Contact test@example.com for info"
        cleaned = clean_text(text, remove_emails=True)
        assert "@" not in cleaned
        assert "Contact" in cleaned
    
    def test_tokenize_basic(self):
        """Test basic tokenization."""
        text = "Hello World Test"
        tokens = tokenize(text)
        assert tokens == ["hello", "world", "test"]
    
    def test_tokenize_preserve_case(self):
        """Test tokenization preserving case."""
        text = "Hello World"
        tokens = tokenize(text, lowercase=False)
        assert tokens == ["Hello", "World"]
    
    def test_remove_stopwords(self):
        """Test stopword removal."""
        words = ["the", "quick", "brown", "fox"]
        stopwords = {"the", "a", "an"}
        filtered = remove_stopwords(words, stopwords)
        assert filtered == ["quick", "brown", "fox"]
    
    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        text = "Hello   world\n\n\n\ntest"
        normalized = normalize_whitespace(text)
        assert "   " not in normalized
        assert "\n\n\n" not in normalized
    
    def test_remove_quotes(self):
        """Test quote removal."""
        text = '"Hello" \'world\' `test`'
        cleaned = remove_quotes(text)
        assert '"' not in cleaned
        assert "'" not in cleaned
        assert "`" not in cleaned
        assert "Hello world test" == cleaned
    
    def test_truncate_text(self):
        """Test text truncation."""
        text = "Hello world this is a test"
        truncated = truncate_text(text, 10)
        assert truncated == "Hello w..."
        assert len(truncated) == 10
    
    def test_truncate_text_no_ellipsis(self):
        """Test truncation without ellipsis."""
        text = "Hello world"
        truncated = truncate_text(text, 5, add_ellipsis=False)
        assert truncated == "Hello"
    
    def test_generate_text_hash(self):
        """Test text hashing."""
        text = "Hello World"
        hash1 = generate_text_hash(text)
        hash2 = generate_text_hash(text)
        assert hash1 == hash2  # Same text produces same hash
        assert len(hash1) == 64  # SHA-256 produces 64 hex chars
    
    def test_generate_text_hash_normalized(self):
        """Test normalized text hashing."""
        text1 = "Hello  WORLD"
        text2 = "hello world"
        hash1 = generate_text_hash(text1, normalize=True)
        hash2 = generate_text_hash(text2, normalize=True)
        assert hash1 == hash2  # Normalized texts produce same hash
    
    def test_get_default_stopwords(self):
        """Test default stopwords."""
        stopwords = get_default_stopwords()
        assert "the" in stopwords
        assert "and" in stopwords
        assert "hello" not in stopwords
        assert len(stopwords) > 50  # Should have many stopwords


class TestTextExtraction:
    """Test text extraction functions."""
    
    def test_extract_text_basic(self):
        """Test basic text extraction from HTML."""
        html = "<html><body><p>Hello world</p></body></html>"
        text = extract_text(html)
        assert text == "Hello world"
    
    def test_extract_text_remove_scripts(self):
        """Test script removal during extraction."""
        html = "<p>Hello</p><script>alert('test')</script><p>world</p>"
        text = extract_text(html)
        assert "alert" not in text
        assert "Hello world" == text
    
    def test_extract_text_preserve_structure(self):
        """Test extraction preserving structure."""
        html = "<p>Paragraph 1</p><p>Paragraph 2</p>"
        text = extract_text(html, preserve_structure=True)
        assert "Paragraph 1" in text
        assert "Paragraph 2" in text
    
    def test_clean_html_remove_dangerous(self):
        """Test removal of dangerous HTML."""
        html = '<p>Safe</p><script>alert("xss")</script><iframe src="bad"></iframe>'
        cleaned = clean_html(html)
        assert "<script>" not in cleaned
        assert "<iframe>" not in cleaned
        assert "Safe" in cleaned
    
    def test_clean_html_remove_attributes(self):
        """Test removal of dangerous attributes."""
        html = '<p onclick="alert()">Click me</p>'
        cleaned = clean_html(html)
        assert "onclick" not in cleaned
        assert "Click me" in cleaned
    
    def test_remove_html_tags(self):
        """Test HTML tag removal."""
        text = "Hello <b>world</b> <em>test</em>"
        cleaned = remove_html_tags(text)
        assert cleaned == "Hello world test"
    
    def test_extract_metadata_title(self):
        """Test title extraction from metadata."""
        html = "<html><head><title>Test Page</title></head></html>"
        metadata = extract_metadata(html)
        assert metadata["title"] == "Test Page"
    
    def test_extract_metadata_description(self):
        """Test description extraction."""
        html = '<meta name="description" content="Test description">'
        metadata = extract_metadata(html)
        assert metadata["description"] == "Test description"
    
    def test_extract_metadata_opengraph(self):
        """Test OpenGraph metadata extraction."""
        html = '<meta property="og:description" content="OG description">'
        metadata = extract_metadata(html)
        assert metadata["description"] == "OG description"
    
    def test_extract_metadata_jsonld(self):
        """Test JSON-LD metadata extraction."""
        html = '''
        <script type="application/ld+json">
        {
            "headline": "Test Article",
            "author": {"name": "John Doe"},
            "datePublished": "2025-01-01"
        }
        </script>
        '''
        metadata = extract_metadata(html)
        assert metadata["title"] == "Test Article"
        assert metadata["author"] == "John Doe"
        assert metadata["published_date"] == "2025-01-01"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])