"""Unit tests for parallel collection of free API providers."""

import asyncio
import time
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from research_system.collection import (
    collect_from_free_apis_async,
    _execute_provider_async,
    collect_from_free_apis
)
from research_system.models import EvidenceCard


class TestParallelCollection:
    """Test parallel execution of free API providers."""
    
    @pytest.mark.asyncio
    async def test_parallel_execution_faster_than_serial(self):
        """Test that parallel execution is faster than serial would be."""
        
        # Mock provider implementations with delays
        def slow_search(topic):
            """Simulate a slow API call."""
            time.sleep(0.5)  # 500ms delay
            return [{"title": f"Result for {topic}", "url": f"https://example.com/{topic}"}]
        
        def to_cards(results):
            """Convert results to card format."""
            return [{"title": r["title"], "url": r["url"], "snippet": "Test"} for r in results]
        
        mock_providers = {
            "openalex": {"search": slow_search, "to_cards": to_cards},
            "crossref": {"search": slow_search, "to_cards": to_cards},
            "wikipedia": {"search": slow_search, "to_cards": to_cards},
        }
        
        with patch("research_system.collection.enhanced.PROVIDERS", mock_providers):
            with patch("research_system.collection.enhanced.choose_providers") as mock_choose:
                mock_choose.return_value = MagicMock(
                    providers=["openalex", "crossref", "wikipedia"],
                    categories=["test"]
                )
                # Mock is_off_topic to always return False
                with patch("research_system.collection.enhanced.is_off_topic", return_value=False):
                    start_time = time.time()
                    # Pass providers explicitly to avoid routing
                    cards = await collect_from_free_apis_async("test topic", providers=["openalex", "crossref", "wikipedia"])
                    elapsed = time.time() - start_time
                    
                    # Should complete in ~0.5s (parallel) not ~1.5s (serial)
                    assert elapsed < 1.0, f"Parallel execution took {elapsed}s, should be < 1.0s"
                    assert len(cards) == 3, f"Expected 3 cards, got {len(cards)}"
    
    @pytest.mark.asyncio
    async def test_provider_timeout_handling(self):
        """Test that timeouts are handled gracefully."""
        
        async def hanging_provider(topic):
            """Simulate a provider that hangs."""
            await asyncio.sleep(10)  # Way too long
            return []
        
        def normal_search(topic):
            """Normal fast search."""
            return [{"title": "Quick result", "url": "https://fast.com"}]
        
        def to_cards(results):
            return [{"title": r["title"], "url": r["url"], "snippet": "Test"} for r in results]
        
        mock_impl_slow = {"search": lambda t: asyncio.run(hanging_provider(t)), "to_cards": to_cards}
        mock_impl_fast = {"search": normal_search, "to_cards": to_cards}
        
        # Test with 1 second timeout
        cards = await _execute_provider_async("worldbank", "test", mock_impl_slow)
        assert len(cards) == 0, "Slow provider should timeout and return empty"
        
        cards = await _execute_provider_async("openalex", "test", mock_impl_fast)
        assert len(cards) == 1, "Fast provider should complete successfully"
    
    @pytest.mark.asyncio
    async def test_provider_error_handling(self):
        """Test that provider errors don't crash the whole collection."""
        
        def failing_search(topic):
            raise Exception("Provider error")
        
        def working_search(topic):
            return [{"title": "Working", "url": "https://works.com"}]
        
        def to_cards(results):
            return [{"title": r["title"], "url": r["url"], "snippet": "Test"} for r in results]
        
        mock_providers = {
            "worldbank": {"search": failing_search, "to_cards": to_cards},
            "openalex": {"search": working_search, "to_cards": to_cards},
        }
        
        with patch("research_system.collection.enhanced.PROVIDERS", mock_providers):
            with patch("research_system.collection.enhanced.choose_providers") as mock_choose:
                mock_choose.return_value = MagicMock(
                    providers=["worldbank", "openalex"],
                    categories=["test"]
                )
                # Mock is_off_topic to always return False
                with patch("research_system.collection.enhanced.is_off_topic", return_value=False):
                    cards = await collect_from_free_apis_async("test topic")
                    
                    # Should get 1 card from working provider, failing provider is handled
                    assert len(cards) == 1
                    assert cards[0].title == "Working"
    
    def test_sync_wrapper_works(self):
        """Test that the synchronous wrapper works correctly."""
        
        def mock_search(topic):
            return [{"title": "Sync test", "url": "https://sync.com"}]
        
        def to_cards(results):
            return [{"title": r["title"], "url": r["url"], "snippet": "Test"} for r in results]
        
        mock_providers = {
            "wikipedia": {"search": mock_search, "to_cards": to_cards},
        }
        
        with patch("research_system.collection.enhanced.PROVIDERS", mock_providers):
            with patch("research_system.collection.enhanced.choose_providers") as mock_choose:
                mock_choose.return_value = MagicMock(
                    providers=["wikipedia"],
                    categories=["test"]
                )
                # Mock is_off_topic to always return False (not off-topic)
                with patch("research_system.collection.enhanced.is_off_topic", return_value=False):
                    # This should work without being in an async context
                    cards = collect_from_free_apis("test topic")
                    
                    assert len(cards) == 1
                    assert cards[0].title == "Sync test"
    
    @pytest.mark.asyncio
    async def test_metrics_recorded(self):
        """Test that metrics are properly recorded for each provider."""
        
        def mock_search(topic):
            return [{"title": "Metrics test", "url": "https://metrics.com"}]
        
        def to_cards(results):
            return [{"title": r["title"], "url": r["url"], "snippet": "Test"} for r in results]
        
        mock_impl = {"search": mock_search, "to_cards": to_cards}
        
        with patch("research_system.collection.enhanced.SEARCH_REQUESTS") as mock_requests:
            with patch("research_system.collection.enhanced.SEARCH_LATENCY") as mock_latency:
                cards = await _execute_provider_async("openalex", "test", mock_impl)
                
                # Check metrics were recorded
                mock_requests.labels.assert_called_with(provider="openalex")
                mock_requests.labels().inc.assert_called_once()
                mock_latency.labels.assert_called_with(provider="openalex")
                mock_latency.labels().observe.assert_called_once()
                
                assert len(cards) == 1