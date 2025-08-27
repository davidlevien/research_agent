"""Tests for semantic intent classification."""

import pytest
import os
from research_system.intent.classifier import Intent, classify
from research_system.intent import semantic, nli_fallback


class TestSemanticClassifier:
    """Test semantic classification functionality."""
    
    def test_semantic_init(self):
        """Test semantic classifier initialization."""
        semantic.init()
        
        # Check model is loaded
        assert semantic._MODEL is not None or not self._has_sentence_transformers()
        
        # Check labels are loaded
        assert len(semantic._LABELS) > 0
        
        # Check examples are loaded
        assert len(semantic._EXAMPLES) > 0
    
    def test_semantic_score(self):
        """Test semantic scoring returns ranked intents."""
        semantic.init()
        
        if not self._has_sentence_transformers():
            pytest.skip("SentenceTransformers not available")
        
        scores = semantic.score("what is quantum computing")
        
        # Should return list of tuples
        assert isinstance(scores, list)
        assert all(isinstance(item, tuple) for item in scores)
        assert all(len(item) == 2 for item in scores)
        
        # Scores should be sorted descending
        score_values = [s for _, s in scores]
        assert score_values == sorted(score_values, reverse=True)
        
        # Scores should be in 0..1 range
        assert all(0 <= s <= 1 for _, s in scores)
    
    def test_semantic_predict(self):
        """Test semantic prediction with confidence threshold."""
        semantic.init()
        
        if not self._has_sentence_transformers():
            pytest.skip("SentenceTransformers not available")
        
        # High confidence query
        label, confidence, scores = semantic.predict("what is quantum computing")
        assert label in ["encyclopedia", "generic"]
        assert 0 <= confidence <= 1
        assert len(scores) > 0
        
        # Low confidence should return generic
        label, confidence, scores = semantic.predict("xyz123 asdf", min_score=0.9)
        assert label == "generic"
    
    def test_semantic_examples_boost(self):
        """Test that examples boost relevant intents."""
        semantic.init()
        
        if not self._has_sentence_transformers():
            pytest.skip("SentenceTransformers not available")
        
        # Query similar to travel examples
        scores = semantic.score("best beaches in Thailand")
        scores_dict = dict(scores)
        
        # Travel should be high-ranked
        assert "travel" in scores_dict
        assert scores_dict["travel"] > 0.4
    
    def test_semantic_fallback_without_model(self):
        """Test semantic classifier works without model."""
        # Force model to None
        semantic._MODEL = None
        
        scores = semantic.score("test query")
        
        # Should return equal scores
        assert len(scores) > 0
        assert all(s == 0.5 for _, s in scores)
    
    def _has_sentence_transformers(self):
        """Check if SentenceTransformers is available."""
        try:
            import sentence_transformers
            return True
        except ImportError:
            return False


class TestNLIFallback:
    """Test NLI fallback classification."""
    
    def test_nli_init(self):
        """Test NLI classifier initialization."""
        nli_fallback.init()
        
        # Check pipeline is loaded (or None if not available)
        if self._has_transformers():
            assert nli_fallback._NLI_PIPELINE is not None
            assert nli_fallback._NLI_LABELS is not None
    
    def test_nli_classify(self):
        """Test NLI zero-shot classification."""
        nli_fallback.init()
        
        if not self._has_transformers():
            pytest.skip("Transformers not available")
        
        scores = nli_fallback.classify("latest AI developments")
        
        # Should return list of tuples
        assert isinstance(scores, list)
        assert all(isinstance(item, tuple) for item in scores)
        
        # Scores should sum to approximately 1 (for single-label)
        score_sum = sum(s for _, s in scores)
        assert 0.95 <= score_sum <= 1.05
    
    def test_nli_predict(self):
        """Test NLI prediction with confidence threshold."""
        nli_fallback.init()
        
        if not self._has_transformers():
            pytest.skip("Transformers not available")
        
        label, confidence, scores = nli_fallback.predict("systematic review COVID vaccines")
        assert label in ["academic", "medical", "generic"]
        assert 0 <= confidence <= 1
        assert len(scores) > 0
    
    def test_nli_multi_label(self):
        """Test NLI multi-label classification."""
        nli_fallback.init()
        
        if not self._has_transformers():
            pytest.skip("Transformers not available")
        
        scores = nli_fallback.classify(
            "travel guide with statistics",
            multi_label=True
        )
        
        # Multi-label scores don't need to sum to 1
        assert len(scores) > 0
        assert all(0 <= s <= 1 for _, s in scores)
    
    def test_nli_fallback_without_model(self):
        """Test NLI classifier works without model."""
        # Force pipeline to None
        nli_fallback._NLI_PIPELINE = None
        
        scores = nli_fallback.classify("test query")
        
        # Should return equal scores
        assert len(scores) > 0
        assert all(s == 0.5 for _, s in scores)
    
    def _has_transformers(self):
        """Check if transformers is available."""
        try:
            import transformers
            return True
        except ImportError:
            return False


class TestHybridClassification:
    """Test hybrid classification pipeline."""
    
    def test_hybrid_pipeline_rules_first(self):
        """Test rules take precedence in hybrid pipeline."""
        # Query with clear rule match
        intent = classify("how to build a website", use_hybrid=True)
        assert intent == Intent.HOWTO
    
    def test_hybrid_pipeline_semantic_fallback(self):
        """Test semantic classification when rules don't match."""
        if not self._has_sentence_transformers():
            pytest.skip("SentenceTransformers not available")
        
        # Initialize semantic classifier
        semantic.init()
        
        # Query without rule match but clear semantic intent
        intent = classify("quantum computing explained", use_hybrid=True)
        assert intent in [Intent.ENCYCLOPEDIA, Intent.GENERIC]
    
    def test_hybrid_disabled(self):
        """Test classification with hybrid disabled."""
        # Query without rule match
        intent = classify("random query without patterns", use_hybrid=False)
        assert intent == Intent.GENERIC
    
    def test_hybrid_environment_control(self):
        """Test hybrid controlled by environment variable."""
        # Enable hybrid
        os.environ["INTENT_USE_HYBRID"] = "true"
        intent1 = classify("quantum physics research")
        
        # Disable hybrid
        os.environ["INTENT_USE_HYBRID"] = "false"
        intent2 = classify("quantum physics research")
        
        # With hybrid, might get ACADEMIC or ENCYCLOPEDIA
        # Without hybrid, should get GENERIC (no rule match)
        assert intent2 == Intent.GENERIC or intent1 != Intent.GENERIC
        
        # Clean up
        del os.environ["INTENT_USE_HYBRID"]
    
    def test_hybrid_confidence_thresholds(self):
        """Test confidence thresholds in hybrid pipeline."""
        if not self._has_sentence_transformers():
            pytest.skip("SentenceTransformers not available")
        
        # Set high thresholds to force fallback
        os.environ["INTENT_MIN_SCORE"] = "0.99"
        os.environ["INTENT_NLI_MIN_SCORE"] = "0.99"
        
        try:
            semantic.init()
            intent = classify("ambiguous query", use_hybrid=True)
            # Should fall back to generic with high thresholds
            assert intent == Intent.GENERIC
        finally:
            # Clean up
            if "INTENT_MIN_SCORE" in os.environ:
                del os.environ["INTENT_MIN_SCORE"]
            if "INTENT_NLI_MIN_SCORE" in os.environ:
                del os.environ["INTENT_NLI_MIN_SCORE"]
    
    def _has_sentence_transformers(self):
        """Check if SentenceTransformers is available."""
        try:
            import sentence_transformers
            return True
        except ImportError:
            return False


class TestSemanticExamples:
    """Test semantic classification with specific examples."""
    
    @pytest.mark.parametrize("query,expected_intents", [
        ("origins of the platypus", ["encyclopedia"]),
        ("best desk fans under $50", ["product"]),
        ("coffee shops near me", ["local"]),
        ("latest AI developments", ["news"]),
        ("systematic review COVID vaccines", ["academic", "medical"]),
        ("GDP growth rate 2024", ["stats"]),
        ("itinerary for Japan trip", ["travel"]),
        ("Apple 10-K filing", ["regulatory"]),
        ("how to build a website", ["howto"]),
        ("symptoms of diabetes", ["medical"]),
    ])
    def test_semantic_with_examples(self, query, expected_intents):
        """Test semantic classification with example queries."""
        if not self._has_sentence_transformers():
            pytest.skip("SentenceTransformers not available")
        
        semantic.init()
        label, confidence, scores = semantic.predict(query)
        
        # Should classify as one of expected intents or generic
        assert label in expected_intents + ["generic"]
        
        # Check expected intent is in top 3
        top_3_labels = [l for l, _ in scores[:3]]
        assert any(intent in top_3_labels for intent in expected_intents)
    
    def _has_sentence_transformers(self):
        """Check if SentenceTransformers is available."""
        try:
            import sentence_transformers
            return True
        except ImportError:
            return False