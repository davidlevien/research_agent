"""Provider-level circuit breaker to prevent API exhaustion."""

import os
import time
import logging
import random
from typing import Dict, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ProviderState:
    """State for a single provider."""
    consecutive_failures: int = 0
    last_failure_time: float = 0
    circuit_open_until: float = 0
    total_attempts: int = 0
    total_failures: int = 0
    last_429_time: float = 0
    backoff_until: float = 0


class ProviderCircuitBreaker:
    """Circuit breaker with exponential backoff for provider APIs."""
    
    def __init__(
        self, 
        failure_threshold: int = 3,
        cooldown_seconds: int = 600,  # 10 minutes
        max_backoff_seconds: int = 300,  # 5 minutes
        initial_backoff_seconds: int = 5
    ):
        """
        Initialize provider circuit breaker.
        
        Args:
            failure_threshold: Consecutive failures before opening circuit
            cooldown_seconds: Time to keep circuit open
            max_backoff_seconds: Maximum backoff duration
            initial_backoff_seconds: Initial backoff duration
        """
        # Read from environment with defaults
        self.failure_threshold = int(os.getenv("PROVIDER_CB_THRESHOLD", str(failure_threshold)))
        self.cooldown_seconds = int(os.getenv("PROVIDER_CB_COOLDOWN", str(cooldown_seconds)))
        self.max_backoff = int(os.getenv("PROVIDER_MAX_BACKOFF", str(max_backoff_seconds)))
        self.initial_backoff = int(os.getenv("PROVIDER_INITIAL_BACKOFF", str(initial_backoff_seconds)))
        
        # Provider states
        self.states: Dict[str, ProviderState] = defaultdict(ProviderState)
        
    def is_available(self, provider: str) -> Tuple[bool, Optional[str]]:
        """
        Check if provider is available for requests.
        
        Args:
            provider: Provider name (e.g., "serpapi", "tavily")
            
        Returns:
            Tuple of (is_available, reason_if_not)
        """
        state = self.states[provider]
        now = time.time()
        
        # Check if circuit is open
        if now < state.circuit_open_until:
            remaining = int(state.circuit_open_until - now)
            return False, f"Circuit open for {remaining}s after {state.consecutive_failures} failures"
        
        # Check if in backoff
        if now < state.backoff_until:
            remaining = int(state.backoff_until - now)
            return False, f"Rate limit backoff for {remaining}s"
        
        return True, None
    
    def record_success(self, provider: str):
        """Record successful API call."""
        state = self.states[provider]
        state.consecutive_failures = 0
        state.total_attempts += 1
        # Clear backoff on success
        state.backoff_until = 0
        logger.debug(f"Provider {provider} success recorded")
    
    def record_failure(self, provider: str, status_code: Optional[int] = None):
        """
        Record failed API call.
        
        Args:
            provider: Provider name
            status_code: HTTP status code if available
        """
        state = self.states[provider]
        now = time.time()
        
        state.consecutive_failures += 1
        state.total_attempts += 1
        state.total_failures += 1
        state.last_failure_time = now
        
        # Handle rate limiting (429) with exponential backoff
        if status_code == 429:
            state.last_429_time = now
            # Calculate exponential backoff with jitter
            backoff_multiplier = min(2 ** (state.consecutive_failures - 1), 32)
            backoff_seconds = min(
                self.initial_backoff * backoff_multiplier,
                self.max_backoff
            )
            # Add jitter (±20%)
            jitter = random.uniform(0.8, 1.2)
            backoff_seconds = int(backoff_seconds * jitter)
            
            state.backoff_until = now + backoff_seconds
            logger.warning(
                f"Provider {provider} rate limited (429), "
                f"backing off for {backoff_seconds}s"
            )
        
        # Open circuit if threshold reached
        if state.consecutive_failures >= self.failure_threshold:
            state.circuit_open_until = now + self.cooldown_seconds
            logger.error(
                f"Provider {provider} circuit opened after "
                f"{state.consecutive_failures} consecutive failures, "
                f"cooling down for {self.cooldown_seconds}s"
            )
    
    def get_health_stats(self, provider: str) -> Dict:
        """Get health statistics for a provider."""
        state = self.states[provider]
        now = time.time()
        
        return {
            "provider": provider,
            "is_available": self.is_available(provider)[0],
            "consecutive_failures": state.consecutive_failures,
            "total_attempts": state.total_attempts,
            "total_failures": state.total_failures,
            "failure_rate": (
                state.total_failures / max(1, state.total_attempts)
            ),
            "circuit_open": now < state.circuit_open_until,
            "in_backoff": now < state.backoff_until,
            "last_failure": (
                f"{int(now - state.last_failure_time)}s ago"
                if state.last_failure_time > 0
                else "Never"
            )
        }
    
    def reset(self, provider: Optional[str] = None):
        """Reset circuit breaker state."""
        if provider:
            self.states[provider] = ProviderState()
            logger.info(f"Reset circuit breaker for {provider}")
        else:
            self.states.clear()
            logger.info("Reset all circuit breakers")
    
    def get_available_providers(self, providers: list) -> list:
        """
        Filter list of providers to only available ones.
        
        Args:
            providers: List of provider names
            
        Returns:
            List of available provider names
        """
        available = []
        for provider in providers:
            is_avail, reason = self.is_available(provider)
            if is_avail:
                available.append(provider)
            else:
                logger.debug(f"Provider {provider} unavailable: {reason}")
        return available


# Global provider circuit breaker instance
PROVIDER_CIRCUIT = ProviderCircuitBreaker()