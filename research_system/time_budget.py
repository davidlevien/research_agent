"""Time budget management for deadline propagation."""
import time
from typing import Optional


class Budget:
    """Wall-clock time budget tracker."""
    
    def __init__(self, seconds: int):
        """Initialize budget with total seconds.
        
        Args:
            seconds: Total wall-clock seconds for operation
        """
        self.t0 = time.time()
        self.deadline = self.t0 + seconds
        self.total_seconds = seconds
    
    def remaining(self) -> float:
        """Get remaining time in seconds.
        
        Returns:
            Remaining seconds (minimum 0.1 to avoid 0 timeouts)
        """
        return max(0.1, self.deadline - time.time())
    
    def elapsed(self) -> float:
        """Get elapsed time in seconds.
        
        Returns:
            Seconds since budget started
        """
        return time.time() - self.t0
    
    def is_expired(self) -> bool:
        """Check if budget has expired.
        
        Returns:
            True if deadline has passed
        """
        return time.time() >= self.deadline
    
    def percentage_used(self) -> float:
        """Get percentage of budget used.
        
        Returns:
            Percentage (0-100) of budget consumed
        """
        return min(100.0, (self.elapsed() / self.total_seconds) * 100)
    
    def get_timeout(self, max_timeout: Optional[int] = None) -> float:
        """Get timeout value respecting both budget and max.
        
        Args:
            max_timeout: Maximum timeout in seconds
            
        Returns:
            Minimum of remaining budget and max_timeout
        """
        remaining = self.remaining()
        if max_timeout:
            return min(remaining, max_timeout)
        return remaining


# Global budget instance (set at start of orchestrator.run)
_GLOBAL_BUDGET: Optional[Budget] = None


def set_global_budget(seconds: int) -> Budget:
    """Set global time budget.
    
    Args:
        seconds: Total seconds for operation
        
    Returns:
        Budget instance
    """
    global _GLOBAL_BUDGET
    _GLOBAL_BUDGET = Budget(seconds)
    return _GLOBAL_BUDGET


def get_global_budget() -> Optional[Budget]:
    """Get current global budget.
    
    Returns:
        Budget instance or None
    """
    return _GLOBAL_BUDGET


def get_timeout(max_timeout: Optional[int] = None) -> float:
    """Get timeout respecting global budget.
    
    Args:
        max_timeout: Maximum timeout in seconds
        
    Returns:
        Timeout value in seconds
    """
    if _GLOBAL_BUDGET:
        return _GLOBAL_BUDGET.get_timeout(max_timeout)
    return max_timeout or 30.0