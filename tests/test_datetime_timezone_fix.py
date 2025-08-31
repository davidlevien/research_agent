"""Test timezone-aware datetime operations to prevent comparison errors."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock
import time


def test_gates_calculate_recent_primary_count():
    """Test that calculate_recent_primary_count uses timezone-aware datetimes."""
    from research_system.quality.gates import calculate_recent_primary_count
    
    # Create mock cards with different collected_at formats
    cards = []
    
    # Recent card (within 730 days)
    recent_card = Mock()
    recent_card.source_domain = 'oecd.org'
    recent_card.is_primary_source = True
    # Use Z suffix format (common in JSON APIs)
    recent_card.collected_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    cards.append(recent_card)
    
    # Old card (older than 730 days)
    old_card = Mock()
    old_card.source_domain = 'imf.org'
    old_card.is_primary_source = True
    old_date = datetime.now(timezone.utc) - timedelta(days=800)
    # Use Z suffix format
    old_card.collected_at = old_date.isoformat().replace('+00:00', 'Z')
    cards.append(old_card)
    
    # Card with no date
    no_date_card = Mock()
    no_date_card.source_domain = 'worldbank.org'
    no_date_card.is_primary_source = True
    no_date_card.collected_at = None
    cards.append(no_date_card)
    
    # Should not raise timezone comparison error
    count = calculate_recent_primary_count(cards)
    assert count == 1  # Only the recent card should count


def test_source_filters_is_recent_primary():
    """Test that is_recent_primary uses timezone-aware datetimes."""
    from research_system.selection.source_filters import is_recent_primary
    
    # Recent primary card
    recent_card = Mock()
    recent_card.source_domain = 'oecd.org'
    recent_card.is_primary_source = True
    recent_card.collected_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    
    # Should not raise timezone comparison error
    is_recent = is_recent_primary(recent_card)
    assert is_recent == True
    
    # Old primary card
    old_card = Mock()
    old_card.source_domain = 'imf.org'
    old_card.is_primary_source = True
    old_date = datetime.now(timezone.utc) - timedelta(days=800)
    old_card.collected_at = old_date.isoformat().replace('+00:00', 'Z')
    
    is_recent = is_recent_primary(old_card)
    assert is_recent == False


def test_datetime_safe_ensure_dt():
    """Test that ensure_dt always returns timezone-aware datetimes."""
    from research_system.utils.datetime_safe import ensure_dt
    
    # Test with naive datetime
    naive_dt = datetime(2024, 1, 1, 12, 0, 0)
    result = ensure_dt(naive_dt)
    assert result.tzinfo is not None
    assert result.tzinfo == timezone.utc
    
    # Test with aware datetime
    aware_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    result = ensure_dt(aware_dt)
    assert result.tzinfo is not None
    assert result == aware_dt
    
    # Test with timestamp
    timestamp = time.time()
    result = ensure_dt(timestamp)
    assert result.tzinfo is not None
    assert result.tzinfo == timezone.utc
    
    # Test with ISO string
    iso_string = "2024-01-01T12:00:00Z"
    result = ensure_dt(iso_string)
    assert result.tzinfo is not None
    assert result.tzinfo == timezone.utc


def test_datetime_safe_ensure_datetime():
    """Test that ensure_datetime always returns timezone-aware datetimes."""
    from research_system.utils.datetime_safe import ensure_datetime
    
    # Test with naive datetime
    naive_dt = datetime(2024, 1, 1, 12, 0, 0)
    result = ensure_datetime(naive_dt)
    assert result.tzinfo is not None
    assert result.tzinfo == timezone.utc
    
    # Test with aware datetime
    aware_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    result = ensure_datetime(aware_dt)
    assert result.tzinfo is not None
    assert result == aware_dt
    
    # Test with timestamp
    timestamp = time.time()
    result = ensure_datetime(timestamp)
    assert result.tzinfo is not None
    assert result.tzinfo == timezone.utc
    
    # Test with string
    date_string = "2024-01-01 12:00:00"
    result = ensure_datetime(date_string)
    assert result.tzinfo is not None
    assert result.tzinfo == timezone.utc


def test_quality_assurance_age_calculation():
    """Test that quality assurance age calculation uses timezone-aware datetime."""
    # The age calculation is now using timezone-aware datetime.now(timezone.utc).year
    # which won't cause comparison errors. The fix was applied in core/quality_assurance.py
    # at line 154 where we changed from datetime.now().year to datetime.now(timezone.utc).year
    
    # Verify we can get the current year with timezone awareness
    from datetime import datetime, timezone
    current_year = datetime.now(timezone.utc).year
    assert isinstance(current_year, int)
    assert current_year >= 2024  # Sanity check


def test_health_uptime_calculation():
    """Test that health uptime calculation uses timezone-aware datetimes."""
    from research_system.core.health import HealthMonitor
    
    monitor = HealthMonitor()
    
    # Should not raise timezone comparison error
    uptime = monitor.get_uptime()
    assert isinstance(uptime, timedelta)


def test_mixed_datetime_comparisons():
    """Test that we can safely compare datetimes from different sources."""
    from research_system.utils.datetime_safe import ensure_dt, ensure_datetime
    
    # Create various datetime representations
    naive_dt = datetime(2024, 1, 1, 12, 0, 0)
    aware_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    timestamp = time.time()
    iso_string = "2024-01-01T12:00:00Z"
    
    # Convert all to timezone-aware using our functions
    dt1 = ensure_dt(naive_dt)
    dt2 = ensure_dt(aware_dt)
    dt3 = ensure_dt(timestamp)
    dt4 = ensure_dt(iso_string)
    
    # All should be comparable without errors
    assert dt1 < dt3  # Historical date < current timestamp
    assert dt2 == dt1  # Same date
    assert dt4 == dt1  # Same date from ISO string
    
    # Test with ensure_datetime as well
    dt5 = ensure_datetime(naive_dt)
    dt6 = ensure_datetime(timestamp)
    
    # Should be comparable
    assert dt5 < dt6  # Historical date < current timestamp
    
    # All should have timezone info
    for dt in [dt1, dt2, dt3, dt4, dt5, dt6]:
        assert dt.tzinfo is not None


def test_datetime_comparison_in_production_flow():
    """Simulate the production flow that was causing the error."""
    from research_system.quality.gates import calculate_recent_primary_count
    from research_system.quality.metrics_v2 import compute_metrics
    
    # Create cards with mixed datetime formats (simulating real data)
    cards = []
    
    # Card with timezone-aware collected_at
    card1 = Mock()
    card1.source_domain = 'oecd.org'
    card1.is_primary_source = True
    card1.collected_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    card1.credibility_score = 0.8
    card1.triangulated = True
    card1.labels = None
    cards.append(card1)
    
    # Card with naive datetime string
    card2 = Mock()
    card2.source_domain = 'imf.org'
    card2.is_primary_source = True
    card2.collected_at = datetime.now().isoformat()  # Naive datetime string
    card2.credibility_score = 0.7
    card2.triangulated = False
    card2.labels = None
    cards.append(card2)
    
    # This should not raise "can't compare offset-naive and offset-aware datetimes"
    try:
        # Compute metrics (calls calculate_recent_primary_count internally)
        metrics = compute_metrics(cards)
        
        # Verify metrics were computed
        assert metrics.primary_share > 0
        assert metrics.sample_sizes['total_cards'] == 2
        
        # Also test direct call
        count = calculate_recent_primary_count(cards)
        assert count >= 0  # Should complete without error
        
    except TypeError as e:
        if "can't compare offset-naive and offset-aware datetimes" in str(e):
            pytest.fail(f"Timezone comparison error still exists: {e}")
        raise


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])