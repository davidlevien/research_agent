"""Circuit breaker for domain failures to prevent repeat stalls."""
import os
import time
import collections
from typing import Dict, Any


class Circuit:
    """Circuit breaker pattern for HTTP failures per domain."""
    
    def __init__(self, fail_thresh: int = None, cooldown: int = None):
        """Initialize circuit breaker.
        
        Args:
            fail_thresh: Number of failures before opening circuit
            cooldown: Seconds to wait before closing circuit
        """
        # Read from environment if not provided
        if fail_thresh is None:
            fail_thresh = int(os.getenv("HTTP_CB_FAILS", "3"))
        if cooldown is None:
            cooldown = int(os.getenv("HTTP_CB_RESET", "900"))
            
        self.state: Dict[str, Dict[str, Any]] = collections.defaultdict(
            lambda: {'f': 0, 'until': 0}
        )
        self.t = time.time
        self.th = fail_thresh
        self.cd = cooldown
    
    def allow(self, host: str) -> bool:
        """Check if requests to host are allowed.
        
        Args:
            host: Domain/host to check
            
        Returns:
            True if circuit is closed (requests allowed)
        """
        s = self.state[host]
        return self.t() >= s['until']
    
    def fail(self, host: str) -> None:
        """Record a failure for host.
        
        Args:
            host: Domain/host that failed
        """
        s = self.state[host]
        s['f'] += 1
        # Open circuit if threshold reached
        if s['f'] >= self.th:
            s['until'] = self.t() + self.cd
    
    def ok(self, host: str) -> None:
        """Record a success for host, resetting failures.
        
        Args:
            host: Domain/host that succeeded
        """
        self.state[host] = {'f': 0, 'until': 0}
    
    def is_open(self, host: str) -> bool:
        """Check if circuit is currently open for host.
        
        Args:
            host: Domain/host to check
            
        Returns:
            True if circuit is open (requests blocked)
        """
        return not self.allow(host)
    
    def reset(self, host: str) -> None:
        """Manually reset circuit for host.
        
        Args:
            host: Domain/host to reset
        """
        if host in self.state:
            del self.state[host]


# Global circuit breaker instance
CIRCUIT = Circuit()